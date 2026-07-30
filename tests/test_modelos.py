"""Tests del modelo de datos.

No verifican que SQLAlchemy funcione (eso ya está probado): verifican que las
REGLAS DEL DOMINIO estén realmente garantizadas por la base. Si alguna de
estas falla, el sistema puede corromper el historial en silencio.

Corren contra SQLite en memoria: no necesitan Supabase ni conexión a internet.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from relevamiento.modelos import (
    Base,
    EstadoPropiedad,
    Evaluacion,
    Fuente,
    Propiedad,
    TipoFuente,
    Tipologia,
)

HOY = date(2026, 7, 28)


@pytest.fixture
def sesion():
    """Base vacía y descartable para cada test."""
    motor = create_engine("sqlite://")
    Base.metadata.create_all(motor)
    with Session(motor) as s:
        yield s


@pytest.fixture
def fuente(sesion):
    f = Fuente(
        nombre="Inmobiliaria de prueba",
        tipo=TipoFuente.INMOBILIARIA_LOCAL,
        url_base="https://ejemplo.com.ar",
    )
    sesion.add(f)
    sesion.commit()
    return f


def _propiedad(fuente, id_en_fuente="ABC-123", **extra):
    return Propiedad(
        fuente_id=fuente.id,
        id_en_fuente=id_en_fuente,
        url=f"https://ejemplo.com.ar/{id_en_fuente}",
        tipologia=Tipologia.CASA,
        fecha_primera_vista=HOY,
        fecha_ultima_vista=HOY,
        **extra,
    )


def test_se_crean_todas_las_tablas(sesion):
    """Las 7 tablas del PLAN existen y son coherentes entre sí."""
    tablas = set(Base.metadata.tables)
    assert tablas == {
        "fuentes",
        "propiedades",
        "corridas",
        "observaciones",
        "cambios",
        "evaluaciones",
        "evaluacion_criterios",
    }


def test_no_permite_dos_propiedades_con_la_misma_identidad(sesion, fuente):
    """Regla 3 de CLAUDE.md: identidad = (fuente_id, id_en_fuente).

    Es LA defensa contra duplicar registros semana a semana. Al estar en la
    base, ni siquiera un bug en el código de scraping puede saltearla.
    """
    sesion.add(_propiedad(fuente))
    sesion.commit()

    sesion.add(_propiedad(fuente))  # mismo aviso, segunda corrida
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_la_misma_id_en_fuentes_distintas_si_se_permite(sesion, fuente):
    """Dos inmobiliarias pueden usar el mismo código interno sin colisionar."""
    otra = Fuente(
        nombre="Otra inmobiliaria",
        tipo=TipoFuente.INMOBILIARIA_LOCAL,
        url_base="https://otra.com.ar",
    )
    sesion.add(otra)
    sesion.commit()

    sesion.add(_propiedad(fuente, "ABC-123"))
    sesion.add(_propiedad(otra, "ABC-123"))
    sesion.commit()  # no debe fallar

    assert sesion.query(Propiedad).count() == 2


def test_una_propiedad_nace_activa(sesion, fuente):
    p = _propiedad(fuente)
    sesion.add(p)
    sesion.commit()

    assert p.estado == EstadoPropiedad.ACTIVA
    assert p.fecha_finalizacion is None


def test_finalizar_no_borra_el_registro(sesion, fuente):
    """Regla 1 de CLAUDE.md: nunca borrar. Se marca finalizada con fecha."""
    p = _propiedad(fuente)
    sesion.add(p)
    sesion.commit()

    p.estado = EstadoPropiedad.FINALIZADA
    p.fecha_finalizacion = date(2026, 10, 2)
    sesion.commit()

    assert sesion.query(Propiedad).count() == 1
    # El historial de cuándo se vio por primera vez sigue intacto:
    # es lo que después permite calcular el tiempo en mercado.
    assert p.fecha_primera_vista == HOY


def test_la_evaluacion_humana_vive_aparte_de_la_propiedad(sesion, fuente):
    """Regla 2 de CLAUDE.md: el scraping nunca puede pisar lo que cargó el usuario.

    Se verifica actualizando la propiedad (como haría una corrida) y
    comprobando que la evaluación queda intacta.
    """
    p = _propiedad(fuente, precio_actual=95000)
    sesion.add(p)
    sesion.commit()

    sesion.add(
        Evaluacion(
            propiedad_id=p.id,
            fecha_visita=date(2026, 8, 10),
            humedad=True,
            notas="Humedad en el fondo, cerca del lavadero.",
        )
    )
    sesion.commit()

    # Simula lo que hace una corrida semanal: actualizar el precio.
    p.precio_actual = 89000
    p.fecha_ultima_vista = date(2026, 8, 17)
    sesion.commit()

    evaluacion = sesion.query(Evaluacion).one()
    assert evaluacion.humedad is True
    assert evaluacion.disponible is True  # por defecto, disponible
    assert evaluacion.notas.startswith("Humedad en el fondo")


def test_los_enums_guardan_el_valor_legible(sesion, fuente):
    """Al mirar la tabla en Supabase debe leerse 'casa', no 'CASA'."""
    from sqlalchemy import text

    sesion.add(_propiedad(fuente))
    sesion.commit()

    crudo = sesion.execute(text("SELECT tipologia FROM propiedades")).scalar_one()
    assert crudo == "casa"
