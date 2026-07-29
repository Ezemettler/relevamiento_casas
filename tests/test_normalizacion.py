"""Tests de normalización, con los textos reales encontrados al inspeccionar
Carlos Fernández Prop. (ver PLAN.md sección 2.b). Si el sitio cambia el
formato, estos tests son los primeros en avisarlo.
"""

from relevamiento.modelos import CategoriaZona, Moneda
from relevamiento.normalizacion.precios import parsear_precio
from relevamiento.normalizacion.superficie import parsear_entero, parsear_numero
from relevamiento.normalizacion.ubicacion import clasificar_zona, parsear_tipo_ubicacion


def test_precio_usd_simple():
    assert parsear_precio("USD390.000") == (390000.0, Moneda.USD)


def test_precio_ignora_basura_pegada():
    """El HTML real trae el código de referencia y "Favorito" pegados."""
    texto = "USD390.000\n          \nCHO8429785\n+/- Favorito"
    assert parsear_precio(texto) == (390000.0, Moneda.USD)


def test_precio_con_espacio_y_simbolo_u_dolar_s():
    assert parsear_precio("U$S 54.000") == (54000.0, Moneda.USD)


def test_precio_pesos():
    assert parsear_precio("$ 12.500.000") == (12500000.0, Moneda.ARS)


def test_precio_con_decimales():
    assert parsear_precio("USD145.500,50") == (145500.5, Moneda.USD)


def test_precio_ausente():
    assert parsear_precio(None) is None
    assert parsear_precio("Consultar precio") is None


def test_superficie_con_unidad():
    assert parsear_numero("320 m²") == 320.0


def test_entero_con_palabra_pegada():
    assert parsear_entero("29 Años") == 29


def test_numero_ausente():
    assert parsear_numero("") is None
    assert parsear_numero(None) is None


def test_tipo_ubicacion_con_barrio_y_localidad():
    texto = "Casa en Venta   en Castelar Norte, Castelar"
    assert parsear_tipo_ubicacion(texto) == {
        "tipo_texto": "Casa",
        "barrio": "Castelar Norte",
        "localidad": "Castelar",
    }


def test_tipo_ubicacion_sin_coma_usa_barrio_como_localidad():
    texto = "PH en Venta en Morón"
    resultado = parsear_tipo_ubicacion(texto)
    assert resultado["barrio"] == "Morón"
    assert resultado["localidad"] == "Morón"


def test_tipo_ubicacion_vacia():
    assert parsear_tipo_ubicacion(None)["tipo_texto"] is None


def test_clasificar_zona_objetivo():
    assert clasificar_zona("Castelar") == CategoriaZona.OBJETIVO
    assert clasificar_zona("Morón") == CategoriaZona.OBJETIVO


def test_clasificar_zona_referencia():
    assert clasificar_zona("Ramos Mejía") == CategoriaZona.REFERENCIA


def test_clasificar_zona_usa_barrio_si_la_localidad_es_el_partido():
    """Carlos Fernández Prop. informa 'La Matanza' como localidad (el
    partido) y deja el nombre que clasifica la zona en el barrio."""
    resultado_ramos = clasificar_zona("La Matanza", barrio="Ramos Mejia")
    assert resultado_ramos == CategoriaZona.REFERENCIA
    resultado_ciudadela = clasificar_zona("Tres De Febrero", barrio="Ciudadela")
    assert resultado_ciudadela == CategoriaZona.REFERENCIA


def test_clasificar_zona_desconocida():
    assert clasificar_zona("Villa Desconocida") is None
    assert clasificar_zona("La Matanza", barrio="San Justo") is None


def test_clasificar_zona_vacia():
    assert clasificar_zona(None) is None
