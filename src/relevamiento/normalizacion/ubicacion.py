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


def parsear_direccion_con_barrio(
    texto: str | None,
    localidades_conocidas: list[str] | None = None,
    separador: str = " - ",
) -> dict[str, str | None]:
    """Separa un texto tipo 'Concordia al 900 - Haedo' en calle y barrio.

    Para fuentes que dan la tipología aparte (`ItemListado.tipologia_texto`)
    y combinan la dirección con el barrio en un solo campo, en vez de tres
    piezas como Tokko.

    El separador solo no alcanza: en Sarro Pucheta se comprobó que el mismo
    sitio escribe esto de forma inconsistente — "Concordia al 900 - Haedo"
    pero también "Rep.Oriental del Uruguay 800 Moron" (sin separador
    ninguno). Por eso primero se intenta reconocer el barrio por sufijo,
    contra una lista de localidades conocidas de la fuente (viene de su
    propio config/fuentes/*.yaml, no inventada acá); recién si eso no
    matchea se cae al separador. Si nada matchea, todo el texto queda como
    dirección — es preferible eso a adivinar.
    """
    vacio = {"direccion": None, "barrio": None, "localidad": None}
    if not texto:
        return vacio
    texto = texto.strip()

    # De más larga a más corta: "Ramos Mejía" tiene que probarse antes que
    # cualquier localidad de una sola palabra que sea substring suyo.
    for localidad in sorted(localidades_conocidas or [], key=len, reverse=True):
        if texto.lower().endswith(localidad.lower()):
            resto = texto[: -len(localidad)].rstrip(" -,")
            return {
                "direccion": resto or None,
                "barrio": localidad,
                "localidad": localidad,
            }

    partes = [p.strip() for p in texto.split(separador, maxsplit=1)]
    if len(partes) == 2:
        direccion, barrio = partes
    else:
        direccion, barrio = partes[0], None

    return {
        "direccion": direccion or None,
        "barrio": barrio,
        # Mismo criterio que parsear_tipo_ubicacion: sin un segundo nivel,
        # el barrio también hace de localidad para clasificar la zona.
        "localidad": barrio,
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


def nombre_legible_localidad(localidad: str | None) -> str | None:
    """'Moron' y 'Morón' -> 'Morón' — un solo nombre prolijo por localidad.

    Sin esto, agrupar por `Propiedad.localidad` cuenta la misma localidad
    dos veces cuando distintas fuentes la escriben con o sin tilde. Si no
    está en la tabla de alias (una localidad fuera de alcance, ej. "Merlo"),
    se devuelve el texto tal cual vino — no hay nada que unificar.
    """
    if not localidad:
        return localidad

    config = cargar_yaml("filtros.yaml")
    slug = config.get("alias_localidad", {}).get(_slug(localidad))
    if slug is None:
        return localidad
    return config.get("nombres_localidad", {}).get(slug, localidad)
