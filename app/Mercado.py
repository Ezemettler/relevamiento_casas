"""Mercado — pantalla principal: KPIs, flujo semanal y señales de negociación."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from componentes import encabezado  # noqa: E402
from datos import (  # noqa: E402
    flujo_semanal,
    listado_propiedades,
    precio_m2_por_localidad,
    resumen_general,
    senales_negociacion_top,
    tipo_mercado,
)

encabezado("🏠 Mercado — Morón y alrededores")
st.caption("Relevamiento semanal de casas, PH y departamentos de 3+ ambientes.")

resumen = resumen_general()
df = listado_propiedades()
df_flujo = flujo_semanal()

# ── KPIs ──────────────────────────────────────────────────────────────────
con_bajadas = int((df["bajadas"] >= 2).sum()) if not df.empty else 0
precio_promedio = df["precio"].mean() if not df.empty else None
precio_m2_promedio = df["precio_m2"].mean() if not df.empty else None
balance_semana = int(df_flujo.iloc[-1]["balance"]) if not df_flujo.empty else None

# Seis columnas angostas + valores largos ("USD 180.860") se cortaban con
# el tamaño de fuente por defecto de st.metric — se achica acá nada más,
# scopeado a este contenedor, sin tocar la tarjeta de detalle de Propiedades
# (que ya tiene su propio tamaño reducido, más chico todavía).
with st.container(key="kpis_mercado"):
    st.markdown(
        """
        <style>
        .st-key-kpis_mercado [data-testid="stMetricValue"] {
            font-size: 1.4rem;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Propiedades activas", resumen["activas"])
    col2.metric(
        "Precio promedio",
        f"USD {precio_promedio:,.0f}".replace(",", ".") if precio_promedio else "—",
    )
    col3.metric(
        "USD/m² promedio",
        f"{precio_m2_promedio:,.0f}".replace(",", ".") if precio_m2_promedio else "—",
    )
    col4.metric("Con 2+ bajadas", con_bajadas, help="Señal de necesidad de venta")
    col5.metric(
        "Balance esta semana",
        f"{balance_semana:+d}" if balance_semana is not None else "—",
        help="Entradas menos salidas",
    )
    col6.metric("Tipo de mercado", tipo_mercado(df_flujo))

st.divider()

# ── Flujo semanal ─────────────────────────────────────────────────────────
st.subheader("Flujo de mercado semanal")
st.caption(
    "Propiedades que entran vs. salen del mercado. Con pocas semanas de "
    "corridas esto se ve escaso todavía — se completa solo, corrida a corrida."
)
if df_flujo.empty:
    st.info("Todavía no hay datos de flujo.")
else:
    base = alt.Chart(df_flujo).encode(x=alt.X("semana:N", title=None, sort=None))
    barras = (
        base.transform_fold(["entradas", "salidas"], as_=["tipo", "cantidad"])
        .mark_bar()
        .encode(
            y=alt.Y("cantidad:Q", title="Propiedades"),
            color=alt.Color(
                "tipo:N",
                scale=alt.Scale(
                    domain=["entradas", "salidas"], range=["#4C78A8", "#E45756"]
                ),
                title=None,
            ),
            xOffset="tipo:N",
        )
    )
    linea = base.mark_line(color="#F2A007", point=True).encode(
        y=alt.Y("balance:Q", title=None)
    )
    st.altair_chart((barras + linea).properties(height=280), use_container_width=True)

st.divider()

# ── Precio/m² y stock por localidad ──────────────────────────────────────
st.subheader("Precio/m² y stock por localidad")
st.caption(
    "Comparar barrios entre sí, no solo la zona en bloque — azul es zona "
    "objetivo, gris son las de referencia."
)
precios_localidad = precio_m2_por_localidad()
if precios_localidad.empty:
    st.info("Todavía no hay suficientes propiedades con precio y m² para calcular esto.")
else:
    orden_localidades = precios_localidad["localidad"].tolist()
    escala_zona = alt.Scale(
        domain=["objetivo", "referencia"], range=["#4C78A8", "#B0B0B0"]
    )

    col_precio, col_stock = st.columns(2)

    # Una línea de referencia, no una barra más: si el promedio apareciera
    # como una barra al lado de las localidades, parecería "un barrio más"
    # en vez de una medida — con una línea punteada queda claro que es una
    # referencia, no un lugar.
    def _linea_promedio(valor: float, texto: str) -> alt.Chart:
        base = alt.Chart(pd.DataFrame({"y": [valor], "texto": [texto]}))
        linea = base.mark_rule(strokeDash=[4, 4], color="#F2A007").encode(y="y:Q")
        etiqueta = base.mark_text(align="left", dx=5, dy=-6, color="#F2A007").encode(
            y="y:Q", text="texto:N"
        )
        return linea + etiqueta

    with col_precio:
        st.caption("USD/m² promedio")
        chart_precio = (
            alt.Chart(precios_localidad)
            .mark_bar()
            .encode(
                x=alt.X("localidad:N", sort=orden_localidades, title=None),
                y=alt.Y("precio_m2_promedio:Q", title="USD/m²"),
                color=alt.Color("zona:N", scale=escala_zona, title=None),
                tooltip=["localidad", "precio_m2_promedio", "cantidad"],
            )
        )
        promedio_precio = precios_localidad["precio_m2_promedio"].mean()
        texto_promedio = f"Promedio: USD {promedio_precio:,.0f}".replace(",", ".")
        st.altair_chart(
            (chart_precio + _linea_promedio(promedio_precio, texto_promedio)).properties(
                height=280
            ),
            use_container_width=True,
        )

    with col_stock:
        st.caption("Cantidad de propiedades")
        chart_stock = (
            alt.Chart(precios_localidad)
            .mark_bar()
            .encode(
                x=alt.X("localidad:N", sort=orden_localidades, title=None),
                y=alt.Y("cantidad:Q", title="Propiedades"),
                color=alt.Color("zona:N", scale=escala_zona, title=None),
                tooltip=["localidad", "cantidad"],
            )
        )
        promedio_cantidad = precios_localidad["cantidad"].mean()
        texto_promedio_cantidad = f"Promedio: {promedio_cantidad:,.1f}".replace(",", ".")
        st.altair_chart(
            (
                chart_stock + _linea_promedio(promedio_cantidad, texto_promedio_cantidad)
            ).properties(height=280),
            use_container_width=True,
        )

st.divider()

# ── Señales de negociación ────────────────────────────────────────────────
st.subheader("Señales de negociación más fuertes")
señales = senales_negociacion_top()
if señales.empty:
    st.info("Ninguna propiedad tiene señal de negociación todavía.")
else:
    st.dataframe(
        señales,
        use_container_width=True,
        hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn("Aviso", display_text="Ver original"),
            "senial": st.column_config.TextColumn("Señal"),
            "tendencia": st.column_config.TextColumn("Tendencia"),
        },
        column_order=[
            "senial",
            "direccion",
            "barrio",
            "precio",
            "moneda",
            "tendencia",
            "dias_en_mercado",
            "url",
        ],
    )
