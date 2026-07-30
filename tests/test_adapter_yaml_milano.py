"""Confirma que la config de Marcelo Milano resuelve bien contra HTML real.

La lógica del adapter ya está probada a fondo en test_adapter_yaml.py — acá
solo se valida que ESTE YAML en particular (selectores, mapeos) funcione
contra los fixtures de esta fuente. Si algún día el sitio cambia de
plantilla, este test es el primero en avisarlo.
"""

from pathlib import Path

from relevamiento.config import cargar_yaml
from relevamiento.scraping.adapter_yaml import (
    ConfigFuente,
    iterar_listado,
    obtener_detalle,
)

FIXTURES = Path(__file__).parent / "fixtures" / "html"


def _leer(nombre: str) -> str:
    return (FIXTURES / nombre).read_text(encoding="utf-8")


def test_listado_de_milano_recorre_paginas_hasta_el_marcador():
    config = ConfigFuente.desde_yaml(cargar_yaml("fuentes/marcelo_milano.yaml"))
    paginas = [
        _leer("marcelo_milano_listado_p1.html"),
        _leer("marcelo_milano_listado_p2.html"),
        _leer("marcelo_milano_listado_fin.html"),
    ]
    llamadas = []

    def descargar_falso(url: str) -> str:
        llamadas.append(url)
        return paginas[len(llamadas) - 1]

    items = list(iterar_listado(config, descargar_falso))

    assert len(items) == 40
    assert len(llamadas) == 3
    assert items[0].id_en_fuente == "8560513"
    # es otra fuente, no la de Carlos Fernández
    assert "390.000" not in items[0].precio_texto


def test_detalle_de_milano_trae_caracteristicas_mapeadas():
    config = ConfigFuente.desde_yaml(cargar_yaml("fuentes/marcelo_milano.yaml"))
    html = _leer("marcelo_milano_detalle.html")
    detalle = obtener_detalle("https://ejemplo.test/p/1", config, lambda _url: html)

    assert detalle.caracteristicas["ambientes"] == "6"
    assert detalle.caracteristicas["dormitorios"] == "5"
    assert detalle.caracteristicas["banos"] == "5"


def test_detalle_de_milano_limpia_html_crudo_de_la_descripcion():
    """Milano deja "<div><br></div>" y similares como texto literal en la
    descripción — no es un error de nuestro parseo, viene así en el campo
    de origen. Confirma que se limpia antes de guardar."""
    config = ConfigFuente.desde_yaml(cargar_yaml("fuentes/marcelo_milano.yaml"))
    html = _leer("marcelo_milano_detalle.html")
    detalle = obtener_detalle("https://ejemplo.test/p/1", config, lambda _url: html)

    assert "<div>" not in detalle.descripcion
    assert "<br>" not in detalle.descripcion
    assert "Residencia exclusiva en Casco de Leloir" in detalle.descripcion
