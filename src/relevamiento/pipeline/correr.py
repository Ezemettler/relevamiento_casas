"""Orquestador de una corrida real: conecta YAML + HTTP + base de datos.

`pipeline/persistir.py` no sabe nada de HTTP ni de YAML a propósito (así se
testea con datos armados a mano). Este módulo es el que arma todas las
piezas reales para una corrida efectiva contra un sitio y una base.
"""

from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from relevamiento.config import cargar_yaml
from relevamiento.modelos import Fuente
from relevamiento.pipeline.persistir import ResultadoCorrida, ejecutar_corrida
from relevamiento.scraping import descarga
from relevamiento.scraping.adapter_yaml import (
    ConfigFuente,
    iterar_listado,
    obtener_detalle,
)
from relevamiento.scraping.base import ItemListado


def obtener_o_crear_fuente(sesion: Session, config: ConfigFuente) -> Fuente:
    """Primera vez que corre una fuente, se registra en el catálogo. Después
    se reutiliza el mismo registro — nunca se crea uno duplicado."""
    existente = sesion.scalar(select(Fuente).where(Fuente.nombre == config.nombre))
    if existente:
        return existente

    fuente = Fuente(nombre=config.nombre, tipo=config.tipo, url_base=config.url_base)
    sesion.add(fuente)
    sesion.flush()
    return fuente


def ejecutar_corrida_real(sesion: Session, archivo_config: str) -> ResultadoCorrida:
    """Corre una fuente de punta a punta contra el sitio real.

    `archivo_config` es el nombre dentro de config/fuentes/, ej.
    "carlos_fernandez.yaml".
    """
    config = ConfigFuente.desde_yaml(cargar_yaml(f"fuentes/{archivo_config}"))
    fuente = obtener_o_crear_fuente(sesion, config)

    with httpx.Client(timeout=30.0, follow_redirects=True) as cliente:

        def descargar(url: str) -> str:
            return descarga.obtener(url, cliente=cliente)

        items = list(iterar_listado(config, descargar))

        def obtener_detalle_de(item: ItemListado):
            return obtener_detalle(item.url, config, descargar)

        return ejecutar_corrida(
            sesion,
            fuente,
            items,
            obtener_detalle_de,
            config.mapeo_tipologia,
        )
