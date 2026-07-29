"""Estructuras de datos crudas del scraping.

'Crudo' quiere decir: tal como se leyó del HTML, sin normalizar todavía.
Por ejemplo `precio_texto` puede valer "USD390.000\\nCHO8429785\\n+/- Favorito"
(con basura pegada) — recién se limpia en la capa de `normalizacion/`.

Separar esto de los modelos de SQLAlchemy es deliberado: lo que se scrapea
puede no alcanzar para llenar una fila de `propiedades` sin antes normalizar
y, en algunos campos, sin visitar además la ficha de detalle.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ItemListado:
    """Un ítem tal como aparece en la página de listado (una tarjeta)."""

    id_en_fuente: str
    url: str
    tipo_ubicacion_texto: str | None = None
    direccion_texto: str | None = None
    precio_texto: str | None = None


@dataclass
class DetalleCrudo:
    """Lo extraído de la ficha de una propiedad.

    `caracteristicas` guarda pares etiqueta->valor tal como los escribió la
    fuente (ej. {"ambientes": "5", "antigüedad": "29 Años"}), sin normalizar
    ni traducir todavía. El adapter YAML se encarga de mapear esas etiquetas
    a los campos de nuestro modelo, usando `mapeo_caracteristicas`.
    """

    caracteristicas: dict[str, str] = field(default_factory=dict)
    descripcion: str | None = None
