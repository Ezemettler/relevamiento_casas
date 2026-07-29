"""Adapter guiado por config/fuentes/*.yaml para sitios sobre Tokkobroker.

Tokkobroker es un CMS muy usado por inmobiliarias argentinas: HTML servido
por el servidor (sin JavaScript de por medio) y paginación por scroll
infinito vía un parámetro de página en la misma URL. Confirmado en Carlos
Fernández Prop. y Marcelo Milano (ver PLAN.md sección 2.b).

Si una fuente nueva usa otra plataforma, este adapter no le sirve — hace
falta escribir uno distinto. Lo reutilizable entre fuentes Tokko es este
mismo archivo: para sumar Milano alcanza con un YAML nuevo, no con código.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from selectolax.parser import HTMLParser, Node

from relevamiento.normalizacion.texto import quitar_acentos
from relevamiento.scraping.base import DetalleCrudo, ItemListado

# El llamador decide cómo descargar (rate limit, reintentos): este módulo
# solo sabe parsear. Ver `scraping/descarga.py`.
DescargarFn = Callable[[str], str]


@dataclass
class ConfigFuente:
    nombre: str
    tipo: str
    url_base: str
    listado: dict[str, Any]
    detalle: dict[str, Any]
    mapeo_tipologia: dict[str, str]

    @classmethod
    def desde_yaml(cls, datos: dict[str, Any]) -> ConfigFuente:
        return cls(
            nombre=datos["nombre"],
            tipo=datos["tipo"],
            url_base=datos["url_base"],
            listado=datos["listado"],
            detalle=datos["detalle"],
            mapeo_tipologia=datos.get("mapeo_tipologia", {}),
        )


def _extraer_campo(nodo: Node, definicion: dict[str, Any]) -> str | None:
    """Aplica una definición de campo del YAML (selector + atributo opcional)."""
    selector = definicion.get("selector")
    objetivo = nodo.css_first(selector) if selector else nodo
    if objetivo is None:
        return None

    atributo = definicion.get("atributo")
    if atributo:
        return objetivo.attributes.get(atributo)

    # deep=True: junta el texto de los hijos también. Hace falta porque
    # varias tarjetas anidan divs (precio + código de referencia + botón de
    # favoritos); la normalización de precio se encarga de filtrar el resto.
    texto = objetivo.text(deep=True, separator=" ", strip=True)
    return texto or None


def iterar_listado(config: ConfigFuente, descargar: DescargarFn) -> Iterator[ItemListado]:
    """Recorre todas las páginas del listado hasta el marcador de fin.

    La descarga de cada página la hace `descargar` (inyectada): así el
    llamador controla el rate limit y puede contar páginas para la
    verificación de salud (regla 5 de CLAUDE.md) sin que este módulo lo sepa.
    """
    pagina = config.listado["primera_pagina"]
    marcador_fin = config.listado["marcador_fin"]
    # Sin este tope, un cambio de plantilla que rompa la detección del fin
    # de paginación dejaría el bucle pidiendo páginas para siempre.
    max_paginas = config.listado.get("max_paginas", 100)

    while pagina < config.listado["primera_pagina"] + max_paginas:
        url = config.url_base + config.listado["url"].format(pagina=pagina)
        html = descargar(url)
        # El marcador real es una respuesta CORTA que es solo eso (así
        # contesta el fin del scroll infinito). No alcanza con buscarlo con
        # "in": la página 1 completa lo menciona dentro de su propio
        # JavaScript (el código que define esta misma condición de corte),
        # así que ese chequeo daba un falso positivo en la primera página.
        if html.strip() == marcador_fin:
            return

        nodos = HTMLParser(html).css(config.listado["item"])
        if not nodos:
            return

        for nodo in nodos:
            yield _parsear_item(nodo, config)

        pagina += 1


def _parsear_item(nodo: Node, config: ConfigFuente) -> ItemListado:
    campos = config.listado["campos"]
    id_en_fuente = _extraer_campo(nodo, campos["id_en_fuente"])
    url_relativa = _extraer_campo(nodo, campos["url"])
    return ItemListado(
        id_en_fuente=id_en_fuente or "",
        url=urljoin(config.url_base, url_relativa) if url_relativa else config.url_base,
        tipo_ubicacion_texto=_extraer_campo(nodo, campos["tipo_ubicacion_texto"]),
        direccion_texto=_extraer_campo(nodo, campos["direccion_texto"]),
        precio_texto=_extraer_campo(nodo, campos["precio_texto"]),
    )


def obtener_detalle(
    url: str, config: ConfigFuente, descargar: DescargarFn
) -> DetalleCrudo:
    """Descarga y parsea la ficha de una propiedad.

    Las características vienen como pares "Etiqueta : Valor" repartidos en
    varias listas (`listas_caracteristicas`). Se traduce cada etiqueta a
    nuestro nombre de campo usando `mapeo_caracteristicas`: lo que no está
    en el mapeo se ignora, no se guarda con el nombre crudo de la fuente.
    """
    html = descargar(url)
    arbol = HTMLParser(html)

    mapeo = config.detalle["mapeo_caracteristicas"]
    caracteristicas: dict[str, str] = {}
    for selector in config.detalle["listas_caracteristicas"]:
        for li in arbol.css(selector):
            texto = li.text(deep=True, separator=" ", strip=True)
            if ":" not in texto:
                continue
            etiqueta, _, valor = texto.partition(":")
            etiqueta_normalizada = quitar_acentos(etiqueta).strip().lower()
            campo = mapeo.get(etiqueta_normalizada)
            if campo:
                caracteristicas[campo] = valor.strip()

    descripcion_def = config.detalle.get("descripcion")
    descripcion = _extraer_campo(arbol, descripcion_def) if descripcion_def else None

    return DetalleCrudo(caracteristicas=caracteristicas, descripcion=descripcion)
