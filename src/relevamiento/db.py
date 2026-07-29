"""Conexión a la base de datos.

El resto del código nunca crea su propia conexión: pide una sesión acá. Así,
si mañana cambia el motor o la forma de conectarse, se toca un solo archivo.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from relevamiento.config import ajustes

_motor = None
_crear_sesion: sessionmaker[Session] | None = None


def motor():
    """Crea el motor de conexión una sola vez y lo reutiliza."""
    global _motor, _crear_sesion
    if _motor is None:
        _motor = create_engine(
            ajustes().database_url,
            # Verifica que la conexión siga viva antes de usarla. Necesario
            # con bases gestionadas, que cierran conexiones ociosas.
            pool_pre_ping=True,
        )
        _crear_sesion = sessionmaker(bind=_motor, expire_on_commit=False)
    return _motor


@contextmanager
def sesion() -> Iterator[Session]:
    """Abre una sesión y garantiza commit al salir bien, rollback si falla.

    Uso:
        with sesion() as s:
            s.add(propiedad)

    El rollback automático es importante para la regla 5 de CLAUDE.md: si una
    fuente falla a mitad de camino, no queda escrita a medias.
    """
    motor()
    assert _crear_sesion is not None
    s = _crear_sesion()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
