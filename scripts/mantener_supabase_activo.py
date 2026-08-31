"""Ping mínimo a la base para que Supabase no la pause por inactividad.

El plan gratuito de Supabase pausa proyectos sin actividad de base de datos
por 7 días. Una corrida semanal cae justo en ese límite — cualquier
variación de horario puede hacer que el chequeo de Supabase caiga del lado
equivocado (pasó el 2026-08-29). Esto no scrapea nada ni toca ninguna
fuente: solo abre una conexión y hace una consulta trivial.

Uso: uv run python scripts/mantener_supabase_activo.py
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from relevamiento.db import sesion


def main() -> int:
    try:
        with sesion() as s:
            s.execute(select(1))
    except Exception as exc:
        print(f"ERROR: no se pudo conectar a la base: {exc}")
        return 1

    print("OK: conexión a Supabase confirmada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
