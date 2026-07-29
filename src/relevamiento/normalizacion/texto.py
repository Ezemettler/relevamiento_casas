"""Utilidades de texto compartidas por el resto de `normalizacion/`."""

from __future__ import annotations

import unicodedata


def quitar_acentos(texto: str) -> str:
    """'Baños' -> 'Banos'. Sirve para comparar etiquetas sin depender de
    que la fuente escriba los acentos de forma consistente."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
