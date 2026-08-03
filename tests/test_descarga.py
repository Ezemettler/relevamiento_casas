"""Tests del reintento en la descarga HTTP — sin red real, con un
transporte falso de httpx.

Nace de un fallo real: un 500 puntual de Marcelo Milano hizo fallar toda
la corrida del 2026-08-02 porque el único reintento (2s de espera) no
alcanzó — la misma URL ya respondía 200 pocos minutos después.
"""

from __future__ import annotations

import httpx
import pytest

from relevamiento.scraping import descarga


@pytest.fixture(autouse=True)
def _sin_espera(monkeypatch):
    """Evita que el rate limit real y el backoff entre reintentos hagan
    lentos los tests — acá se prueba CUÁNDO reintenta, no cuánto espera."""
    monkeypatch.setattr(descarga.time, "sleep", lambda _segundos: None)
    monkeypatch.setattr(descarga, "_ultima_request", 0.0)


def _cliente_con_respuestas(respuestas: list[httpx.Response]) -> httpx.Client:
    """Cliente de httpx que devuelve una respuesta distinta en cada request,
    en el orden dado — simula un servidor que falla y después se recupera."""
    iterador = iter(respuestas)

    def manejador(_request: httpx.Request) -> httpx.Response:
        return next(iterador)

    return httpx.Client(transport=httpx.MockTransport(manejador))


def test_reintenta_ante_500_y_se_recupera():
    cliente = _cliente_con_respuestas(
        [httpx.Response(500), httpx.Response(200, text="contenido real")]
    )
    assert descarga.obtener("https://ejemplo.test/pagina", cliente=cliente) == (
        "contenido real"
    )


def test_no_reintenta_ante_404():
    """Un 4xx no se arregla reintentando — se propaga de una."""
    cliente = _cliente_con_respuestas([httpx.Response(404)])
    with pytest.raises(httpx.HTTPStatusError):
        descarga.obtener("https://ejemplo.test/no-existe", cliente=cliente)


def test_propaga_si_el_500_persiste_mas_que_los_intentos():
    cliente = _cliente_con_respuestas([httpx.Response(500)] * 3)
    with pytest.raises(httpx.HTTPStatusError):
        descarga.obtener("https://ejemplo.test/pagina", cliente=cliente)
