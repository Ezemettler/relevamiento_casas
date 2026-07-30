"""Mercado — pantalla principal: KPIs, flujo semanal y señales de negociación."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import altair as alt  # noqa: E402
import streamlit as st  # noqa: E402
from datos import (  # noqa: E402
    flujo_semanal,
    listado_propiedades,
    metricas_por_zona_y_tipologia,
    resumen_general,
    senales_negociacion_top,
    tipo_mercado,
)

st.set_page_config(page_title="Mercado", page_icon="🏠", layout="wide")
st.title("🏠 Mercado — Morón y alrededores")
st.caption("Relevamiento semanal de casas, PH y departamentos de 3+ ambientes.")

resumen = resumen_general()
df = listado_propiedades()
df_flujo = flujo_semanal()

# ── KPIs ──────────────────────────────────────────────────────────────────
con_bajadas = int((df["bajadas"] >= 2).sum()) if not df.empty else 0
precio_promedio = df["precio"].mean() if not df.empty else None
precio_m2_promedio = df["precio_m2"].mean() if not df.empty else None
balance_semana = int(df_flujo.iloc[-1]["balance"]) if not df_flujo.empty else None

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

# ── Precio/m² por zona y tipología ──────────────────────────────────────
st.subheader("Precio/m² por zona y tipología")
st.caption("La referencia para saber si un precio está caro o barato — no en abstracto.")
metricas = metricas_por_zona_y_tipologia()
if metricas.empty:
    st.info("Todavía no hay suficientes propiedades con precio y m² para calcular esto.")
else:
    st.dataframe(metricas, use_container_width=True, hide_index=True)

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
