"""Configuración del proyecto: variables de entorno y archivos YAML.

Dos fuentes de configuración, separadas a propósito:

    .env           -> secretos y cosas que cambian por máquina (credenciales)
    config/*.yaml  -> reglas del negocio que el usuario debe poder editar
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[2]
DIR_CONFIG = RAIZ / "config"


class Ajustes(BaseSettings):
    """Variables de entorno, validadas al arrancar.

    Si falta DATABASE_URL, el programa falla de entrada con un mensaje claro
    en vez de romperse a mitad de una corrida.
    """

    model_config = SettingsConfigDict(
        env_file=RAIZ / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str
    user_agent: str = "relevamiento-personal/0.1"
    # Segundos de espera entre requests. Ver CLAUDE.md: uso responsable.
    rate_limit_segundos: float = 2.5


@lru_cache
def ajustes() -> Ajustes:
    """Devuelve los ajustes, leyéndolos del entorno una sola vez."""
    return Ajustes()  # type: ignore[call-arg]


def cargar_yaml(nombre: str) -> dict[str, Any]:
    """Carga un archivo de `config/`. Ej: cargar_yaml('filtros.yaml')."""
    ruta = DIR_CONFIG / nombre
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo de configuración: {ruta}")
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
