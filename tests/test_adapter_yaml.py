"""Tests del adapter contra HTML real de Carlos Fernández Prop. (fixtures
guardados en tests/fixtures/html/). No pegan a la web: corren siempre igual,
y si el sitio cambia de plantilla, estos son los que hay que actualizar
junto con el fixture.
"""

import itertools
from pathlib import Path

import pytest

from relevamiento.config import cargar_yaml
from relevamiento.scraping.adapter_yaml import (
    ConfigFuente,
    iterar_listado,
    obtener_detalle,
)

FIXTURES = Path(__file__).parent / "fixtures" / "html"


@pytest.fixture
def config():
    return ConfigFuente.desde_yaml(cargar_yaml("fuentes/carlos_fernandez.yaml"))


def _leer(nombre: str) -> str:
    return (FIXTURES / nombre).read_text(encoding="utf-8")


def test_iterar_listado_recorre_paginas_hasta_el_marcador(config):
    """Simula 3 llamadas de red con las páginas reales guardadas: la 1 y la 2
    con propiedades, la 3 con el marcador de fin. Debe traer 40 y frenar ahí,
    sin intentar una cuarta página.
    """
    paginas = [
        _leer("carlos_fernandez_listado_p1.html"),
        _leer("carlos_fernandez_listado_p2.html"),
        _leer("carlos_fernandez_listado_fin.html"),
    ]
    llamadas = []

    def descargar_falso(url: str) -> str:
        llamadas.append(url)
        return paginas[len(llamadas) - 1]

    items = list(iterar_listado(config, descargar_falso))

    assert len(items) == 40
    assert len(llamadas) == 3  # se detuvo al ver el marcador, no siguió


def test_item_de_listado_trae_los_campos_esperados(config):
    """El descargador falso devuelve siempre la misma página (no importa qué
    página se pida): alcanza para ver el primer ítem, así que se corta con
    `islice` en vez de agotar el generador, que nunca terminaría solo.
    """
    html = _leer("carlos_fernandez_listado_p1.html")
    items = list(itertools.islice(iterar_listado(config, lambda _url: html), 1))
    primero = items[0]

    assert primero.id_en_fuente == "8429785"
    assert primero.url.startswith("https://www.carlosfernandezprop.com.ar/p/8429785")
    # Espacios múltiples tal cual vienen en el HTML de origen: se limpian
    # recién en normalizacion.ubicacion.parsear_tipo_ubicacion, no acá.
    assert primero.tipo_ubicacion_texto == "Casa en Venta   en Castelar Norte, Castelar"
    assert primero.direccion_texto == "Cardoso 2949"
    assert "390.000" in primero.precio_texto


def test_iterar_listado_corta_si_la_primera_pagina_esta_vacia(config):
    """Si la fuente cambia de plantilla y el selector deja de matchear en la
    primera página, no debe reintentar para siempre.
    """
    items = list(iterar_listado(config, lambda _url: "<html><body>vacío</body></html>"))
    assert items == []


def test_obtener_detalle_trae_caracteristicas_mapeadas(config):
    html = _leer("carlos_fernandez_detalle.html")
    detalle = obtener_detalle("https://ejemplo.test/p/1", config, lambda _url: html)

    assert detalle.caracteristicas["ambientes"] == "5"
    assert detalle.caracteristicas["dormitorios"] == "4"
    assert detalle.caracteristicas["banos"] == "3"
    assert "29" in detalle.caracteristicas["antiguedad_anios"]
    assert "320" in detalle.caracteristicas["m2_terreno"]
    assert "320" in detalle.caracteristicas["m2_cubiertos"]
    assert detalle.descripcion is not None
    assert "5 ambientes" in detalle.descripcion
