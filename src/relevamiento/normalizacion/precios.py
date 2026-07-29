"""Normalización de precios.

El texto scrapeado suele traer basura pegada (código de referencia, botón de
favoritos) y usa el formato numérico argentino (punto de miles, coma
decimal). Esta función separa moneda y monto de forma tolerante a eso.
"""

from __future__ import annotations

import re

from relevamiento.modelos import Moneda

# Los signos de moneda argentinos son ambiguos si se buscan por separado
# ("$" solo podría matchear dentro de otra cosa): se buscan todos juntos,
# de más específico a menos, y se toma el primero que aparezca en el texto.
_PATRON_PRECIO = re.compile(
    r"(U\$S|US\$|USD|ARS|\$)\s?([\d][\d.,]*)",
    re.IGNORECASE,
)

_SIMBOLO_A_MONEDA = {
    "usd": Moneda.USD,
    "u$s": Moneda.USD,
    "us$": Moneda.USD,
    "ars": Moneda.ARS,
    "$": Moneda.ARS,
}


def parsear_precio(texto: str | None) -> tuple[float, Moneda] | None:
    """Extrae (monto, moneda) de un texto. None si no se encuentra ninguno.

    Ejemplos:
        "USD390.000"                          -> (390000.0, USD)
        "USD390.000\\nCHO8429785\\n+/- Favorito" -> (390000.0, USD)  (ignora la basura)
        "U$S 54.000"                          -> (54000.0, USD)
        "$ 12.500.000"                        -> (12500000.0, ARS)
    """
    if not texto:
        return None

    match = _PATRON_PRECIO.search(texto)
    if not match:
        return None

    simbolo, monto_texto = match.groups()
    moneda = _SIMBOLO_A_MONEDA[simbolo.lower()]
    return _parsear_monto(monto_texto), moneda


def _parsear_monto(texto: str) -> float:
    """'390.000' -> 390000.0 | '145.500,50' -> 145500.5

    Los precios de estas fuentes casi nunca llevan decimales, pero se
    soporta el formato por si alguna fuente lo usa (coma = decimal,
    punto = separador de miles, como es estándar en Argentina).
    """
    if "," in texto:
        return float(texto.replace(".", "").replace(",", "."))
    return float(texto.replace(".", ""))
