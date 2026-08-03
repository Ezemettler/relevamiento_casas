"""Descarga HTTP con las reglas de uso responsable del proyecto.

Todo el tráfico de scraping pasa por acá: es el único lugar donde se aplica
el rate limit y el User-Agent, así ningún adapter puede saltearlos por
accidente.
"""

from __future__ import annotations

import time

import httpx

from relevamiento.config import ajustes

_ultima_request: float = 0.0

# 3 intentos con espera creciente (2s, 4s) — un solo reintento con 2s fijos
# no alcanzó para un 500 puntual de Marcelo Milano (ver corrida del
# 2026-08-02: falló dos veces seguidas y a los pocos minutos la misma URL
# ya respondía 200 de nuevo).
_MAX_INTENTOS = 3


def obtener(url: str, cliente: httpx.Client | None = None) -> str:
    """Descarga una URL respetando el rate limit configurado.

    Reintenta ante errores de red transitorios (timeout, conexión rechazada)
    y ante errores 5xx del servidor de la fuente, con espera creciente entre
    intentos. Los errores 4xx (recurso inexistente, acceso bloqueado) se
    propagan de inmediato: reintentarlos no cambia el resultado y solo
    quema tiempo. Si se agotan los intentos, el error se propaga para que
    la corrida lo registre como error de esa fuente en vez de fallar en
    silencio.
    """
    global _ultima_request

    espera = ajustes().rate_limit_segundos - (time.monotonic() - _ultima_request)
    if espera > 0:
        time.sleep(espera)

    headers = {"User-Agent": ajustes().user_agent}
    propio = cliente is None
    if propio:
        cliente = httpx.Client(timeout=30.0, follow_redirects=True)

    try:
        for intento in range(_MAX_INTENTOS):
            ultimo_intento = intento == _MAX_INTENTOS - 1
            try:
                respuesta = cliente.get(url, headers=headers)
                respuesta.raise_for_status()
                return respuesta.text
            except httpx.HTTPStatusError as error:
                if error.response.status_code < 500 or ultimo_intento:
                    raise
                time.sleep(2.0 * (intento + 1))
            except httpx.TransportError:
                if ultimo_intento:
                    raise
                time.sleep(2.0 * (intento + 1))
        raise AssertionError("inalcanzable")  # pragma: no cover
    finally:
        _ultima_request = time.monotonic()
        if propio:
            cliente.close()
