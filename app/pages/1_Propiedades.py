"""Listado de propiedades con panel de detalle al costado.

Seleccionar una fila no navega a otra página — el panel de la derecha se
actualiza en el lugar. "Modificar datos" tampoco navega: abre un modal
(`st.dialog`) encima de esta misma pantalla. No existe una página aparte
de "completar datos" — se decidió así explícitamente: cargar humedad,
orientación, etc. es una acción sobre una propiedad, no un destino propio
de la navegación.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from componentes import encabezado  # noqa: E402
from datos import (  # noqa: E402
    actualizar_atributos_propiedad,
    barrios_disponibles,
    detalle_propiedad,
    filtros_configurados,
    guardar_o_actualizar_evaluacion,
    inmobiliarias_disponibles,
    listado_propiedades,
)

from relevamiento.modelos import NivelLuz, Orientacion  # noqa: E402

encabezado("📋 Propiedades")

config = filtros_configurados()
tipologias_disponibles = config.get("recoleccion", {}).get("tipologias", [])
precio_defecto = config.get("vista_por_defecto", {}).get("precio_maximo_usd")
zonas_defecto = config.get("vista_por_defecto", {}).get("categorias_zona", ["objetivo"])

_SI_NO_OPCIONES = {"Sin dato": None, "No": False, "Sí": True}


def _selector_si_no(etiqueta: str, actual: dict | None, campo: str) -> bool | None:
    """Selectbox de tres estados en vez de checkbox: un tilde sin marcar es
    indistinguible de "no lo cargué todavía" — acá "Sin dato" queda
    explícito en vez de guardarse como False sin querer."""
    valor_actual = actual.get(campo) if actual else None
    opciones = list(_SI_NO_OPCIONES.keys())
    etiqueta_actual = next(
        (k for k, v in _SI_NO_OPCIONES.items() if v == valor_actual), "Sin dato"
    )
    seleccion = st.selectbox(
        etiqueta, options=opciones, index=opciones.index(etiqueta_actual)
    )
    return _SI_NO_OPCIONES[seleccion]


@st.dialog("Modificar datos de la propiedad")
def _modal_completar_datos(
    propiedad_id: int, etiqueta: str, propiedad: dict, actual: dict | None
) -> None:
    st.caption(etiqueta)
    st.caption(
        "Lo que el scraping no puede sacar solo — mirando fotos del aviso o "
        "después de visitarla. Guardar reemplaza lo que hayas cargado antes."
    )

    # El scraping carga estos atributos una sola vez, al crear la propiedad
    # (ver persistir.py), y nunca los vuelve a tocar — si vino vacío o mal,
    # se queda así para siempre salvo que se corrija acá a mano.
    st.markdown("**Atributos físicos**")
    st.caption("Por si el scraping no los sacó bien o quedaron vacíos.")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        m2_cubiertos = st.number_input(
            "M² cubiertos",
            min_value=0.0,
            step=1.0,
            value=float(propiedad.get("m2_cubiertos") or 0),
        )
        ambientes = st.number_input(
            "Ambientes",
            min_value=0,
            step=1,
            value=int(propiedad.get("ambientes") or 0),
        )
        antiguedad_anios = st.number_input(
            "Antigüedad (años)",
            min_value=0,
            step=1,
            value=int(propiedad.get("antiguedad_anios") or 0),
        )
    with col_m2:
        m2_totales = st.number_input(
            "M² totales",
            min_value=0.0,
            step=1.0,
            value=float(propiedad.get("m2_totales") or 0),
        )
        dormitorios = st.number_input(
            "Dormitorios",
            min_value=0,
            step=1,
            value=int(propiedad.get("dormitorios") or 0),
        )
        banos = st.number_input(
            "Baños",
            min_value=0,
            step=1,
            value=int(propiedad.get("banos") or 0),
        )
    st.divider()

    disponible = st.checkbox(
        "Disponible para el análisis",
        value=actual["disponible"] if actual else True,
        help="Destildar para descartarla del listado y las métricas. El "
        "scraping le sigue registrando cambios de precio igual.",
    )

    opciones_luz = [None, *[n.value for n in NivelLuz]]
    indice_luz = (
        opciones_luz.index(actual["luz_natural"])
        if actual and actual.get("luz_natural") in opciones_luz
        else 0
    )
    luz_natural = st.selectbox(
        "Luz natural",
        options=opciones_luz,
        index=indice_luz,
        format_func=lambda v: v.capitalize() if v else "(sin especificar)",
    )

    humedad = _selector_si_no("Humedad", actual, "humedad")

    opciones_orientacion = [None, *[o.value for o in Orientacion]]
    indice_orientacion = (
        opciones_orientacion.index(actual["orientacion"])
        if actual and actual.get("orientacion") in opciones_orientacion
        else 0
    )
    orientacion = st.selectbox(
        "Orientación",
        options=opciones_orientacion,
        index=indice_orientacion,
        format_func=lambda v: v if v else "(sin especificar)",
    )

    distancia_estacion_km = st.number_input(
        "Distancia a la estación (km)",
        min_value=0.0,
        step=0.1,
        format="%.1f",
        value=float(actual["distancia_estacion_km"])
        if actual and actual.get("distancia_estacion_km")
        else 0.0,
    )

    st.caption("Criterios de descarte")
    col_a, col_b = st.columns(2)
    with col_a:
        cochera = _selector_si_no("Cochera", actual, "cochera")
        patio_jardin = _selector_si_no("Patio o jardín", actual, "patio_jardin")
        posibilidad_ampliacion = _selector_si_no(
            "Posibilidad de ampliación", actual, "posibilidad_ampliacion"
        )
    with col_b:
        ventilacion_cruzada = _selector_si_no(
            "Ventilación cruzada", actual, "ventilacion_cruzada"
        )
        grietas = _selector_si_no("Grietas", actual, "grietas")
        desniveles = _selector_si_no("Desniveles", actual, "desniveles")

    notas_defecto = actual["notas"] if actual and actual.get("notas") else ""
    notas = st.text_area("Notas libres", value=notas_defecto)

    if st.button("Guardar", type="primary", use_container_width=True):
        actualizar_atributos_propiedad(
            propiedad_id,
            {
                "m2_cubiertos": m2_cubiertos or None,
                "m2_totales": m2_totales or None,
                "ambientes": ambientes or None,
                "dormitorios": dormitorios or None,
                "banos": banos or None,
                "antiguedad_anios": antiguedad_anios or None,
            },
        )
        guardar_o_actualizar_evaluacion(
            propiedad_id,
            {
                "fecha_visita": date.today(),
                "disponible": disponible,
                "luz_natural": NivelLuz(luz_natural) if luz_natural else None,
                "humedad": humedad,
                "orientacion": Orientacion(orientacion) if orientacion else None,
                "distancia_estacion_km": distancia_estacion_km or None,
                "cochera": cochera,
                "patio_jardin": patio_jardin,
                "posibilidad_ampliacion": posibilidad_ampliacion,
                "ventilacion_cruzada": ventilacion_cruzada,
                "grietas": grietas,
                "desniveles": desniveles,
                "notas": notas or None,
            },
        )
        st.rerun()


# Se completa más abajo, una vez que se sabe cuántas propiedades cumplen
# los criterios — pero se reserva el lugar acá arriba, debajo del título.
texto_criterios = st.empty()

col_tipo, col_inmobiliaria, col_barrio, col_orden = st.columns([2, 2, 2, 1])
with col_tipo:
    tipologias = st.multiselect(
        "Tipología", options=tipologias_disponibles, default=tipologias_disponibles
    )
with col_inmobiliaria:
    # Sin selección = sin filtrar (no "sin resultados") — con pocas opciones
    # no hace falta arrancar con todas tildadas para que se entienda.
    inmobiliarias = st.multiselect(
        "Inmobiliaria", options=inmobiliarias_disponibles(), placeholder="Todas"
    )
with col_barrio:
    # Solo barrios de propiedades que realmente pueden aparecer en esta
    # tabla — sin esto, aparecían barrios de zonas fuera de alcance (la
    # costa, etc.) que acá nunca se muestran.
    opciones_barrio = barrios_disponibles(
        categorias_zona=zonas_defecto, precio_maximo=precio_defecto
    )
    barrios = st.multiselect("Barrio", options=opciones_barrio, placeholder="Todos")
with col_orden:
    orden = st.selectbox(
        "Ordenar por", ["precio_m2", "precio", "dias_en_mercado", "bajadas"]
    )

# Zona, techo de precio y disponibilidad quedan fijos en los valores por
# defecto de config/filtros.yaml — no son ajustables desde acá.
df = listado_propiedades(
    tipologias=tipologias or None,
    categorias_zona=zonas_defecto,
    precio_maximo=precio_defecto,
    solo_disponibles=True,
    inmobiliarias=inmobiliarias or None,
    barrios=barrios or None,
)

precio_texto = f"USD {precio_defecto:,.0f}".replace(",", ".")
texto_criterios.caption(
    f"{len(df)} propiedades disponibles en zona {'/'.join(zonas_defecto)} y "
    f"hasta {precio_texto} — los criterios que definimos por defecto. Fuera "
    "de estos, las propiedades se siguen guardando igual: no se pierden, "
    "solo no se muestran acá."
)

st.divider()

# Campos de descarte cargados a mano: sin evaluación todavía, "—" (no es lo
# mismo que "No" — todavía no se revisó).
# La polaridad no es la misma para todos: tener patio/cochera/ampliación es
# bueno (Sí = verde), pero tener grietas/desniveles es malo (Sí = rojo, al
# revés que los anteriores).
_CAMPOS_POSITIVOS = [
    "patio_jardin",
    "cochera",
    "posibilidad_ampliacion",
    "ventilacion_cruzada",
]
_CAMPOS_NEGATIVOS = ["grietas", "desniveles"]
_VERDE = "color: #4ADE80"
_ROJO = "color: #F87171"
_AMARILLO = "color: #FBBF24"

# Corte del semáforo para distancia a la estación, definido por el usuario.
_DISTANCIA_MAXIMA_VERDE_KM = 2.0

_EMOJI_TIPO = {"casa": "🏠", "ph": "🏘️", "departamento": "🏢", "otro": "📍"}


def _si_no(valor: bool | None) -> str:
    if valor is True:
        return "Sí"
    if valor is False:
        return "No"
    return "—"


def _color_positivo(valor: str) -> str:
    return _VERDE if valor == "Sí" else _ROJO if valor == "No" else ""


def _color_negativo(valor: str) -> str:
    return _ROJO if valor == "Sí" else _VERDE if valor == "No" else ""


# (campo, etiqueta, es_positivo) — mismo criterio de polaridad que en la
# tabla: cochera/patio/ampliación/ventilación son buenas noticias (Sí=verde),
# humedad/grietas/desniveles son al revés (Sí=rojo).
_CARACTERISTICAS = [
    ("cochera", "Cochera", True),
    ("patio_jardin", "Patio o jardín", True),
    ("posibilidad_ampliacion", "Posibilidad de ampliación", True),
    ("ventilacion_cruzada", "Ventilación cruzada", True),
    ("humedad", "Humedad", False),
    ("grietas", "Grietas", False),
    ("desniveles", "Desniveles", False),
]


def _semaforo_caracteristicas(p: dict, evaluacion: dict | None) -> None:
    """Bloque tipo semáforo: un vistazo rápido a los criterios de descarte
    de la propiedad, sin tener que leer una tabla. Además de los sí/no de
    siempre, suma luz natural (mucha/media/poca) y distancia a la estación
    (con un corte en km) — no son booleanos, pero es el mismo bloque."""
    items: list[tuple[str, str, str]] = []
    for campo, etiqueta, positivo in _CARACTERISTICAS:
        texto = _si_no(p.get(campo))
        color = _color_positivo(texto) if positivo else _color_negativo(texto)
        items.append((etiqueta, texto, color))

    luz = evaluacion.get("luz_natural") if evaluacion else None
    color_luz = {"mucha": _VERDE, "media": _AMARILLO, "poca": _ROJO}.get(luz, "")
    items.append(("Luz natural", luz.capitalize() if luz else "—", color_luz))

    distancia = evaluacion.get("distancia_estacion_km") if evaluacion else None
    if distancia is None:
        texto_distancia, color_distancia = "—", ""
    else:
        texto_distancia = f"{distancia} km"
        color_distancia = _VERDE if distancia <= _DISTANCIA_MAXIMA_VERDE_KM else _ROJO
    items.append(("Distancia estación", texto_distancia, color_distancia))

    columnas = st.columns(2)
    for i, (etiqueta, texto, color) in enumerate(items):
        if color == _VERDE:
            emoji = "🟢"
        elif color == _ROJO:
            emoji = "🔴"
        elif color == _AMARILLO:
            emoji = "🟡"
        else:
            emoji = "⚪"
        columnas[i % 2].markdown(f"{emoji} **{etiqueta}:** {texto}")


def _texto_cambio(c: dict) -> str:
    """Una línea legible por movimiento — "tal fecha bajó precio" en vez de
    una fila de tabla con columnas fecha/tipo/campo/de/a."""
    fecha_texto = c["fecha"].strftime("%d/%m/%Y")
    if c["tipo"] == "precio":
        de = float(c["de"]) if c["de"] else None
        a = float(c["a"]) if c["a"] else None
        variacion = f" ({c['variacion_pct']:+.0f}%)" if c["variacion_pct"] else ""
        flecha = "📉" if de and a and a < de else "📈"
        texto_de = f"USD {de:,.0f}".replace(",", ".") if de else "—"
        texto_a = f"USD {a:,.0f}".replace(",", ".") if a else "—"
        return f"{flecha} **{fecha_texto}** — precio: {texto_de} → {texto_a}{variacion}"
    if c["tipo"] == "estado":
        return f"🔴 **{fecha_texto}** — finalizó la publicación"
    if c["tipo"] == "reactivacion":
        return (
            f"🔵 **{fecha_texto}** — volvió a aparecer (se había marcado como finalizada)"
        )
    return f"⚪ **{fecha_texto}** — {c['campo']}: {c['de']} → {c['a']}"


col_lista, col_detalle = st.columns([3, 2])

with col_lista:
    if df.empty:
        st.info("Ninguna propiedad coincide con estos filtros.")
        propiedad_id = None
    else:
        df_mostrado = df.sort_values(orden, ascending=(orden != "bajadas")).copy()
        for campo in _CAMPOS_POSITIVOS + _CAMPOS_NEGATIVOS:
            df_mostrado[campo] = df_mostrado[campo].map(_si_no)

        estilo = df_mostrado.style.map(_color_positivo, subset=_CAMPOS_POSITIVOS).map(
            _color_negativo, subset=_CAMPOS_NEGATIVOS
        )

        evento = st.dataframe(
            estilo,
            use_container_width=True,
            hide_index=True,
            height=560,
            on_select="rerun",
            selection_mode="single-row",
            key="tabla_propiedades",
            column_config={
                "tipologia": st.column_config.TextColumn("Tipo"),
                "direccion": st.column_config.TextColumn("Dirección"),
                "barrio": st.column_config.TextColumn("Barrio"),
                "inmobiliaria": st.column_config.TextColumn("Inmobiliaria"),
                "precio_inicial": st.column_config.NumberColumn(
                    "Precio Inicial", format="%.0f"
                ),
                "precio": st.column_config.NumberColumn("Precio Actual", format="%.0f"),
                "moneda": st.column_config.TextColumn("Moneda"),
                "precio_m2": st.column_config.NumberColumn("Precio M2", format="%.0f"),
                "tendencia": st.column_config.TextColumn("Tendencia"),
                "ambientes": st.column_config.NumberColumn("Ambientes", format="%.0f"),
                "m2_cubiertos": st.column_config.NumberColumn(
                    "M2 Cubiertos", format="%.0f"
                ),
                "antiguedad_anios": st.column_config.NumberColumn(
                    "Antigüedad Años", format="%.0f"
                ),
                "dias_en_mercado": st.column_config.NumberColumn(
                    "Días En Mercado", format="%.0f"
                ),
                "patio_jardin": st.column_config.TextColumn("Patio Jardín"),
                "cochera": st.column_config.TextColumn("Cochera"),
                "posibilidad_ampliacion": st.column_config.TextColumn(
                    "Posibilidad Ampliación"
                ),
                "ventilacion_cruzada": st.column_config.TextColumn("Ventilación Cruzada"),
                "grietas": st.column_config.TextColumn("Grietas"),
                "desniveles": st.column_config.TextColumn("Desniveles"),
            },
            column_order=[
                "tipologia",
                "direccion",
                "barrio",
                "inmobiliaria",
                "precio_inicial",
                "precio",
                "moneda",
                "precio_m2",
                "tendencia",
                "ambientes",
                "m2_cubiertos",
                "antiguedad_anios",
                "dias_en_mercado",
                "patio_jardin",
                "cochera",
                "posibilidad_ampliacion",
                "ventilacion_cruzada",
                "grietas",
                "desniveles",
            ],
        )

        filas_elegidas = evento.selection.rows
        propiedad_id = (
            int(df_mostrado.iloc[filas_elegidas[0]]["id"]) if filas_elegidas else None
        )

with col_detalle:
    if propiedad_id is None:
        st.info("Seleccioná una propiedad de la lista para ver el detalle.")
    else:
        datos = detalle_propiedad(propiedad_id)
        p = datos["propiedad"]
        evaluacion = datos["evaluacion"]
        etiqueta = f"{p['tipologia']} — {p['direccion']}, {p['barrio']}"

        # Los valores de st.metric por defecto quedan enormes para una
        # columna angosta (se cortaban con "...") — se achica la fuente y el
        # espaciado vertical acá nada más, con una clase scopeada al
        # contenedor de la tarjeta, para no afectar los KPIs de Mercado.
        with st.container(key="tarjeta_detalle"):
            st.markdown(
                """
                <style>
                .st-key-tarjeta_detalle [data-testid="stMetricValue"] {
                    font-size: 1.15rem;
                }
                .st-key-tarjeta_detalle [data-testid="stVerticalBlock"] {
                    gap: 0.4rem;
                }
                .st-key-tarjeta_detalle hr {
                    margin: 0.3rem 0;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            emoji_tipo = _EMOJI_TIPO.get(p["tipologia"], "📍")
            tipo_texto = p["tipologia"].capitalize() if p["tipologia"] else "—"
            st.subheader(f"{emoji_tipo} {p['direccion'] or 'Sin dirección'}")
            st.caption(
                f"{p['barrio'] or 'sin barrio'} · {p['inmobiliaria'] or 'sin fuente'} "
                f"· {tipo_texto}"
            )
            if not p["disponible"]:
                st.warning(
                    "Descartada — no aparece en Mercado ni en el listado por defecto."
                )
            if p.get("otras_en_direccion"):
                plural = "es" if p["otras_en_direccion"] != 1 else ""
                st.caption(
                    f"ℹ️ Hay {p['otras_en_direccion']} publicación{plural} más de "
                    f"{p['inmobiliaria']} en esta misma dirección — no es un aviso "
                    "repetido, suele ser otra unidad del mismo lote o edificio."
                )
            st.divider()

            precio_actual_texto = (
                f"{p['moneda']} {p['precio']:,.0f}".replace(",", ".")
                if p["precio"]
                else "—"
            )
            precio_inicial_texto = (
                f"{p['moneda']} {p['precio_inicial']:,.0f}".replace(",", ".")
                if p["precio_inicial"]
                else "—"
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Precio actual", precio_actual_texto)
            c2.metric("Precio inicial", precio_inicial_texto)
            variacion = p["variacion_pct"]
            with c3:
                st.caption("Variación")
                if variacion is None:
                    st.markdown("—")
                else:
                    # Subir de precio es mala noticia para quien compra (rojo);
                    # bajar es buena noticia (verde) — al revés de lo que
                    # esperaría un inversor mirando una acción.
                    color = _ROJO if variacion > 0 else _VERDE if variacion < 0 else ""
                    flecha = "🔺" if variacion > 0 else "🔻" if variacion < 0 else "➖"
                    st.markdown(
                        f"<span style='{color}; font-weight: 600; "
                        f"font-size: 1.15rem;'>{flecha} {variacion:+.1f}%</span>",
                        unsafe_allow_html=True,
                    )
            st.divider()

            fecha_registro_texto = (
                p["fecha_primera_vista"].strftime("%d/%m/%Y")
                if p["fecha_primera_vista"]
                else "—"
            )
            c4, c5 = st.columns(2)
            c4.metric("📅 Primer registro", fecha_registro_texto)
            c5.metric("⏳ Días en mercado", p["dias_en_mercado"])
            st.divider()

            st.markdown("📐 **Superficie**")
            m2_cub = p["m2_cubiertos"]
            m2_tot = p["m2_totales"]
            col_cub, col_tot = st.columns(2)
            col_cub.caption(f"Cubiertos: {m2_cub:,.0f} m²" if m2_cub else "Cubiertos: —")
            col_tot.caption(f"Totales: {m2_tot:,.0f} m²" if m2_tot else "Totales: —")
            if m2_cub and m2_tot and m2_tot > 0:
                st.progress(min(m2_cub / m2_tot, 1.0))
            else:
                st.caption("Sin dato de m² totales para comparar.")
            st.divider()

            c6, c7 = st.columns(2)
            c6.metric("Ambientes", p["ambientes"] if p["ambientes"] is not None else "—")
            c7.metric(
                "Antigüedad",
                f"{p['antiguedad_anios']} años"
                if p["antiguedad_anios"] is not None
                else "—",
            )
            st.caption(
                f"Dormitorios: {p['dormitorios'] or '—'} · Baños: {p['banos'] or '—'}"
            )
            st.divider()

            st.markdown("🚦 **Características**")
            _semaforo_caracteristicas(p, evaluacion)
            if evaluacion and evaluacion.get("orientacion"):
                st.caption(f"Orientación: {evaluacion['orientacion']}")

            st.link_button("🔗 Ver aviso original", p["url"], use_container_width=True)
            if st.button(
                "📝 Modificar datos de esta propiedad", use_container_width=True
            ):
                _modal_completar_datos(propiedad_id, etiqueta, p, evaluacion)

            if p.get("descripcion"):
                with st.expander("Descripción de la fuente"):
                    st.write(p["descripcion"])

            st.divider()
            st.markdown("📈 **Historial de precios**")
            if len(datos["historial_precios"]) < 2:
                st.caption(
                    "Todavía no hay suficientes semanas registradas para graficar."
                )
            else:
                df_precios = pd.DataFrame(datos["historial_precios"])
                grafico_precios = (
                    alt.Chart(df_precios)
                    .mark_line(point=True, color="#38BDF8")
                    .encode(
                        x=alt.X("fecha:T", title=None),
                        y=alt.Y("precio:Q", title=None, scale=alt.Scale(zero=True)),
                        tooltip=["fecha:T", "precio:Q"],
                    )
                    .properties(height=180)
                )
                st.altair_chart(grafico_precios, use_container_width=True)

            st.divider()
            st.markdown("🔔 **Movimientos de esta publicación**")
            if not datos["cambios"]:
                st.caption("Todavía sin movimientos registrados.")
            else:
                for cambio in datos["cambios"]:
                    st.markdown(_texto_cambio(cambio))

            st.divider()
            st.markdown("📝 **Notas**")
            notas_texto = evaluacion.get("notas") if evaluacion else None
            st.write(notas_texto if notas_texto else "—")
