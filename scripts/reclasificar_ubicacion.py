"""Re-deriva barrio/localidad/categoria_zona de propiedades ya guardadas.

Uso puntual: cuando se corrige un bug en la normalización de ubicación (como
pasó con Sarro Pucheta el 2026-07-29, donde el separador " - " no alcanzaba),
el fix solo aplica a corridas futuras — `_actualizar_propiedad` nunca toca
estos campos en una propiedad que ya existe. Este script repara lo ya
guardado, sin volver a scrapear: usa el `payload_crudo` de la primera
observación de cada propiedad (el texto tal cual vino de la fuente, nunca
tocado) como entrada a la normalización ya corregida.

Uso: uv run python scripts/reclasificar_ubicacion.py "Sarro Pucheta"
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from relevamiento.config import cargar_yaml
from relevamiento.db import sesion
from relevamiento.modelos import Fuente, Observacion, Propiedad
from relevamiento.normalizacion.ubicacion import (
    clasificar_zona,
    parsear_direccion_con_barrio,
    parsear_tipo_ubicacion,
)


def _archivo_config_de(nombre_fuente: str) -> str:
    """Convención: 'Sarro Pucheta' -> 'sarro_pucheta.yaml'. Si no matchea
    ningún archivo real, `cargar_yaml` lanza un error claro más abajo."""
    return nombre_fuente.lower().replace(" ", "_") + ".yaml"


def main() -> int:
    if len(sys.argv) != 2:
        print('Uso: uv run python scripts/reclasificar_ubicacion.py "Nombre Fuente"')
        return 1

    nombre_fuente = sys.argv[1]
    config = cargar_yaml(f"fuentes/{_archivo_config_de(nombre_fuente)}")
    localidades_conocidas = config.get("localidades_conocidas", [])

    corregidas = 0
    sin_cambios = 0
    with sesion() as s:
        fuente = s.scalar(select(Fuente).where(Fuente.nombre == nombre_fuente))
        if fuente is None:
            print(f"No existe ninguna fuente llamada {nombre_fuente!r}.")
            return 1

        propiedades = s.scalars(
            select(Propiedad).where(Propiedad.fuente_id == fuente.id)
        ).all()

        for p in propiedades:
            primera_observacion = s.scalar(
                select(Observacion)
                .where(Observacion.propiedad_id == p.id)
                .order_by(Observacion.fecha.asc())
                .limit(1)
            )
            if primera_observacion is None:
                continue
            item_crudo = primera_observacion.payload_crudo.get("item", {})

            if item_crudo.get("tipologia_texto"):
                ubicacion = parsear_direccion_con_barrio(
                    item_crudo.get("direccion_texto"), localidades_conocidas
                )
            else:
                resultado = parsear_tipo_ubicacion(item_crudo.get("tipo_ubicacion_texto"))
                ubicacion = {
                    "direccion": item_crudo.get("direccion_texto"),
                    "barrio": resultado["barrio"],
                    "localidad": resultado["localidad"],
                }

            nueva_zona = clasificar_zona(
                ubicacion["localidad"], barrio=ubicacion["barrio"]
            )
            cambio = (
                p.direccion_texto != ubicacion["direccion"]
                or p.barrio != ubicacion["barrio"]
                or p.localidad != ubicacion["localidad"]
                or p.categoria_zona != nueva_zona
            )
            if cambio:
                p.direccion_texto = ubicacion["direccion"]
                p.barrio = ubicacion["barrio"]
                p.localidad = ubicacion["localidad"]
                p.categoria_zona = nueva_zona
                corregidas += 1
            else:
                sin_cambios += 1

    print(f"Corregidas: {corregidas} | sin cambios: {sin_cambios}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
