"""Consultas de datos compartidas entre las páginas de la app.

Cada función abre su propia sesión y devuelve datos ya "desconectados"
(dicts, DataFrames) en vez de objetos de SQLAlchemy — así ninguna página
corre el riesgo de acceder a un atributo después de que la sesión se cerró
(`DetachedInstanceError`), que es el error clásico de mezclar ORM con una
UI que vive en reruns cortos como Streamlit.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from relevamiento.config import cargar_yaml
from relevamiento.db import sesion
from relevamiento.modelos import (
    Cambio,
    Corrida,
    EstadoPropiedad,
    Evaluacion,
    Fuente,
    Observacion,
    Propiedad,
    TipoCambio,
)
from relevamiento.normalizacion.ubicacion import nombre_legible_localidad


def filtros_configurados() -> dict[str, Any]:
    """Valores por defecto que vienen de config/filtros.yaml, no del código."""
    return cargar_yaml("filtros.yaml")


def senial_negociacion(bajadas: int, dias_en_mercado: int) -> str:
    """'fuerte' / 'moderada' / 'baja' — cuánto margen hay para negociar.

    Combina cantidad de bajas de precio con tiempo publicado: varias bajas,
    o bajas + mucho tiempo sin venderse, sugieren un vendedor con necesidad
    real. Ver PLAN.md — es la síntesis de la señal más valiosa del sistema,
    para no tener que leer el historial completo de cada propiedad.
    """
    if bajadas >= 3 or (bajadas >= 2 and dias_en_mercado > 90):
        return "fuerte"
    if bajadas >= 1 or dias_en_mercado > 60:
        return "moderada"
    return "baja"


def _tendencia_texto(
    bajadas: int, variacion_pct: float | None, dias_en_mercado: int
) -> str:
    """Resumen compacto para una columna del listado — de un vistazo, sin
    tener que abrir el detalle de cada propiedad. Reemplaza a la vieja
    columna "señal" (fuerte/moderada/baja): esa categoría abstracta no decía
    nada por sí sola, esto muestra el hecho concreto detrás."""
    if bajadas == 0:
        if dias_en_mercado <= 7:
            return "nueva"
        return f"{dias_en_mercado} días sin cambios"
    plural = "s" if bajadas != 1 else ""
    if variacion_pct:
        return f"↓{abs(variacion_pct):.0f}% en {bajadas} baja{plural}"
    return f"↓ {bajadas} baja{plural}"


def _contar_bajadas_por_propiedad(s: Session) -> dict[int, int]:
    """Una sola consulta agrupada, no una por propiedad (evita N+1)."""
    filas = s.execute(
        select(Cambio.propiedad_id, func.count())
        .where(Cambio.tipo == TipoCambio.PRECIO)
        .group_by(Cambio.propiedad_id)
    ).all()
    return dict(filas)


def _fila_propiedad(
    p: Propiedad,
    bajadas: int,
    evaluacion: Evaluacion | None = None,
    inmobiliaria: str | None = None,
) -> dict[str, Any]:
    precio = float(p.precio_actual) if p.precio_actual is not None else None
    precio_inicial = float(p.precio_inicial) if p.precio_inicial is not None else None
    m2 = float(p.m2_cubiertos) if p.m2_cubiertos is not None else None
    dias_en_mercado = (date.today() - p.fecha_primera_vista).days
    variacion_pct = (
        round((precio - precio_inicial) / precio_inicial * 100, 1)
        if precio and precio_inicial
        else None
    )

    return {
        "id": p.id,
        "tipologia": p.tipologia.value if p.tipologia else None,
        "direccion": p.direccion_texto,
        "barrio": p.barrio,
        "localidad": p.localidad,
        "zona": p.categoria_zona.value if p.categoria_zona else None,
        "inmobiliaria": inmobiliaria,
        "precio_inicial": precio_inicial,
        "precio": precio,
        "moneda": p.moneda_actual.value if p.moneda_actual else None,
        "precio_m2": round(precio / m2, 0) if precio and m2 else None,
        "ambientes": p.ambientes,
        "dormitorios": p.dormitorios,
        "banos": p.banos,
        "m2_cubiertos": m2,
        "m2_totales": float(p.m2_totales) if p.m2_totales is not None else None,
        "m2_terreno": float(p.m2_terreno) if p.m2_terreno is not None else None,
        "antiguedad_anios": p.antiguedad_anios,
        "fecha_primera_vista": p.fecha_primera_vista,
        "dias_en_mercado": dias_en_mercado,
        "bajadas": bajadas,
        "variacion_pct": variacion_pct,
        "senial": senial_negociacion(bajadas, dias_en_mercado),
        "tendencia": _tendencia_texto(bajadas, variacion_pct, dias_en_mercado),
        # None en `Evaluacion.disponible` (sin fila todavía) cuenta como
        # disponible: ver docstring de `Evaluacion` en modelos.py.
        "disponible": evaluacion.disponible if evaluacion else True,
        "notas": evaluacion.notas if evaluacion else None,
        "humedad": evaluacion.humedad if evaluacion else None,
        "cochera": evaluacion.cochera if evaluacion else None,
        "patio_jardin": evaluacion.patio_jardin if evaluacion else None,
        "posibilidad_ampliacion": evaluacion.posibilidad_ampliacion
        if evaluacion
        else None,
        "ventilacion_cruzada": evaluacion.ventilacion_cruzada if evaluacion else None,
        "grietas": evaluacion.grietas if evaluacion else None,
        "desniveles": evaluacion.desniveles if evaluacion else None,
        "url": p.url,
    }


def listado_propiedades(
    tipologias: list[str] | None = None,
    categorias_zona: list[str] | None = None,
    precio_maximo: float | None = None,
    estados: list[str] | None = None,
    inmobiliarias: list[str] | None = None,
    barrios: list[str] | None = None,
) -> pd.DataFrame:
    """Propiedades activas, con los filtros aplicados. `None` = sin filtrar.

    `estados`: valores "disponible"/"descartada". `None` o solo
    ["disponible"] es el default de siempre (una propiedad sin fila en
    `evaluaciones` cuenta como disponible). Pasar ambos valores, o una
    lista vacía, no filtra por estado — trae las dos cosas. El scraping le
    sigue registrando cambios de precio a una descartada igual, esto solo
    controla qué se lista acá.
    """
    with sesion() as s:
        consulta = (
            select(Propiedad, Evaluacion, Fuente.nombre)
            .join(Fuente, Fuente.id == Propiedad.fuente_id)
            .outerjoin(Evaluacion, Evaluacion.propiedad_id == Propiedad.id)
            .where(Propiedad.estado == EstadoPropiedad.ACTIVA)
        )
        if tipologias:
            consulta = consulta.where(Propiedad.tipologia.in_(tipologias))
        if categorias_zona:
            consulta = consulta.where(Propiedad.categoria_zona.in_(categorias_zona))
        if precio_maximo:
            consulta = consulta.where(Propiedad.precio_actual <= precio_maximo)
        if estados is None or estados == ["disponible"]:
            consulta = consulta.where(
                or_(Evaluacion.disponible.is_(None), Evaluacion.disponible.is_(True))
            )
        elif estados == ["descartada"]:
            consulta = consulta.where(Evaluacion.disponible.is_(False))
        # cualquier otro caso (ambos estados, o ninguno seleccionado) no
        # filtra por estado — se listan todas.
        if inmobiliarias:
            consulta = consulta.where(Fuente.nombre.in_(inmobiliarias))
        if barrios:
            consulta = consulta.where(Propiedad.barrio.in_(barrios))

        bajadas_por_id = _contar_bajadas_por_propiedad(s)
        consulta = consulta.order_by(Propiedad.fecha_primera_vista.desc())
        filas_db = s.execute(consulta).all()
        filas = [
            _fila_propiedad(p, bajadas_por_id.get(p.id, 0), evaluacion, inmobiliaria)
            for p, evaluacion, inmobiliaria in filas_db
        ]

    return pd.DataFrame(filas)


def _evaluacion_a_dict(e: Evaluacion) -> dict[str, Any]:
    return {
        "fecha_visita": e.fecha_visita,
        "disponible": e.disponible,
        "luz_natural": e.luz_natural.value if e.luz_natural else None,
        "humedad": e.humedad,
        "orientacion": e.orientacion.value if e.orientacion else None,
        "distancia_estacion_km": float(e.distancia_estacion_km)
        if e.distancia_estacion_km is not None
        else None,
        "cochera": e.cochera,
        "patio_jardin": e.patio_jardin,
        "posibilidad_ampliacion": e.posibilidad_ampliacion,
        "ventilacion_cruzada": e.ventilacion_cruzada,
        "grietas": e.grietas,
        "desniveles": e.desniveles,
        "notas": e.notas,
    }


def evaluacion_actual(propiedad_id: int) -> dict[str, Any] | None:
    """Los datos complementarios ya cargados para esta propiedad, si hay."""
    with sesion() as s:
        e = s.scalar(select(Evaluacion).where(Evaluacion.propiedad_id == propiedad_id))
        return _evaluacion_a_dict(e) if e else None


def guardar_o_actualizar_evaluacion(propiedad_id: int, datos: dict[str, Any]) -> None:
    """Único punto de escritura en `evaluaciones` de toda la app — el
    scraping nunca pasa por acá (regla 2 de CLAUDE.md).

    Upsert: un solo registro por propiedad. Si ya existe, se actualiza en
    el lugar (no se agrega un historial de visitas fechadas — ver el
    docstring de `Evaluacion` en modelos.py sobre por qué).
    """
    with sesion() as s:
        existente = s.scalar(
            select(Evaluacion).where(Evaluacion.propiedad_id == propiedad_id)
        )
        if existente:
            for campo, valor in datos.items():
                setattr(existente, campo, valor)
        else:
            s.add(Evaluacion(propiedad_id=propiedad_id, **datos))


def actualizar_atributos_propiedad(propiedad_id: int, datos: dict[str, Any]) -> None:
    """Corrección manual de atributos físicos (m², ambientes, antigüedad...)
    que el scraping sacó mal o no encontró.

    Es la única escritura manual sobre `propiedades` en toda la app —
    separada de `guardar_o_actualizar_evaluacion` porque escribe en la
    tabla del scraping, no en evaluaciones. No hay conflicto con corridas
    futuras: `persistir.py` solo vuelve a tocar `precio_actual` y `estado`
    en propiedades ya vistas (ver `_actualizar_propiedad`), nunca estos
    campos — una corrección acá no se pierde en la próxima corrida.
    """
    with sesion() as s:
        propiedad = s.get(Propiedad, propiedad_id)
        for campo, valor in datos.items():
            setattr(propiedad, campo, valor)


def detalle_propiedad(propiedad_id: int) -> dict[str, Any] | None:
    """Todo lo necesario para el panel de detalle: la propiedad, su
    historial de cambios, el historial de precios semana a semana y los
    datos complementarios ya cargados."""
    with sesion() as s:
        p = s.get(Propiedad, propiedad_id)
        if p is None:
            return None

        bajadas_por_id = _contar_bajadas_por_propiedad(s)
        inmobiliaria = s.scalar(select(Fuente.nombre).where(Fuente.id == p.fuente_id))

        cambios = s.execute(
            select(Cambio)
            .where(Cambio.propiedad_id == propiedad_id)
            .order_by(Cambio.fecha.desc())
        ).scalars()
        cambios_lista = [
            {
                "fecha": c.fecha,
                "tipo": c.tipo.value,
                "campo": c.campo,
                "de": c.valor_anterior,
                "a": c.valor_nuevo,
                "variacion_pct": float(c.variacion_pct) if c.variacion_pct else None,
            }
            for c in cambios
        ]

        # Una fila por corrida (haya cambiado el precio o no) — a diferencia
        # de `cambios`, que solo registra cuándo algo cambió. Esto es lo que
        # arma la serie semanal completa para el gráfico de línea.
        observaciones = s.execute(
            select(Observacion.fecha, Observacion.precio)
            .where(
                Observacion.propiedad_id == propiedad_id,
                Observacion.precio.is_not(None),
            )
            .order_by(Observacion.fecha)
        ).all()
        historial_precios = [
            {"fecha": fecha, "precio": float(precio)} for fecha, precio in observaciones
        ]

        evaluacion = s.scalar(
            select(Evaluacion).where(Evaluacion.propiedad_id == propiedad_id)
        )

        # No es un duplicado a fusionar (ver PLAN.md, decisión D9): confirmado
        # en la práctica que la misma dirección + inmobiliaria casi siempre
        # son unidades distintas (edificios o lotes con varios avisos). Esto
        # es solo para avisar por qué puede parecer repetido en la tabla.
        otras_en_direccion = 0
        if p.direccion_texto:
            otras_en_direccion = s.scalar(
                select(func.count())
                .select_from(Propiedad)
                .where(
                    Propiedad.fuente_id == p.fuente_id,
                    Propiedad.direccion_texto == p.direccion_texto,
                    Propiedad.id != p.id,
                )
            )

        return {
            "propiedad": _fila_propiedad(
                p, bajadas_por_id.get(p.id, 0), evaluacion, inmobiliaria
            )
            | {"descripcion": p.descripcion, "otras_en_direccion": otras_en_direccion},
            "cambios": cambios_lista,
            "historial_precios": historial_precios,
            "evaluacion": _evaluacion_a_dict(evaluacion) if evaluacion else None,
        }


def inmobiliarias_disponibles() -> list[str]:
    """Nombres de fuentes activas — opciones para el filtro de inmobiliaria."""
    with sesion() as s:
        return sorted(
            s.scalars(select(Fuente.nombre).where(Fuente.activa.is_(True))).all()
        )


def barrios_disponibles(
    categorias_zona: list[str] | None = None, precio_maximo: float | None = None
) -> list[str]:
    """Barrios de propiedades disponibles — opciones para el filtro.

    Sin `categorias_zona`/`precio_maximo` traería barrios de cualquier zona
    (hasta de "fuera de alcance", como la costa) y de cualquier precio —
    acá se restringe a lo mismo que ve el listado por defecto, para no
    ofrecer barrios que después no van a aparecer nunca en la tabla.
    """
    with sesion() as s:
        consulta = (
            select(Propiedad.barrio)
            .outerjoin(Evaluacion, Evaluacion.propiedad_id == Propiedad.id)
            .where(
                Propiedad.estado == EstadoPropiedad.ACTIVA,
                Propiedad.barrio.is_not(None),
                or_(Evaluacion.disponible.is_(None), Evaluacion.disponible.is_(True)),
            )
            .distinct()
        )
        if categorias_zona:
            consulta = consulta.where(Propiedad.categoria_zona.in_(categorias_zona))
        if precio_maximo:
            consulta = consulta.where(Propiedad.precio_actual <= precio_maximo)
        return sorted(s.scalars(consulta).all())


def ultima_actualizacion() -> datetime | None:
    """Cuándo corrió la última corrida — para el cartel de 'actualizado el...'
    que aparece en todas las páginas. `None` si todavía no corrió ninguna."""
    with sesion() as s:
        corrida = s.execute(
            select(Corrida).order_by(Corrida.id.desc()).limit(1)
        ).scalar_one_or_none()
        return corrida.inicio if corrida else None


def resumen_general() -> dict[str, Any]:
    with sesion() as s:
        activas = s.scalar(
            select(func.count())
            .select_from(Propiedad)
            .where(Propiedad.estado == EstadoPropiedad.ACTIVA)
        )
        finalizadas = s.scalar(
            select(func.count())
            .select_from(Propiedad)
            .where(Propiedad.estado == EstadoPropiedad.FINALIZADA)
        )
        ultima_corrida = s.execute(
            select(Corrida).order_by(Corrida.id.desc()).limit(1)
        ).scalar_one_or_none()
        total_corridas = s.scalar(select(func.count()).select_from(Corrida))

        return {
            "activas": activas or 0,
            "finalizadas": finalizadas or 0,
            "total_corridas": total_corridas or 0,
            "ultima_corrida": (
                {
                    "inicio": ultima_corrida.inicio,
                    "estado": ultima_corrida.estado.value,
                    "nuevas": ultima_corrida.nuevas,
                    "actualizadas": ultima_corrida.actualizadas,
                    "finalizadas": ultima_corrida.finalizadas,
                }
                if ultima_corrida
                else None
            ),
        }


def precio_m2_por_localidad() -> pd.DataFrame:
    """Precio/m² promedio y stock, por localidad (Morón, Haedo, Castelar...).

    Más granular que agrupar por categoría de zona: permite comparar
    barrios entre sí, no solo "objetivo" contra "referencia" en bloque.
    Excluye "fuera de alcance" (Pinamar, Merlo...) — no sirven de
    comparación para la zona de compra.
    """
    df = listado_propiedades(categorias_zona=["objetivo", "referencia"])
    if df.empty:
        return df
    df = df.dropna(subset=["precio_m2", "localidad"]).copy()
    # Sin esto, "Morón" y "Moron" (distintas fuentes, mismo lugar) quedan
    # como dos barras separadas en vez de una.
    df["localidad"] = df["localidad"].map(nombre_legible_localidad)
    return (
        df.groupby("localidad")
        .agg(
            precio_m2_promedio=("precio_m2", "mean"),
            cantidad=("precio_m2", "count"),
            zona=("zona", "first"),
        )
        .round({"precio_m2_promedio": 0})
        .reset_index()
        .sort_values("precio_m2_promedio", ascending=False)
    )


def senales_negociacion_top(n: int = 5) -> pd.DataFrame:
    """Las propiedades con señal más fuerte — para no tener que escanear
    todo el listado buscando dónde hay margen para negociar."""
    df = listado_propiedades()
    if df.empty:
        return df
    orden_senial = {"fuerte": 0, "moderada": 1, "baja": 2}
    df = df[df["senial"] != "baja"].copy()
    if df.empty:
        return df
    df["_orden"] = df["senial"].map(orden_senial)
    columnas = ["_orden", "bajadas", "dias_en_mercado"]
    return (
        df.sort_values(columnas, ascending=[True, False, False])
        .drop(columns="_orden")
        .head(n)
    )


def flujo_semanal() -> pd.DataFrame:
    """Altas y bajas por semana — para ver si entra más de lo que sale.

    Con pocas semanas de corridas esto va a mostrar poco: es esperable,
    se completa solo con las próximas corridas automáticas.

    Arranque en frío (PLAN.md sección 4): la primera corrida carga TODAS
    las propiedades existentes de una sola vez — no son altas reales de esa
    semana, es la foto inicial. Se excluye esa fecha para no mostrar un pico
    artificial que además arrastra falsamente "Vendedor" en `tipo_mercado`.
    """
    with sesion() as s:
        primera_corrida = s.scalar(select(func.min(Corrida.inicio)))
        fecha_arranque_en_frio = primera_corrida.date() if primera_corrida else None

        altas = s.execute(select(Propiedad.fecha_primera_vista)).scalars().all()
        if fecha_arranque_en_frio:
            altas = [f for f in altas if f != fecha_arranque_en_frio]

        bajas = (
            s.execute(
                select(Propiedad.fecha_finalizacion).where(
                    Propiedad.fecha_finalizacion.is_not(None)
                )
            )
            .scalars()
            .all()
        )

    if not altas and not bajas:
        return pd.DataFrame(columns=["semana", "entradas", "salidas", "balance"])

    def _a_semana(fechas: list[date]) -> pd.Series:
        # W-FRI: la semana arranca sábado, no lunes — así coincide con el
        # cron semanal (sábados). Con el default de pandas (W, lunes a
        # domingo) una corrida de sábado caía en la misma semana que el
        # lunes anterior, y la barra quedaba con la fecha del lunes viejo
        # aunque tuviera datos de hoy adentro.
        periodos = pd.to_datetime(pd.Series(fechas)).dt.to_period("W-FRI")
        return periodos.apply(lambda p: p.start_time)

    entradas = _a_semana(altas).value_counts().rename("entradas")
    salidas = (
        _a_semana(bajas).value_counts().rename("salidas")
        if bajas
        else pd.Series(dtype=int, name="salidas")
    )

    df = pd.concat([entradas, salidas], axis=1).fillna(0).astype(int).sort_index()
    df["balance"] = df["entradas"] - df["salidas"]
    df = df.reset_index(names="semana")
    df["semana"] = df["semana"].dt.strftime("%d/%m")
    return df


def tipo_mercado(df_flujo: pd.DataFrame) -> str:
    """'Comprador' / 'Vendedor' / 'Equilibrado', según el balance de la
    última semana con datos."""
    if df_flujo.empty:
        return "Sin datos suficientes"
    balance = int(df_flujo.iloc[-1]["balance"])
    if balance > 3:
        return "Vendedor"
    if balance < -2:
        return "Comprador"
    return "Equilibrado"
