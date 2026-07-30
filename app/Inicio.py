"""Punto de entrada de la app: define la navegación y arranca la página.

Es el único lugar que llama a `st.set_page_config` — Streamlit solo permite
una vez por corrida. La navegación va arriba (`position="top"`) en vez de
en la barra lateral, para no perder ancho de pantalla: cada página sigue
pudiendo usar su propia barra lateral para filtros (ver Propiedades) sin
que compita con el menú de páginas.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Relevamiento de propiedades", page_icon="🏠", layout="wide"
)

# Streamlit no expone la navegación superior como algo configurable —
# `rc-overflow` y `stTopNavLink` son clases internas (inestables entre
# versiones), pero es lo único disponible para centrar y agrandar las
# solapas. Si una actualización de Streamlit las renombra, esto deja de
# tener efecto (no rompe nada, simplemente la navegación vuelve a verse
# como por defecto).
st.markdown(
    """
    <style>
    div.rc-overflow { justify-content: center !important; }
    [data-testid="stTopNavLink"] { font-size: 18px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

mercado = st.Page("Mercado.py", title="Mercado", icon="🏠", default=True)
propiedades = st.Page("pages/1_Propiedades.py", title="Propiedades", icon="📋")

pagina = st.navigation([mercado, propiedades], position="top")
pagina.run()
