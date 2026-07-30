"""Confirma que la config de Sarro Pucheta resuelve bien contra HTML real.

A diferencia de Tokko: paginación tradicional sin marcador de fin (termina
cuando una página no trae tarjetas), tipología en un atributo aparte, y
dirección combinada con barrio en un solo campo.
"""

from pathlib import Path

from relevamiento.config import cargar_yaml
from relevamiento.normalizacion.superficie import extraer_ambientes_de_titulo
from relevamiento.normalizacion.ubicacion import parsear_direccion_con_barrio
from relevamiento.scraping.adapter_yaml import (
    ConfigFuente,
    iterar_listado,
    obtener_detalle,
)

FIXTURES = Path(__file__).parent / "fixtures" / "html"


def _leer(nombre: str) -> str:
    return (FIXTURES / nombre).read_text(encoding="utf-8")


def test_listado_recorre_paginas_hasta_que_una_no_trae_items():
    """Sin marcador_fin en el YAML: el corte es "página vacía", no un texto."""
    config = ConfigFuente.desde_yaml(cargar_yaml("fuentes/sarro_pucheta.yaml"))
    paginas = [
        _leer("sarro_pucheta_listado_p1.html"),
        _leer("sarro_pucheta_listado_p2.html"),
        _leer("sarro_pucheta_listado_fin.html"),  # 0 tarjetas, HTTP 200 normal
    ]
    llamadas = []

    def descargar_falso(url: str) -> str:
        llamadas.append(url)
        return paginas[len(llamadas) - 1]

    items = list(iterar_listado(config, descargar_falso))

    assert len(items) == 20  # 10 + 10, la tercera página cortó el bucle
    assert len(llamadas) == 3


def test_item_trae_tipologia_del_atributo_y_precio_del_data_price():
    config = ConfigFuente.desde_yaml(cargar_yaml("fuentes/sarro_pucheta.yaml"))
    html = _leer("sarro_pucheta_listado_p1.html")
    items = list(iterar_listado(config, lambda _url: html))
    primero = items[0]

    assert primero.id_en_fuente == "4683130"
    assert primero.tipologia_texto == "PH"
    assert primero.tipo_ubicacion_texto is None  # esta fuente no la usa
    assert "Concordia al 900" in primero.direccion_texto
    assert "54.000" in primero.precio_texto
    assert "ambientes" in primero.titulo_texto.lower()


_LOCALIDADES = ["Morón", "Moron", "Haedo", "Ramos Mejía", "Ramos Mejia"]


def test_direccion_con_guion_se_separa_en_calle_y_barrio():
    resultado = parsear_direccion_con_barrio("Concordia al 900 - Haedo", _LOCALIDADES)
    assert resultado == {
        "direccion": "Concordia al 900",
        "barrio": "Haedo",
        "localidad": "Haedo",
    }


def test_direccion_sin_separador_tambien_se_separa_por_localidad_conocida():
    """El caso real que rompía el parser viejo: mismo sitio, mismo campo,
    sin guión ni coma entre calle y barrio."""
    resultado = parsear_direccion_con_barrio(
        "Rep.Oriental del Uruguay 800 Moron", _LOCALIDADES
    )
    assert resultado["direccion"] == "Rep.Oriental del Uruguay 800"
    assert resultado["barrio"] == "Moron"


def test_direccion_con_localidad_de_dos_palabras():
    resultado = parsear_direccion_con_barrio(
        "Avellaneda al 500 Ramos Mejia", _LOCALIDADES
    )
    assert resultado["direccion"] == "Avellaneda al 500"
    assert resultado["barrio"] == "Ramos Mejia"


def test_direccion_sin_localidad_reconocible_no_inventa_barrio():
    resultado = parsear_direccion_con_barrio("Larguia 93", _LOCALIDADES)
    assert resultado == {"direccion": "Larguia 93", "barrio": None, "localidad": None}


def test_direccion_con_piso_y_guion_no_confunde_el_numero_de_depto():
    """'2°B' tiene un dígito adentro — no debe interpretarse como parte
    del corte de la localidad."""
    resultado = parsear_direccion_con_barrio(
        "Presidente Perón al 2700 2°B - Haedo", _LOCALIDADES
    )
    assert resultado["direccion"] == "Presidente Perón al 2700 2°B"
    assert resultado["barrio"] == "Haedo"


def test_detalle_trae_caracteristicas_mapeadas():
    config = ConfigFuente.desde_yaml(cargar_yaml("fuentes/sarro_pucheta.yaml"))
    html = _leer("sarro_pucheta_detalle.html")
    detalle = obtener_detalle("https://ejemplo.test/p/1", config, lambda _url: html)

    assert detalle.caracteristicas["dormitorios"] == "1"
    assert detalle.caracteristicas["banos"] == "1"
    assert "40" in detalle.caracteristicas["antiguedad_anios"]
    assert "43" in detalle.caracteristicas["m2_cubiertos"]
    # No se mapea "tipo", "orientación" ni "código": ver comentario en el YAML.
    assert "tipo" not in detalle.caracteristicas
    assert "orientacion" not in detalle.caracteristicas
    assert detalle.descripcion is not None
    assert "ph 2 ambientes" in detalle.descripcion.lower()


def test_ambientes_de_titulo_respalda_cuando_falta_en_el_detalle():
    """Sarro no publica 'ambientes' en la ficha — sin este respaldo, todo
    departamento de esta fuente quedaría afuera del relevamiento."""
    assert extraer_ambientes_de_titulo("Venta PH 2 ambientes con patio en Haedo Sur") == 2
    assert extraer_ambientes_de_titulo("Casa sin mención de ambientes") is None


def test_config_carga_las_localidades_conocidas_del_yaml():
    config = ConfigFuente.desde_yaml(cargar_yaml("fuentes/sarro_pucheta.yaml"))
    assert "Haedo" in config.localidades_conocidas
    assert "Ramos Mejía" in config.localidades_conocidas
