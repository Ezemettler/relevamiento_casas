"""Normalización de números sueltos: superficies, ambientes, antigüedad.

Todos comparten el mismo problema: un texto con una unidad o palabra pegada
("320 m²", "29 Años") del que hay que sacar el primer número.
"""

from __future__ import annotations

import re

_PATRON_NUMERO = re.compile(r"[\d]+(?:[.,]\d+)?")


def parsear_numero(texto: str | None) -> float | None:
    """'320 m²' -> 320.0 | '29 Años' -> 29.0 | '' o None -> None"""
    if not texto:
        return None
    match = _PATRON_NUMERO.search(texto)
    if not match:
        return None
    return float(match.group().replace(",", "."))


def parsear_entero(texto: str | None) -> int | None:
    """Como `parsear_numero`, pero trunca a entero (ambientes, antigüedad)."""
    numero = parsear_numero(texto)
    return int(numero) if numero is not None else None
