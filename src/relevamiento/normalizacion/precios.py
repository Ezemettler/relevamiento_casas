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
    """'390.000' -> 390000.0 | '145.500,50' -> 145500.5 | '254,000' -> 254000.0

    Por defecto la coma es decimal y el punto separador de miles (formato
    argentino). Pero si hay exactamente tres dígitos después de la coma, se
    la trata como separador de miles en formato inglés en vez de decimal:
    un precio de casa nunca tiene centavos, así que "254,000" son 254 mil
    dólares, no 254 con algo. Pasó de verdad con una propiedad de Sarro
    Pucheta que quedó guardada en USD 254 en vez de USD 254.000.
    """
    if "," in texto:
        parte_decimal = texto.rsplit(",", 1)[1]
        if len(parte_decimal) == 3:
            return float(texto.replace(".", "").replace(",", ""))
        return float(texto.replace(".", "").replace(",", "."))
    return float(texto.replace(".", ""))
