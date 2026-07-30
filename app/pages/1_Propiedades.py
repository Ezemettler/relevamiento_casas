"""Listado de propiedades con panel de detalle al costado.

Seleccionar una fila no navega a otra página — el panel de la derecha se
actualiza en el lugar. "Modificar datos" tampoco navega: abre un modal
(`st.dialog`) encima de esta misma pantalla. No existe una página aparte
de "completar datos" — se decidió así explícitamente: cargar humedad,
orientación, etc. es una acción sobre una propiedad, no un destino propio
de la navegación.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402
from datos import (  # noqa: E402
    detalle_propiedad,
    filtros_configurados,
    guardar_o_actualizar_evaluacion,
    listado_propiedades,
)

from relevamiento.modelos import NivelLuz, NivelRuido, Orientacion  # noqa: E402

st.set_page_config(page_title="Propiedades", page_icon="📋", layout="wide")
st.title("📋 Propiedades")

config = filtros_configurados()
tipologias_disponibles = config.get("recoleccion", {}).get("tipologias", [])
precio_defecto = config.get("vista_por_defecto", {}).get("precio_maximo_usd")
zonas_defecto = config.get("vista_por_defecto", {}).get("categorias_zona", ["objetivo"])

_HUMEDAD_OPCIONES = {"Sin dato": None, "No": False, "Sí": True}


@st.dialog("Modificar datos de la propiedad")
def _modal_completar_datos(propiedad_id: int, etiqueta: str, actual: dict | None) -> None:
    st.caption(etiqueta)
    st.caption(
        "Lo que el scraping no puede sacar solo — mirando fotos del aviso o "
        "después de visitarla. Guardar reemplaza lo que hayas cargado antes."
    )

    disponible = st.checkbox(
        "Disponible para el análisis",
        value=actual["disponible"] if actual else True,
        help="Destildar para descartarla del listado y las métricas. El "
        "scraping le sigue registrando cambios de precio igual.",
    )

    opciones_luz = [None, *[n.value for n in NivelLuz]]
    indice_luz = (
        opciones_luz.index(actual["luz_natural"])
        if actual and actual.get("luz_natural") in opciones_luz
        else 0
    )
    luz_natural = st.selectbox(
        "Luz natural",
        options=opciones_luz,
        index=indice_luz,
        format_func=lambda v: v.capitalize() if v else "(sin especificar)",
    )

    humedad_actual = actual.get("humedad") if actual else None
    etiqueta_humedad = next(
        (k for k, v in _HUMEDAD_OPCIONES.items() if v == humedad_actual), "Sin dato"
    )
    humedad_texto = st.selectbox(
        "Humedad",
        options=list(_HUMEDAD_OPCIONES.keys()),
        index=list(_HUMEDAD_OPCIONES.keys()).index(etiqueta_humedad),
    )

    opciones_orientacion = [None, *[o.value for o in Orientacion]]
    indice_orientacion = (
        opciones_orientacion.index(actual["orientacion"])
        if actual and actual.get("orientacion") in opciones_orientacion
        else 0
    )
    orientacion = st.selectbox(
        "Orientación",
        options=opciones_orientacion,
        index=indice_orientacion,
        format_func=lambda v: v if v else "(sin especificar)",
    )

    opciones_ruido = [None, *[n.value for n in NivelRuido]]
    indice_ruido = (
        opciones_ruido.index(actual["ruido_entorno"])
        if actual and actual.get("ruido_entorno") in opciones_ruido
        else 0
    )
    ruido_entorno = st.selectbox(
        "Ruido del entorno",
        options=opciones_ruido,
        index=indice_ruido,
        format_func=lambda v: v.capitalize() if v else "(sin especificar)",
    )

    distancia_estacion_metros = st.number_input(
        "Distancia a la estación (metros)",
        min_value=0,
        step=50,
        value=int(actual["distancia_estacion_metros"])
        if actual and actual.get("distancia_estacion_metros")
        else 0,
    )

    entorno_defecto = actual["entorno"] if actual and actual.get("entorno") else ""
    entorno = st.text_area("Entorno (notas sobre la zona)", value=entorno_defecto)

    notas_defecto = actual["notas"] if actual and actual.get("notas") else ""
    notas = st.text_area("Notas libres", value=notas_defecto)

    if st.button("Guardar", type="primary", use_container_width=True):
        guardar_o_actualizar_evaluacion(
            propiedad_id,
            {
                "fecha_visita": date.today(),
                "disponible": disponible,
                "luz_natural": NivelLuz(luz_natural) if luz_natural else None,
                "humedad": _HUMEDAD_OPCIONES[humedad_texto],
                "orientacion": Orientacion(orientacion) if orientacion else None,
                "ruido_entorno": NivelRuido(ruido_entorno) if ruido_entorno else None,
                "distancia_estacion_metros": distancia_estacion_metros or None,
                "entorno": entorno or None,
                "notas": notas or None,
            },
        )
        st.rerun()


with st.sidebar:
    st.header("Filtros")
    tipologias = st.multiselect(
        "Tipología", options=tipologias_disponibles, default=tipologias_disponibles
    )
    categorias_zona = st.multiselect(
        "Zona", options=["objetivo", "referencia"], default=zonas_defecto
    )
    usar_techo_precio = st.checkbox(
        f"Solo hasta USD {precio_defecto:,.0f}".replace(",", "."), value=True
    )
    precio_maximo = precio_defecto if usar_techo_precio else None
    solo_disponibles = st.checkbox(
        "Solo disponibles",
        value=True,
        help="Oculta las que marcaste como descartadas. Se siguen "
        "registrando sus cambios de precio igual, solo no se muestran acá.",
    )

df = listado_propiedades(
    tipologias=tipologias or None,
    categorias_zona=categorias_zona or None,
    precio_maximo=precio_maximo,
    solo_disponibles=solo_disponibles,
)

_EMOJI_SENIAL = {"fuerte": "🔴 fuerte", "moderada": "🟡 moderada", "baja": ""}

col_lista, col_detalle = st.columns([2, 1])

with col_lista:
    st.caption(
        f"{len(df)} propiedades. Las que están fuera del techo de precio se "
        "siguen guardando — solo se ocultan acá por defecto, sirven como referencia."
    )

    if df.empty:
        st.info("Ninguna propiedad coincide con estos filtros.")
        propiedad_id = None
    else:
        orden = st.selectbox(
            "Ordenar por", ["precio_m2", "precio", "dias_en_mercado", "bajadas"]
        )
        df_mostrado = df.sort_values(orden, ascending=(orden != "bajadas")).copy()
        df_mostrado["señal"] = df_mostrado["senial"].map(_EMOJI_SENIAL)

        evento = st.dataframe(
            df_mostrado,
            use_container_width=True,
            hide_index=True,
            height=560,
            on_select="rerun",
            selection_mode="single-row",
            key="tabla_propiedades",
            column_config={
                "precio": st.column_config.NumberColumn("Precio", format="%.0f"),
                "precio_m2": st.column_config.NumberColumn("USD/m²", format="%.0f"),
            },
            column_order=[
                "señal",
                "tipologia",
                "direccion",
                "barrio",
                "zona",
                "precio",
                "moneda",
                "precio_m2",
                "tendencia",
                "ambientes",
                "m2_cubiertos",
                "antiguedad_anios",
                "dias_en_mercado",
            ],
        )

        filas_elegidas = evento.selection.rows
        propiedad_id = (
            int(df_mostrado.iloc[filas_elegidas[0]]["id"]) if filas_elegidas else None
        )

with col_detalle:
    if propiedad_id is None:
        st.info("Seleccioná una propiedad de la lista para ver el detalle.")
    else:
        datos = detalle_propiedad(propiedad_id)
        p = datos["propiedad"]
        etiqueta = f"{p['tipologia']} — {p['direccion']}, {p['barrio']}"

        st.subheader(f"{p['tipologia']} — {p['direccion']}")
        zona_texto = p["zona"] or "sin clasificar"
        st.caption(f"{p['barrio']}, {p['localidad']} · zona: {zona_texto}")
        if not p["disponible"]:
            st.warning("Descartada — no aparece en Mercado ni en el listado por defecto.")

        if p["precio"]:
            precio_texto = f"{p['moneda']} {p['precio']:,.0f}".replace(",", ".")
        else:
            precio_texto = "—"
        st.metric("Precio actual", precio_texto)

        c1, c2, c3 = st.columns(3)
        c1.metric("USD/m²", f"{p['precio_m2']:,.0f}" if p["precio_m2"] else "—")
        c2.metric("Días en mercado", p["dias_en_mercado"])
        c3.metric("Señal", p["senial"])

        st.write(
            f"Ambientes: {p['ambientes'] or '—'} · "
            f"Dormitorios: {p['dormitorios'] or '—'} · "
            f"Baños: {p['banos'] or '—'} · "
            f"m² cub.: {p['m2_cubiertos'] or '—'} · "
            f"Antigüedad: {p['antiguedad_anios'] or '—'} años"
        )

        st.link_button("Ver aviso original", p["url"], use_container_width=True)

        if st.button("📝 Modificar datos de esta propiedad", use_container_width=True):
            _modal_completar_datos(propiedad_id, etiqueta, datos["evaluacion"])

        if p.get("descripcion"):
            with st.expander("Descripción de la fuente"):
                st.write(p["descripcion"])

        st.divider()
        st.markdown("**Historial de cambios**")
        if not datos["cambios"]:
            st.caption("Todavía sin cambios registrados.")
        else:
            st.dataframe(datos["cambios"], use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("**Datos complementarios**")
        evaluacion = datos["evaluacion"]
        if not evaluacion:
            st.caption("Todavía no completaste los datos de esta propiedad.")
        else:
            st.dataframe([evaluacion], use_container_width=True, hide_index=True)
