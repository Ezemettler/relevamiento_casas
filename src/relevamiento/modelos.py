"""Modelo de datos del sistema.

Define las tablas con SQLAlchemy. La estructura sigue la sección 4 del PLAN.md,
y la idea central es separar tres cosas que suelen mezclarse mal:

    propiedades    -> qué es la propiedad (un registro por propiedad, para siempre)
    observaciones  -> qué vio el sistema en cada corrida (memoria bruta)
    evaluaciones   -> qué evaluó el usuario (nunca lo toca el scraping)

Esa separación es lo que garantiza que un re-scrapeo no pise el trabajo manual
ni destruya el historial.
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Clase base de la que heredan todas las tablas."""


# En Postgres usa JSONB (más rápido e indexable); en cualquier otro motor cae
# a JSON genérico. Sirve para que los tests corran contra SQLite en memoria,
# sin depender de que Supabase esté disponible.
Json = JSON().with_variant(JSONB(), "postgresql")


def _enum(clase: type[enum.Enum], nombre: str) -> Enum:
    """Columna de tipo enum que guarda el VALOR y no el NOMBRE del miembro.

    Por defecto SQLAlchemy guardaría 'CASA'; con esto guarda 'casa'. Importa
    porque es lo que se lee al mirar la tabla directamente en Supabase.
    """
    return Enum(clase, name=nombre, values_callable=lambda c: [m.value for m in c])


# --------------------------------------------------------------------------
# Enums
#
# Un Enum restringe una columna a un conjunto cerrado de valores. Es preferible
# a un texto libre porque la base rechaza cualquier valor no previsto: si el
# parseo devuelve basura, falla al insertar en vez de contaminar el historial.
# --------------------------------------------------------------------------


class TipoFuente(enum.StrEnum):
    INMOBILIARIA_LOCAL = "inmobiliaria_local"
    PORTAL = "portal"
    BANCO = "banco"


class Tipologia(enum.StrEnum):
    CASA = "casa"
    PH = "ph"
    DEPARTAMENTO = "departamento"
    OTRO = "otro"  # lo que no encaja; se revisa a mano en vez de descartarse


class Moneda(enum.StrEnum):
    USD = "USD"
    ARS = "ARS"


class EstadoPropiedad(enum.StrEnum):
    ACTIVA = "activa"
    FINALIZADA = "finalizada"


class CategoriaZona(enum.StrEnum):
    """Ver PLAN.md sección 1.b. La zona no filtra: clasifica."""

    OBJETIVO = "objetivo"  # partido de Morón; es lo que se ve en el listado
    REFERENCIA = "referencia"  # vecinas; no se listan pero sí se comparan
    FUERA_DE_ALCANCE = "fuera_de_alcance"


class TipoCambio(enum.StrEnum):
    PRECIO = "precio"
    ESTADO = "estado"
    ATRIBUTO = "atributo"
    REACTIVACION = "reactivacion"  # volvió a aparecer: NO se había vendido


class EstadoCorrida(enum.StrEnum):
    OK = "ok"
    PARCIAL = "parcial"  # alguna fuente falló, las demás se persistieron
    ERROR = "error"


class ResultadoCriterio(enum.StrEnum):
    OK = "ok"
    ATENCION = "atencion"
    ALERTA = "alerta"
    SIN_DATOS = "sin_datos"  # requiere criterio humano -> va al formulario


class NivelHumedad(enum.StrEnum):
    NO_DETECTADA = "no_detectada"
    LEVE = "leve"
    IMPORTANTE = "importante"


class Orientacion(enum.StrEnum):
    N = "N"
    NE = "NE"
    E = "E"
    SE = "SE"
    S = "S"
    SO = "SO"
    O = "O"  # noqa: E741 -- es el punto cardinal Oeste, no la letra suelta
    NO = "NO"


# --------------------------------------------------------------------------
# Tablas
# --------------------------------------------------------------------------


class Fuente(Base):
    """Catálogo de sitios relevados."""

    __tablename__ = "fuentes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)
    tipo: Mapped[TipoFuente] = mapped_column(_enum(TipoFuente, "tipo_fuente"))
    url_base: Mapped[str] = mapped_column(String(300))
    # Permite pausar una fuente rota sin borrarla ni perder su historial.
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

    propiedades: Mapped[list[Propiedad]] = relationship(back_populates="fuente")


