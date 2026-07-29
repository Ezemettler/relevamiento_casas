"""Persistencia de una corrida.

Este módulo es el único lugar que escribe en `propiedades`, `observaciones`
y `cambios`. Concentra acá las reglas no negociables del dominio (ver
CLAUDE.md) para que no se puedan romper por accidente en el código de una
fuente en particular:

  1. Nunca se borra un registro — lo que desaparece se marca `finalizada`.
  2. Nunca se toca `evaluaciones` — ni siquiera se importa ese modelo acá.
  3. La identidad es (fuente_id, id_en_fuente) — ya la garantiza la base
     (UniqueConstraint en el modelo); acá se respeta buscando por esa clave
     antes de decidir si algo es nuevo.
  4. Se guarda `payload_crudo` de cada observación.
  5. Si la fuente trae menos del 50% de lo esperado, se aborta sin escribir.

Deliberadamente no sabe nada de HTTP, YAML ni HTML: recibe una lista de
`ItemListado` ya parseados y una función para pedir el detalle de uno en
particular. Eso permite testear las reglas del dominio con datos armados a
mano, sin fixtures de HTML ni red — ver tests/test_persistir.py.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from relevamiento.config import cargar_yaml
from relevamiento.modelos import (
    Cambio,
    Corrida,
    EstadoCorrida,
    EstadoPropiedad,
    Fuente,
    Observacion,
    Propiedad,
    TipoCambio,
    Tipologia,
)
from relevamiento.normalizacion.precios import parsear_precio
from relevamiento.normalizacion.superficie import parsear_entero, parsear_numero
from relevamiento.normalizacion.texto import quitar_acentos
from relevamiento.normalizacion.ubicacion import clasificar_zona, parsear_tipo_ubicacion
from relevamiento.scraping.base import DetalleCrudo, ItemListado

ObtenerDetalleFn = Callable[[ItemListado], DetalleCrudo]

# Umbral de la regla 5: si el barrido trae menos de esta proporción de lo
# que había activo la corrida anterior, se asume que la fuente se rompió
# (cambio de plantilla, bloqueo de acceso) y no se escribe nada.
UMBRAL_SALUD = 0.5


@dataclass
class ResultadoCorrida:
    corrida: Corrida
    abortada: bool
    motivo: str | None = None


def ejecutar_corrida(
    sesion: Session,
    fuente: Fuente,
    items: list[ItemListado],
    obtener_detalle: ObtenerDetalleFn,
    mapeo_tipologia: dict[str, str],
    filtros: dict[str, Any] | None = None,
    hoy: date | None = None,
) -> ResultadoCorrida:
    hoy = hoy or date.today()
    filtros = filtros if filtros is not None else cargar_yaml("filtros.yaml")

    corrida = Corrida(inicio=datetime.now(UTC), estado=EstadoCorrida.OK)
    sesion.add(corrida)
    sesion.flush()  # asigna corrida.id sin cerrar la transacción

    activas_previas = list(
        sesion.scalars(
            select(Propiedad).where(
                Propiedad.fuente_id == fuente.id,
                Propiedad.estado == EstadoPropiedad.ACTIVA,
            )
        )
    )

    if activas_previas and len(items) < UMBRAL_SALUD * len(activas_previas):
        motivo = (
            f"Se esperaban ~{len(activas_previas)} propiedades activas y "
            f"el barrido trajo {len(items)} "
            f"({len(items) / len(activas_previas):.0%}). Se aborta sin "
            "escribir nada: probablemente la fuente cambió de plantilla o "
            "está bloqueando el acceso."
        )
        corrida.estado = EstadoCorrida.ERROR
        corrida.errores = {fuente.nombre: motivo}
        corrida.fin = datetime.now(UTC)
        return ResultadoCorrida(corrida=corrida, abortada=True, motivo=motivo)

    previas_por_id = {p.id_en_fuente: p for p in activas_previas}
    finalizadas_por_id = {
        p.id_en_fuente: p
        for p in sesion.scalars(
            select(Propiedad).where(
                Propiedad.fuente_id == fuente.id,
                Propiedad.estado == EstadoPropiedad.FINALIZADA,
            )
        )
    }

    vistos: set[str] = set()
    for item in items:
        if not item.id_en_fuente:
            continue
        vistos.add(item.id_en_fuente)

        existente = previas_por_id.get(item.id_en_fuente) or finalizadas_por_id.get(
            item.id_en_fuente
        )
        if existente is not None:
            _actualizar_propiedad(sesion, existente, item, corrida, hoy)
            corrida.actualizadas += 1
            continue

        creada = _crear_propiedad(
            sesion, fuente, item, obtener_detalle, mapeo_tipologia, filtros, corrida, hoy
        )
        if creada:
            corrida.nuevas += 1

    for id_en_fuente, propiedad in previas_por_id.items():
        if id_en_fuente not in vistos:
            _finalizar_propiedad(sesion, propiedad, corrida, hoy)
            corrida.finalizadas += 1

    corrida.fin = datetime.now(UTC)
    return ResultadoCorrida(corrida=corrida, abortada=False)


def _tipologia_permitida(
    tipo_texto: str | None, mapeo_tipologia: dict[str, str], filtros: dict[str, Any]
) -> Tipologia | None:
    """None si la propiedad no entra en el alcance de recolección (terreno,
    alquiler-tipo-no-mapeado, etc.) — ver config/filtros.yaml `recoleccion`.
    """
    if not tipo_texto:
        return None
    clave = quitar_acentos(tipo_texto).strip().lower()
    nombre = mapeo_tipologia.get(clave)
    if nombre is None:
        return None

    permitidas = filtros.get("recoleccion", {}).get("tipologias", [])
    if nombre not in permitidas:
        return None
    return Tipologia(nombre)


def _crear_propiedad(
    sesion: Session,
    fuente: Fuente,
    item: ItemListado,
    obtener_detalle: ObtenerDetalleFn,
    mapeo_tipologia: dict[str, str],
    filtros: dict[str, Any],
    corrida: Corrida,
    hoy: date,
) -> bool:
    ubicacion = parsear_tipo_ubicacion(item.tipo_ubicacion_texto)
    tipologia = _tipologia_permitida(ubicacion["tipo_texto"], mapeo_tipologia, filtros)
    if tipologia is None:
        return False

    detalle = obtener_detalle(item)
    caract = detalle.caracteristicas

    ambientes = parsear_entero(caract.get("ambientes"))
    minimo_depto = filtros.get("recoleccion", {}).get("ambientes_minimos_departamento", 0)
    if tipologia == Tipologia.DEPARTAMENTO and (ambientes or 0) < minimo_depto:
        return False

    precio = parsear_precio(item.precio_texto)
    monto, moneda = precio if precio else (None, None)
    localidad = ubicacion["localidad"]

    propiedad = Propiedad(
        fuente_id=fuente.id,
        id_en_fuente=item.id_en_fuente,
        url=item.url,
        tipologia=tipologia,
        ambientes=ambientes,
        dormitorios=parsear_entero(caract.get("dormitorios")),
        banos=parsear_entero(caract.get("banos")),
        m2_cubiertos=parsear_numero(caract.get("m2_cubiertos")),
        m2_totales=parsear_numero(caract.get("m2_totales")),
        m2_terreno=parsear_numero(caract.get("m2_terreno")),
        antiguedad_anios=parsear_entero(caract.get("antiguedad_anios")),
        direccion_texto=item.direccion_texto,
        barrio=ubicacion["barrio"],
        localidad=localidad,
        categoria_zona=clasificar_zona(localidad, barrio=ubicacion["barrio"]),
        precio_inicial=monto,
        moneda_inicial=moneda,
        precio_actual=monto,
        moneda_actual=moneda,
        descripcion=detalle.descripcion,
        estado=EstadoPropiedad.ACTIVA,
        fecha_primera_vista=hoy,
        fecha_ultima_vista=hoy,
    )
    sesion.add(propiedad)
    sesion.flush()  # asigna propiedad.id para la observación

    sesion.add(
        Observacion(
            propiedad_id=propiedad.id,
            corrida_id=corrida.id,
            fecha=hoy,
            precio=monto,
            moneda=moneda,
            visible=True,
            payload_crudo={"item": asdict(item), "detalle": asdict(detalle)},
        )
    )
    return True


def _actualizar_propiedad(
    sesion: Session, propiedad: Propiedad, item: ItemListado, corrida: Corrida, hoy: date
) -> None:
    """No vuelve a pedir el detalle: los atributos físicos (m², ambientes,
    antigüedad) no cambian semana a semana. Solo precio y estado se
    re-chequean, que es lo único que el listado ya trae liviano.
    """
    precio = parsear_precio(item.precio_texto)
    monto, moneda = precio if precio else (None, None)

    if monto is not None and propiedad.precio_actual is not None:
        anterior = float(propiedad.precio_actual)
        if round(anterior, 2) != round(monto, 2):
            variacion = (monto - anterior) / anterior * 100 if anterior else None
            sesion.add(
                Cambio(
                    propiedad_id=propiedad.id,
                    fecha=hoy,
                    tipo=TipoCambio.PRECIO,
                    campo="precio",
                    valor_anterior=str(anterior),
                    valor_nuevo=str(monto),
                    variacion_pct=variacion,
                )
            )
            propiedad.precio_actual = monto
            propiedad.moneda_actual = moneda or propiedad.moneda_actual

    if propiedad.estado == EstadoPropiedad.FINALIZADA:
        sesion.add(
            Cambio(
                propiedad_id=propiedad.id,
                fecha=hoy,
                tipo=TipoCambio.REACTIVACION,
                campo="estado",
                valor_anterior=EstadoPropiedad.FINALIZADA.value,
                valor_nuevo=EstadoPropiedad.ACTIVA.value,
            )
        )
        propiedad.estado = EstadoPropiedad.ACTIVA
        propiedad.fecha_finalizacion = None

    propiedad.fecha_ultima_vista = hoy
    sesion.add(
        Observacion(
            propiedad_id=propiedad.id,
            corrida_id=corrida.id,
            fecha=hoy,
            precio=monto,
            moneda=moneda,
            visible=True,
            payload_crudo={"item": asdict(item)},
        )
    )


def _finalizar_propiedad(
    sesion: Session, propiedad: Propiedad, corrida: Corrida, hoy: date
) -> None:
    """No se seleccionó en este barrido: se marca finalizada, NUNCA se borra."""
    sesion.add(
        Cambio(
            propiedad_id=propiedad.id,
            fecha=hoy,
            tipo=TipoCambio.ESTADO,
            campo="estado",
            valor_anterior=EstadoPropiedad.ACTIVA.value,
            valor_nuevo=EstadoPropiedad.FINALIZADA.value,
        )
    )
    propiedad.estado = EstadoPropiedad.FINALIZADA
    propiedad.fecha_finalizacion = hoy
