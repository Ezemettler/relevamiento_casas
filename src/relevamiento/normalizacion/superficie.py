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


_PATRON_AMBIENTES_EN_TITULO = re.compile(r"(\d+)\s*amb", re.IGNORECASE)


def extraer_ambientes_de_titulo(texto: str | None) -> int | None:
    """'PH 2 ambientes con patio en Haedo Sur' -> 2

    Respaldo para cuando la ficha de detalle no publica "ambientes" como
    característica aparte (pasa en Sarro Pucheta) pero sí lo menciona en el
    título. Sin esto, cualquier departamento de esa fuente quedaría afuera
    del relevamiento — el filtro de 3+ ambientes trata "sin dato" como 0.
    """
    if not texto:
        return None
    match = _PATRON_AMBIENTES_EN_TITULO.search(texto)
    return int(match.group(1)) if match else None