class Propiedad(Base):
    """Un registro por propiedad, para siempre.

    Es la tabla que se mira. `precio_inicial` y `precio_actual` se mantienen
    acá por comodidad de consulta, pero la fuente de verdad del historial son
    las tablas `observaciones` y `cambios`.
    """

    __tablename__ = "propiedades"
    __table_args__ = (
        # LA regla que evita duplicados: una propiedad es única por
        # (fuente, id del aviso en esa fuente). Si ya existe, se actualiza.
        # Al estar declarada en la base, es imposible violarla por error de código.
        UniqueConstraint("fuente_id", "id_en_fuente", name="uq_propiedad_identidad"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fuente_id: Mapped[int] = mapped_column(ForeignKey("fuentes.id"))
    id_en_fuente: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(600))

    # --- Atributos objetivos (los extrae el scraping) ---
    tipologia: Mapped[Tipologia | None] = mapped_column(_enum(Tipologia, "tipologia"))
    ambientes: Mapped[int | None]
    dormitorios: Mapped[int | None]
    banos: Mapped[int | None]
    m2_cubiertos: Mapped[float | None] = mapped_column(Numeric(10, 2))
    m2_totales: Mapped[float | None] = mapped_column(Numeric(10, 2))
    m2_terreno: Mapped[float | None] = mapped_column(Numeric(10, 2))
    antiguedad_anios: Mapped[int | None]

    # --- Ubicación ---
    direccion_texto: Mapped[str | None] = mapped_column(String(300))
    barrio: Mapped[str | None] = mapped_column(String(120))
    localidad: Mapped[str | None] = mapped_column(String(120))
    # Se completa normalizando `localidad` contra los alias de config/filtros.yaml
    categoria_zona: Mapped[CategoriaZona | None] = mapped_column(
        _enum(CategoriaZona, "categoria_zona")
    )
    lat: Mapped[float | None] = mapped_column(Numeric(10, 7))
    lon: Mapped[float | None] = mapped_column(Numeric(10, 7))

    # --- Precio ---
    precio_inicial: Mapped[float | None] = mapped_column(Numeric(14, 2))
    moneda_inicial: Mapped[Moneda | None] = mapped_column(_enum(Moneda, "moneda_inicial"))
    precio_actual: Mapped[float | None] = mapped_column(Numeric(14, 2))
    moneda_actual: Mapped[Moneda | None] = mapped_column(_enum(Moneda, "moneda_actual"))
    expensas: Mapped[float | None] = mapped_column(Numeric(12, 2))

    titulo: Mapped[str | None] = mapped_column(String(400))
    descripcion: Mapped[str | None] = mapped_column(Text)

    # --- Ciclo de vida ---
    estado: Mapped[EstadoPropiedad] = mapped_column(
        _enum(EstadoPropiedad, "estado_propiedad"),
        default=EstadoPropiedad.ACTIVA,
    )
    fecha_primera_vista: Mapped[date] = mapped_column(Date)
    fecha_ultima_vista: Mapped[date] = mapped_column(Date)
    # Se completa cuando el aviso deja de aparecer. NUNCA se borra el registro.
    fecha_finalizacion: Mapped[date | None] = mapped_column(Date)

    # Previsto para la unificación entre fuentes (decisión D9, pospuesta).
    posible_duplicado_de: Mapped[int | None] = mapped_column(ForeignKey("propiedades.id"))

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    fuente: Mapped[Fuente] = relationship(back_populates="propiedades")
    observaciones: Mapped[list[Observacion]] = relationship(
        back_populates="propiedad", cascade="all, delete-orphan"
    )
    cambios: Mapped[list[Cambio]] = relationship(back_populates="propiedad")
    evaluaciones: Mapped[list[Evaluacion]] = relationship(back_populates="propiedad")


class Corrida(Base):
    """Trazabilidad de cada ejecución semanal."""

    __tablename__ = "corridas"

    id: Mapped[int] = mapped_column(primary_key=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[EstadoCorrida] = mapped_column(_enum(EstadoCorrida, "estado_corrida"))
    nuevas: Mapped[int] = mapped_column(Integer, default=0)
    actualizadas: Mapped[int] = mapped_column(Integer, default=0)
    finalizadas: Mapped[int] = mapped_column(Integer, default=0)
    reactivadas: Mapped[int] = mapped_column(Integer, default=0)
    # Detalle de errores por fuente; sirve para diagnosticar sin abrir logs.
    errores: Mapped[dict | None] = mapped_column(Json)


class Observacion(Base):
    """Lo que el sistema vio de una propiedad en una corrida.

    Es la memoria bruta del sistema: no se consulta a diario, pero es lo que
    permite reconstruir el historial y reprocesarlo si mejora el parseo.
    """

    __tablename__ = "observaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    propiedad_id: Mapped[int] = mapped_column(ForeignKey("propiedades.id"))
    corrida_id: Mapped[int] = mapped_column(ForeignKey("corridas.id"))
    fecha: Mapped[date] = mapped_column(Date)

    precio: Mapped[float | None] = mapped_column(Numeric(14, 2))
    moneda: Mapped[Moneda | None] = mapped_column(_enum(Moneda, "moneda_obs"))
    visible: Mapped[bool] = mapped_column(Boolean, default=True)

    # Todo lo scrapeado tal cual, sin normalizar. Regla 4 de CLAUDE.md:
    # los avisos viejos desaparecen de la web, así que si no se guarda el
    # crudo no hay forma de reprocesar el histórico más adelante.
    payload_crudo: Mapped[dict | None] = mapped_column(Json)
    # Hash del contenido: detecta si algo cambió sin comparar campo por campo.
    hash_contenido: Mapped[str | None] = mapped_column(String(64))

    propiedad: Mapped[Propiedad] = relationship(back_populates="observaciones")


class Cambio(Base):
    """Historial de cambios, derivado de comparar observaciones consecutivas.

    Es lo que permite ver 'bajó tres veces en seis meses', que es la señal de
    negociación más valiosa del sistema.
    """

    __tablename__ = "cambios"

    id: Mapped[int] = mapped_column(primary_key=True)
    propiedad_id: Mapped[int] = mapped_column(ForeignKey("propiedades.id"))
    fecha: Mapped[date] = mapped_column(Date)
    tipo: Mapped[TipoCambio] = mapped_column(_enum(TipoCambio, "tipo_cambio"))
    campo: Mapped[str] = mapped_column(String(60))
    valor_anterior: Mapped[str | None] = mapped_column(String(300))
    valor_nuevo: Mapped[str | None] = mapped_column(String(300))
    variacion_pct: Mapped[float | None] = mapped_column(Numeric(8, 3))

    propiedad: Mapped[Propiedad] = relationship(back_populates="cambios")


class Evaluacion(Base):
    """Evaluación humana de una visita.

    Regla 2 de CLAUDE.md: el scraping NUNCA escribe acá. Está en una tabla
    aparte justamente para que ningún re-scrapeo pueda pisarla.
    """

    __tablename__ = "evaluaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    propiedad_id: Mapped[int] = mapped_column(ForeignKey("propiedades.id"))
    fecha_visita: Mapped[date] = mapped_column(Date)

    luz_natural: Mapped[int | None]  # 1 a 5
    humedad: Mapped[NivelHumedad | None] = mapped_column(
        _enum(NivelHumedad, "nivel_humedad")
    )
    orientacion: Mapped[Orientacion | None] = mapped_column(
        _enum(Orientacion, "orientacion")
    )
    estado_general: Mapped[int | None]  # 1 a 5
    ruido_entorno: Mapped[int | None]  # 1 a 5
    entorno: Mapped[str | None] = mapped_column(Text)
    requiere_refaccion: Mapped[bool | None] = mapped_column(Boolean)
    refaccion_estimada: Mapped[float | None] = mapped_column(Numeric(12, 2))
    notas: Mapped[str | None] = mapped_column(Text)
    fotos: Mapped[list | None] = mapped_column(Json)  # URLs en Supabase Storage

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    propiedad: Mapped[Propiedad] = relationship(back_populates="evaluaciones")


class EvaluacionCriterio(Base):
    """Resultado del motor de criterios (fase 7) por propiedad y corrida."""

    __tablename__ = "evaluacion_criterios"

    id: Mapped[int] = mapped_column(primary_key=True)
    propiedad_id: Mapped[int] = mapped_column(ForeignKey("propiedades.id"))
    corrida_id: Mapped[int | None] = mapped_column(ForeignKey("corridas.id"))
    criterio_id: Mapped[str] = mapped_column(String(80))  # id del catálogo YAML
    resultado: Mapped[ResultadoCriterio] = mapped_column(
        _enum(ResultadoCriterio, "resultado_criterio")
    )
    puntaje: Mapped[float | None] = mapped_column(Numeric(8, 3))
    mensaje: Mapped[str | None] = mapped_column(Text)
