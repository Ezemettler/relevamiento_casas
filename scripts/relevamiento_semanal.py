"""Punto de entrada de la corrida semanal.

Esto es lo que ejecuta GitHub Actions cada lunes (y lo que se puede correr a
mano en cualquier momento). Recorre todas las fuentes declaradas en
config/fuentes/*.yaml y persiste los resultados.

Uso: uv run python scripts/relevamiento_semanal.py
"""

from __future__ import annotations

import sys

from relevamiento.config import DIR_CONFIG
from relevamiento.db import sesion
from relevamiento.pipeline.correr import ejecutar_corrida_real

DIR_FUENTES = DIR_CONFIG / "fuentes"


def main() -> int:
    # El guion bajo inicial marca un archivo de ejemplo/plantilla, no una
    # fuente real (ver config/fuentes/_ejemplo.yaml).
    archivos = sorted(
        p.name for p in DIR_FUENTES.glob("*.yaml") if not p.name.startswith("_")
    )
    if not archivos:
        print("No hay fuentes configuradas en config/fuentes/.")
        return 1

    hubo_error = False
    for archivo in archivos:
        print(f"\n=== {archivo} ===")
        try:
            # `with sesion()` hace commit solo si no hubo excepción; si algo
            # explota a mitad de camino, revierte todo — nunca queda una
            # corrida escrita a medias (regla 5 de CLAUDE.md).
            with sesion() as s:
                resultado = ejecutar_corrida_real(s, archivo)
        except Exception as exc:  # una fuente rota no debe tumbar a las demás
            print(f"ERROR inesperado: {exc}")
            hubo_error = True
            continue

        if resultado.abortada:
            print(f"ABORTADA: {resultado.motivo}")
            hubo_error = True
        else:
            c = resultado.corrida
            print(
                f"OK — nuevas={c.nuevas} actualizadas={c.actualizadas} "
                f"finalizadas={c.finalizadas}"
            )

    # Exit code distinto de cero: GitHub Actions marca la corrida como
    # fallida y la notifica, en vez de fallar en silencio.
    return 1 if hubo_error else 0


if __name__ == "__main__":
    sys.exit(main())
