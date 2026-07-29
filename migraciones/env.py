"""Configuración de Alembic.

Alembic compara los modelos de `modelos.py` contra el estado real de la base y
genera automáticamente el SQL para llevarla de uno al otro. Es lo que permite
cambiar el esquema sin perder datos ni tocar tablas a mano en Supabase.

Este archivo está modificado respecto del que genera Alembic por defecto en dos
puntos:
  1. La URL sale del .env (vía nuestra config), no de alembic.ini. Así la
     credencial vive en un solo lugar y nunca se commitea por accidente.
  2. `target_metadata` apunta a nuestros modelos, para poder autogenerar.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from relevamiento.config import ajustes
from relevamiento.modelos import Base

config = context.config

# La credencial se inyecta acá en tiempo de ejecución, desde el .env.
config.set_main_option("sqlalchemy.url", ajustes().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic compara esto contra la base real para detectar diferencias.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse a la base."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Se conecta a la base y aplica las migraciones."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Detecta también cambios de TIPO de una columna, no solo que la
            # columna exista. Sin esto pasan cambios desapercibidos.
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
