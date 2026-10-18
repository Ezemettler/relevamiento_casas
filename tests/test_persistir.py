"""Tests del pipeline de persistencia — acá viven las reglas no negociables
del dominio (CLAUDE.md). Se arman `ItemListado`/`DetalleCrudo` a mano, sin
HTML ni red: lo que se testea es la lógica de negocio, no el parseo (eso ya
está cubierto en test_adapter_yaml.py).

Corre contra SQLite en memoria.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from relevamiento.modelos import (
    Base,
    Cambio,
    EstadoPropiedad,
    Fuente,
    Propiedad,
    TipoCambio,
    TipoFuente,
)
from relevamiento.pipeline.persistir import ejecutar_corrida
from relevamiento.scraping.base import DetalleCrudo, ItemListado

MAPEO_TIPOLOGIA = {"casa": "casa", "ph": "ph", "departamento": "departamento"}

FILTROS = {
    "recoleccion": {
        "tipologias": ["casa", "ph", "departamento"],
        "ambientes_minimos_departamento": 3,
    },
    # Sin zonas/alias: clasificar_zona da None y no afecta estas pruebas.
    "zonas": {},
    "alias_localidad": {},
}


@pytest.fixture
def sesion():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(motor)
    with Session(motor) as s:
        yield s


@pytest.fixture
def fuente(sesion):
    f = Fuente(
        nombre="Fuente de prueba",
        tipo=TipoFuente.INMOBILIARIA_LOCAL,
        url_base="https://ejemplo.test",
    )
    sesion.add(f)
    sesion.commit()
    return f


def _item(id_en_fuente="1", precio_texto="USD100.000", tipo="Casa", **extra):
    return ItemListado(
        id_en_fuente=id_en_fuente,
        url=f"https://ejemplo.test/p/{id_en_fuente}",
        tipo_ubicacion_texto=f"{tipo} en Venta en Castelar",
        direccion_texto="Calle Falsa 123",
        precio_texto=precio_texto,
        **extra,
    )


def _detalle_casa(ambientes="4"):
    return DetalleCrudo(
        caracteristicas={
            "ambientes": ambientes,
            "dormitorios": "3",
            "banos": "2",
            "antiguedad_anios": "20 Años",
            "m2_cubiertos": "150 m²",
            "m2_terreno": "200 m²",
        },
        descripcion="Una descripción cualquiera.",
    )


def _sin_detalle(_item):
    """Para tests que no deberían llegar a pedir el detalle."""
    raise AssertionError("no debería haberse pedido el detalle")


def test_primera_corrida_crea_propiedad_nueva(sesion, fuente):
    resultado = ejecutar_corrida(
        sesion,
        fuente,
        items=[_item()],
        obtener_detalle=lambda _item: _detalle_casa(),
        mapeo_tipologia=MAPEO_TIPOLOGIA,
        filtros=FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()

    assert not resultado.abortada
    assert resultado.corrida.nuevas == 1
    propiedad = sesion.query(Propiedad).one()
    assert propiedad.estado == EstadoPropiedad.ACTIVA
    assert float(propiedad.precio_actual) == 100000.0
    assert propiedad.ambientes == 4
    assert propiedad.fecha_primera_vista == date(2026, 8, 4)


def test_segunda_corrida_sin_cambios_no_genera_cambio_de_precio(sesion, fuente):
    ejecutar_corrida(
        sesion,
        fuente,
        [_item()],
        lambda _i: _detalle_casa(),
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()

    ejecutar_corrida(
        sesion,
        fuente,
        [_item()],  # mismo precio
        _sin_detalle,  # no debería hacer falta pedir el detalle de nuevo
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 11),
    )
    sesion.commit()

    assert sesion.query(Propiedad).count() == 1
    assert sesion.query(Cambio).count() == 0
    propiedad = sesion.query(Propiedad).one()
    assert propiedad.fecha_ultima_vista == date(2026, 8, 11)


def test_baja_de_precio_genera_cambio_y_actualiza_precio_actual(sesion, fuente):
    ejecutar_corrida(
        sesion,
        fuente,
        [_item(precio_texto="USD100.000")],
        lambda _i: _detalle_casa(),
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()

    ejecutar_corrida(
        sesion,
        fuente,
        [_item(precio_texto="USD89.000")],
        _sin_detalle,
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 11),
    )
    sesion.commit()

    propiedad = sesion.query(Propiedad).one()
    assert float(propiedad.precio_actual) == 89000.0
    # precio_inicial NO cambia: es historia, no estado actual.
    assert float(propiedad.precio_inicial) == 100000.0

    cambio = sesion.query(Cambio).one()
    assert cambio.tipo == TipoCambio.PRECIO
    assert cambio.valor_anterior == "100000.0"
    assert cambio.valor_nuevo == "89000.0"
    assert round(cambio.variacion_pct, 1) == -11.0


def test_propiedad_que_desaparece_se_marca_finalizada_sin_borrar(sesion, fuente):
    """Con 2 propiedades activas, que 1 desaparezca deja el barrido en 50%
    del total previo — justo en el umbral, no por debajo — así se prueba la
    finalización sin disparar el aborto por salud (regla 5), que es un
    comportamiento distinto y ya cubierto en su propio test.
    """
    ejecutar_corrida(
        sesion,
        fuente,
        [_item("1"), _item("2")],
        lambda _i: _detalle_casa(),
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()

    # Segunda corrida: solo sigue apareciendo la "1".
    resultado = ejecutar_corrida(
        sesion,
        fuente,
        [_item("1")],
        _sin_detalle,
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 11),
    )
    sesion.commit()

    assert not resultado.abortada
    assert resultado.corrida.finalizadas == 1
    assert sesion.query(Propiedad).count() == 2  # nunca se borra
    finalizada = sesion.query(Propiedad).filter_by(id_en_fuente="2").one()
    assert finalizada.estado == EstadoPropiedad.FINALIZADA
    assert finalizada.fecha_finalizacion == date(2026, 8, 11)

    cambio = sesion.query(Cambio).filter_by(tipo=TipoCambio.ESTADO).one()
    assert cambio.valor_anterior == "activa"
    assert cambio.valor_nuevo == "finalizada"


def test_propiedad_finalizada_que_reaparece_se_reactiva(sesion, fuente):
    ejecutar_corrida(
        sesion,
        fuente,
        [_item("1"), _item("2")],
        lambda _i: _detalle_casa(),
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()
    ejecutar_corrida(
        sesion,
        fuente,
        [_item("1")],
        _sin_detalle,
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 11),
    )
    sesion.commit()

    # La "2" vuelve a aparecer: NO es una propiedad nueva.
    resultado = ejecutar_corrida(
        sesion,
        fuente,
        [_item("1"), _item("2")],
        _sin_detalle,
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 18),
    )
    sesion.commit()

    assert resultado.corrida.nuevas == 0
    assert sesion.query(Propiedad).count() == 2  # se reactivó, no se duplicó
    reactivada = sesion.query(Propiedad).filter_by(id_en_fuente="2").one()
    assert reactivada.estado == EstadoPropiedad.ACTIVA
    assert reactivada.fecha_finalizacion is None

    cambio = sesion.query(Cambio).filter_by(tipo=TipoCambio.REACTIVACION).one()
    assert cambio.propiedad_id == reactivada.id
    assert cambio.valor_anterior == "finalizada"
    assert cambio.valor_nuevo == "activa"


def test_fuente_con_menos_del_50_por_ciento_aborta_sin_escribir(sesion, fuente):
    # Corrida inicial: 4 propiedades activas.
    items_iniciales = [_item(id_en_fuente=str(i)) for i in range(4)]
    ejecutar_corrida(
        sesion,
        fuente,
        items_iniciales,
        lambda _i: _detalle_casa(),
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()

    # Corrida siguiente: solo 1 de esas 4 (25%) — huele a fuente rota.
    resultado = ejecutar_corrida(
        sesion,
        fuente,
        [_item(id_en_fuente="0")],
        _sin_detalle,
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 11),
    )

    assert resultado.abortada
    assert "25%" in resultado.motivo
    # Ninguna propiedad quedó tocada por la corrida abortada.
    activas = sesion.query(Propiedad).filter_by(estado=EstadoPropiedad.ACTIVA).count()
    assert activas == 4


def test_departamento_de_menos_de_3_ambientes_se_descarta(sesion, fuente):
    resultado = ejecutar_corrida(
        sesion,
        fuente,
        [_item(tipo="Departamento")],
        lambda _i: _detalle_casa(ambientes="2"),
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()

    assert resultado.corrida.nuevas == 0
    assert sesion.query(Propiedad).count() == 0


def test_departamento_de_3_ambientes_se_acepta(sesion, fuente):
    resultado = ejecutar_corrida(
        sesion,
        fuente,
        [_item(tipo="Departamento")],
        lambda _i: _detalle_casa(ambientes="3"),
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()

    assert resultado.corrida.nuevas == 1


def test_tipologia_fuera_de_alcance_se_descarta_sin_pedir_detalle(sesion, fuente):
    """Un terreno no está en `mapeo_tipologia`: se descarta ANTES de pedir
    el detalle (ahorra un request, coherente con el uso responsable)."""
    resultado = ejecutar_corrida(
        sesion,
        fuente,
        [_item(tipo="Terreno")],
        _sin_detalle,
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()

    assert resultado.corrida.nuevas == 0
    assert sesion.query(Propiedad).count() == 0


def test_observacion_guarda_el_payload_crudo(sesion, fuente):
    ejecutar_corrida(
        sesion,
        fuente,
        [_item()],
        lambda _i: _detalle_casa(),
        MAPEO_TIPOLOGIA,
        FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()

    from relevamiento.modelos import Observacion

    observacion = sesion.query(Observacion).one()
    assert observacion.payload_crudo["item"]["id_en_fuente"] == "1"
    assert observacion.payload_crudo["detalle"]["caracteristicas"]["ambientes"] == "4"


def test_mismo_id_en_fuente_repetido_en_el_mismo_barrido_no_duplica(sesion, fuente):
    """Pasó de verdad con Sarro Pucheta (corrida del 2026-10-17): un solape
    de paginación hizo que el mismo aviso apareciera dos veces en el mismo
    barrido. La segunda aparición tiene que actualizar la que se acaba de
    crear, no intentar insertarla de nuevo — si no, la restricción de
    identidad única rechaza el duplicado y tumba toda la fuente."""
    resultado = ejecutar_corrida(
        sesion,
        fuente,
        items=[_item(id_en_fuente="1"), _item(id_en_fuente="1")],
        obtener_detalle=lambda _item: _detalle_casa(),
        mapeo_tipologia=MAPEO_TIPOLOGIA,
        filtros=FILTROS,
        hoy=date(2026, 8, 4),
    )
    sesion.commit()

    assert not resultado.abortada
    assert resultado.corrida.nuevas == 1
    assert resultado.corrida.actualizadas == 1
    assert sesion.query(Propiedad).count() == 1
