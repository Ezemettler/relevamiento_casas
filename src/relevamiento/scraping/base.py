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
    """Un ítem tal como aparece en la página de listado (una tarjeta).

    Dos formas de dar la tipología, según la fuente:
      - `tipo_ubicacion_texto`: texto combinado "Casa en Venta en Barrio,
        Localidad" (Tokko) — se separa con `parsear_tipo_ubicacion`.
      - `tipologia_texto`: la tipología ya viene sola (ej. un atributo
        `data-type="PH"`) — en ese caso `direccion_texto` se interpreta
        como "calle - barrio" y se separa con `parsear_direccion_con_barrio`.

    El pipeline decide cuál de las dos formas está en juego mirando si
    `tipologia_texto` viene con algo.
    """

    id_en_fuente: str
    url: str
    tipo_ubicacion_texto: str | None = None
    tipologia_texto: str | None = None
    direccion_texto: str | None = None
    precio_texto: str | None = None
    # Título del aviso. Sirve como respaldo para extraer datos que faltan
    # en los campos estructurados (ej. "ambientes" cuando la fuente no lo
    # publica como característica aparte, solo lo menciona en el título).
    titulo_texto: str | None = None


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
