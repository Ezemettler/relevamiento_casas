"""Normalización de ubicación: separar el texto de la tarjeta y clasificar la zona.

Dos problemas distintos:

1. La fuente mezcla tipología, operación, barrio y localidad en un solo texto
   (ej. "Casa en Venta   en Castelar Norte, Castelar"). Hay que separarlos.
2. Una vez separada la localidad, hay que decidir si es zona objetivo,
   referencia o fuera de alcance — usando `config/filtros.yaml`, nunca un
   valor fijo en el código (ver PLAN.md sección 1.b).
"""

from __future__ import annotations

import re

from relevamiento.config import cargar_yaml
from relevamiento.modelos import CategoriaZona
from relevamiento.normalizacion.texto import quitar_acentos

# "Casa en Venta   en Castelar Norte, Castelar" (los espacios múltiples son
# reales en el HTML de origen: hay que tolerarlos, no son un error de tipeo).
_PATRON_TIPO_UBICACION = re.compile(
    r"^(?P<tipo>.+?)\s+en\s+(?:Venta|Alquiler)\s+en\s+(?P<barrio>[^,]+)(?:,\s*(?P<localidad>.+))?$",
    re.IGNORECASE,
)


def parsear_tipo_ubicacion(texto: str | None) -> dict[str, str | None]:
    """Separa el texto de la tarjeta en sus tres partes.

    Devuelve {"tipo_texto": ..., "barrio": ..., "localidad": ...}. Cualquier
    parte que no se pueda identificar queda en None: es preferible perder un
    dato a inventarlo.
    """
    vacio = {"tipo_texto": None, "barrio": None, "localidad": None}
    if not texto:
        return vacio

    normalizado = re.sub(r"\s+", " ", texto).strip()
    match = _PATRON_TIPO_UBICACION.match(normalizado)
    if not match:
        return vacio

    barrio = match.group("barrio").strip()
    localidad = match.group("localidad")
    return {
        "tipo_texto": match.group("tipo").strip(),
        "barrio": barrio,
        # Si no hay coma, la fuente solo dio una ubicación: se usa también
        # como localidad, porque es el dato que clasifica la zona.
        "localidad": localidad.strip() if localidad else barrio,
    }


def _slug(texto: str) -> str:
    """'Ramos Mejía' -> 'ramos mejia' (sin acentos, minúsculas)."""
    return quitar_acentos(texto).strip().lower()


def clasificar_zona(
    localidad: str | None, barrio: str | None = None
) -> CategoriaZona | None:
    """Clasifica una ubicación usando los alias y zonas de filtros.yaml.

    Se prueba primero `localidad` y, si no matchea, `barrio`. Hace falta
    porque algunas fuentes informan el partido en `localidad` (ej. "La
    Matanza") y dejan el nombre que realmente clasifica la zona en `barrio`
    (ej. "Ramos Mejía", que sí figura en nuestra tabla de zonas).

    None si ninguno de los dos matchea — se revisa a mano en vez de asumir
    una categoría.
    """
    config = cargar_yaml("filtros.yaml")
    alias = config.get("alias_localidad", {})
    zonas = config.get("zonas", {})

    normalizada = None
    for candidato in (localidad, barrio):
        if candidato:
            normalizada = alias.get(_slug(candidato))
            if normalizada is not None:
                break

    if normalizada is None:
        return None

    if normalizada in zonas.get("objetivo", []):
        return CategoriaZona.OBJETIVO
    if normalizada in zonas.get("referencia", []):
        return CategoriaZona.REFERENCIA
    return CategoriaZona.FUERA_DE_ALCANCE
