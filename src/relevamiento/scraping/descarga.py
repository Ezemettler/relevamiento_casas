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


def obtener(url: str, cliente: httpx.Client | None = None) -> str:
    """Descarga una URL respetando el rate limit configurado.

    Reintenta una vez ante errores de red transitorios (timeout, conexión
    rechazada); un segundo fallo se propaga para que la corrida lo registre
    como error de esa fuente en vez de fallar en silencio.
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
        for intento in range(2):
            try:
                respuesta = cliente.get(url, headers=headers)
                respuesta.raise_for_status()
                return respuesta.text
            except (httpx.TransportError, httpx.HTTPStatusError):
                if intento == 1:
                    raise
                time.sleep(2.0)
        raise AssertionError("inalcanzable")  # pragma: no cover
    finally:
        _ultima_request = time.monotonic()
        if propio:
            cliente.close()
