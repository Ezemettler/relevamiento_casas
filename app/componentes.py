"""Piezas de UI compartidas entre páginas — evita duplicar el mismo layout
en Mercado.py y en Propiedades.py."""

from __future__ import annotations

import streamlit as st
from datos import ultima_actualizacion


def encabezado(titulo: str) -> None:
    """Título de la página + cartel de "última actualización" arriba a la
    derecha — para saber de un vistazo qué tan al día están los datos."""
    col_titulo, col_actualizado = st.columns([4, 1])
    with col_titulo:
        st.title(titulo)
    with col_actualizado:
        momento = ultima_actualizacion()
        texto_momento = f"{momento:%d/%m %H:%M}" if momento else "sin corridas todavía"
        st.caption(f"🕒 Última actualización: **{texto_momento}**")
