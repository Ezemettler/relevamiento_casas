# PLAN — Sistema de relevamiento de propiedades

> Documento de arquitectura. Definido antes de escribir código.
> Estado: **borrador para aprobación**
> Fecha: 2026-07-28

---

## 1. Qué es este sistema

Un sistema que releva propiedades en venta de varias fuentes, una vez por semana, mantiene el
historial completo de cada publicación, y ayuda a decidir una compra usando criterios de
arquitectura y construcción además del precio.

**Doble objetivo:** herramienta de uso real + pieza de portfolio profesional.

### Qué hace

- Recolecta propiedades nuevas de varias fuentes, semanalmente.
- Extrae lo objetivo: precio, m², ambientes, ubicación, antigüedad, link.
- Mantiene historial: detecta bajas/subas de precio y publicaciones finalizadas (registra la
  fecha, **nunca borra**).
- Marca qué campos requieren criterio humano y ofrece un formulario para completarlos.
- Analiza el conjunto: precio/m², tiempo en mercado, evolución del mercado, oportunidades.
- Evalúa cada propiedad contra un catálogo de criterios de construcción y errores comunes de compra.

### Qué NO hace

- No decide la compra.
- No reemplaza la visita ni la inspección profesional.
- No evalúa lo que requiere ojo humano o presencial.
- No extrae tasas ni condiciones de crédito (descartado explícitamente).

### Alcance del relevamiento

| Incluye | Excluye |
|---|---|
| Casas | Terrenos y lotes |
| PH | Departamentos de 1 y 2 ambientes |
| Departamentos de 3 ambientes o más | Alquileres |

### Zona — dos niveles, no un filtro

Las inmobiliarias relevadas publican propiedades de toda la zona oeste: **se descargan las
mismas páginas sin importar el recorte geográfico**. Ampliar la cobertura no cuesta requests
extra. Por eso no se descarta nada; se **clasifica**.

| Categoría | Localidades | Uso |
|---|---|---|
| `objetivo` | **Partido de Morón**: Morón, Castelar, Haedo, El Palomar, Villa Sarmiento | Lo que se ve en el listado por defecto |
| `referencia` | Ramos Mejía, Ituzaingó, Ciudadela, Hurlingham, Villa Tesei, San Antonio de Padua, Villa Luzuriaga | No aparece en el listado, **pero sí entra en las comparaciones de precio/m²** |
| `fuera_de_alcance` | El resto | Se guarda, no se analiza |

**Por qué la zona de referencia importa:** un precio/m² sin comparación no significa nada. La
categoría `referencia` permite responder *"esta casa está 18% arriba de la mediana de tu zona
objetivo y 25% arriba de Haedo"*, que es el tipo de dato que evita el error de anclarse en una
localidad y pagar sobreprecio sin saber que a doce cuadras había mejor relación.

Reclasificar una localidad es cambiar un valor en `config/filtros.yaml`: los datos históricos
ya están guardados y la nueva categoría aplica retroactivamente.

> **Tarea derivada (fase 2):** normalizar `localidad`. Cada inmobiliaria escribe la dirección a
> su manera ("Morón", "Moron", "Morón Sur", "B° Carlos Gardel"). Sin normalización, la
> clasificación por zona no funciona. Se resuelve con una tabla de alias en configuración.

### El filtro actúa en dos capas

Distinción importante, porque tienen consecuencias distintas:

| Capa | Dónde se define | Qué controla | Criterio |
|---|---|---|---|
| **Recolección** | `config/filtros.yaml` | Qué se scrapea y se guarda | **Amplio.** Lo que no se captura hoy no se recupera nunca: el aviso desaparece del sitio |
| **Visualización** | Control en la app | Qué se muestra en el listado | **A gusto**, cambia en cualquier momento sin tocar archivos |

Consecuencia práctica: si más adelante querés ver solo casas, destildás PH y departamento en
la interfaz. El historial acumulado queda intacto y podés volver atrás cuando quieras. Solo se
toca `filtros.yaml` si querés dejar de **recolectar** una tipología, que es una decisión más
difícil de revertir.

**Precio:** techo de 150.000 USD. Se aplica como **filtro por defecto de la vista**, no de la
recolección: las propiedades por encima se siguen guardando porque son las que dan el marco de
referencia para saber si un precio es bueno. Verlas o no es un checkbox.

**Operación:** solo venta. Los alquileres se descartan en la recolección.

---

## 2. Decisiones de arquitectura

Cada decisión con su alternativa descartada y el motivo. Si una premisa cambia, se revisa acá.

| # | Decisión | Elegido | Descartado | Por qué |
|---|---|---|---|---|
| D1 | Lenguaje | Python 3.12 | TypeScript | Scraping, análisis y UI en un solo lenguaje. |
| D2 | Interfaz | Streamlit | Web app FastAPI+React | Los campos de criterio humano se cargan durante la visita: hace falta un formulario real. Streamlit lo da con poco código y sin cambiar de lenguaje. Una web app completa consumiría el tiempo en UI en vez de en la capa diferencial. |
| D3 | Base de datos | Postgres (Supabase) | SQLite en git | Hay **dos escritores**: el job semanal y las evaluaciones manuales. Un `.db` binario commiteado produce conflictos de merge irresolubles. Supabase además da vista de tablas tipo planilla y storage para fotos. |
| D4 | Acceso a datos | SQLAlchemy + Alembic | SQL a mano | El esquema va a cambiar mucho en los primeros meses. Alembic hace que cambiar una tabla no implique perder datos. |
| D5 | Ejecución periódica | GitHub Actions (cron semanal) | Cron local / VPS | Corre con la máquina apagada, deja historial de ejecuciones auditable, sin infra que mantener ni costo. |
| D6 | Descarga HTML | `httpx` + `selectolax` | Playwright por defecto | La mayoría de las inmobiliarias locales sirven HTML estático. Playwright queda como fallback declarado por fuente, solo donde haga falta. |
| D7 | Configuración de fuentes | YAML declarativo | Un módulo Python por sitio | Cuando una fuente cambia el HTML se edita un archivo de texto con los selectores, no código. Reduce el costo de mantenimiento, que es el punto más frágil del sistema. |
| D8 | Capa de criterio | Reglas determinísticas en YAML | LLM como evaluador | Auditable, testeable y reproducible. El criterio de dominio queda **escrito y versionado**, que es lo que da valor real y de portfolio. El LLM entra después, acotado al texto libre. |
| D9 | Duplicados entre fuentes | No implementar por ahora | Unificación automática | Se desconoce la frecuencia real del problema. El modelo queda preparado, pero no se une nada hasta tener evidencia. |
| D10 | Validación de datos | Pydantic | Chequeos ad-hoc | Un dato mal parseado que entra a la base contamina el historial para siempre. Se valida en la frontera, antes de persistir. |

---

## 2.b Fuentes — reconocimiento técnico

Verificado el 2026-07-28 con peticiones reales.

| Fuente | URL de listado | Método | Fase | Observaciones |
|---|---|---|---|---|
| Carlos Fernández Prop. | `carlosfernandezprop.com.ar/Venta` | `httpx` | 1 | HTML servido por servidor, precios y m² presentes |
| Marcelo Milano | `marcelomilano.com.ar/Venta` | `httpx` | 2 | Ídem |
| Sarro Pucheta | `sarropucheta.com/propiedades/todas/venta` | `httpx` | 2 | Ídem |
| Milano Antonio (Argenprop) | `argenprop.com/inmobiliarias/milano-antonio/...` | `httpx` + fallback | 6 | Inmobiliaria **distinta** de Marcelo Milano. Ver nota |
| +Hogares Banco Nación | `mashogaresconbna.com.ar/list?...&ubicaciones=[Morón]` | API o Playwright | 6 | SPA Next.js. Ver nota |

**Ninguna de las tres primeras requiere Playwright** — confirma D6. Son HTML estático y el
adapter YAML genérico debería cubrirlas sin código específico.

**Nota sobre Argenprop:** respondió 200 con datos, pero el HTML incluye marcadores de
Cloudflare y captcha. Funcionó desde IP residencial; **es probable que sea bloqueada desde las
IPs de datacenter de GitHub Actions**. Si eso ocurre, la opción es correr esa fuente
manualmente desde la máquina local y el resto en la nube — el pipeline es el mismo código con
distinto disparador, así que no requiere rediseño. Además, verificar si es la misma
inmobiliaria que "Marcelo Milano": de serlo, conviene relevar solo el sitio propio (más simple
y sin anti-bot) y descartar esta fuente.

**Nota sobre +Hogares (BNA):** la página no trae datos en el HTML — es una SPA de Next.js que
los pide a una API interna. Dos caminos, en este orden de preferencia:

1. **Identificar la API que consume el frontend.** Si se encuentra, pasa a ser la fuente *más
   fácil* de todas: devuelve JSON estructurado, sin parseo de HTML y sin fragilidad ante
   cambios de diseño.
2. **Playwright** como fallback: renderizar la página y leer el DOM resultante. Más lento y
   más frágil, pero funciona siempre.

**Uso responsable:** ninguno de los sitios publica `robots.txt` (devuelven error o HTML), por
lo que no hay restricción explícita. Igualmente se aplica rate limit de 1 request cada 2-3
segundos, User-Agent identificable y una sola corrida semanal. Es uso personal, de bajo
volumen y no comercial.

---

## 3. Stack

```
Python 3.12
├── httpx + selectolax          Descarga y parseo HTML
├── playwright                  Fallback para sitios con JS / anti-bot (fase 5)
├── pydantic                    Validación de datos scrapeados
├── sqlalchemy + alembic        ORM y migraciones
├── psycopg                     Driver Postgres
├── pandas                      Análisis y métricas
├── streamlit                   Interfaz
├── pytest                      Tests
├── ruff                        Lint y formato
└── uv                          Gestión de dependencias y entorno
```

Infraestructura: **Supabase** (Postgres + storage), **GitHub Actions** (cron), **Streamlit
Community Cloud** (deploy de la app).

---

## 4. Modelo de datos

La decisión central del sistema. Separa tres cosas que suelen mezclarse mal:
**qué es la propiedad**, **qué vio el sistema cada semana**, y **qué evaluaste vos**.

```
                    ┌──────────────┐
                    │   fuentes    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
        ┌───────────┤ propiedades  ├───────────┐
        │           └──────┬───────┘           │
        │                  │                   │
┌───────▼──────┐   ┌───────▼──────┐   ┌────────▼───────┐
│ observaciones│   │   cambios    │   │  evaluaciones  │
│  (sistema)   │   │ (derivado)   │   │   (humanas)    │
└──────────────┘   └──────────────┘   └────────────────┘
```

### `fuentes`
Catálogo de sitios relevados.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `nombre` | text | ej. "Inmobiliaria X" |
| `tipo` | enum | `inmobiliaria_local` / `portal` / `banco` |
| `url_base` | text | |
| `activa` | bool | permite pausar una fuente rota sin borrarla |

### `propiedades`
**Un registro por propiedad, para siempre.** Es la tabla que se mira.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | interno |
| `fuente_id` | FK | |
| `id_en_fuente` | text | ID o slug del aviso en el sitio origen |
| `url` | text | |
| `tipologia` | enum | `casa` / `ph` / `departamento` |
| `ambientes`, `dormitorios`, `banos` | int | |
| `m2_cubiertos`, `m2_totales`, `m2_terreno` | numeric | |
| `antiguedad_anios` | int | |
| `direccion_texto`, `barrio`, `localidad` | text | |
| `lat`, `lon` | numeric | nullable, se completa cuando se pueda geocodificar |
| `precio_inicial`, `moneda_inicial` | numeric, text | precio de la primera vez que se vio |
| `precio_actual`, `moneda_actual` | numeric, text | precio de la última corrida |
| `expensas` | numeric | nullable |
| `titulo`, `descripcion` | text | |
| `estado` | enum | `activa` / `finalizada` |
| `fecha_primera_vista` | date | de acá sale "tiempo en mercado" |
| `fecha_ultima_vista` | date | |
| `fecha_finalizacion` | date | nullable; se completa cuando el aviso desaparece |
| `posible_duplicado_de` | FK nullable | previsto para D9, no se usa todavía |

**Regla de identidad (evita duplicados):** `(fuente_id, id_en_fuente)` es único. Cada semana,
si esa combinación ya existe, se **actualiza** el registro existente; nunca se crea uno nuevo.
Si un aviso deja de aparecer, no se borra: se marca `finalizada` con fecha.

### `observaciones`
Lo que el sistema vio en cada corrida. Es la memoria bruta; no se consulta a diario.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `propiedad_id` | FK | |
| `corrida_id` | FK | |
| `fecha` | date | |
| `precio`, `moneda` | numeric, text | |
| `visible` | bool | si el aviso seguía publicado |
| `payload_crudo` | jsonb | todo lo scrapeado tal cual, sin normalizar |
| `hash_contenido` | text | detecta si algo cambió sin comparar campo por campo |

> Guardar el `payload_crudo` permite re-procesar el histórico si más adelante se mejora el
> parseo, sin tener que volver a scrapear (los avisos viejos ya no existen).

### `cambios`
Derivado de `observaciones`. **Es el "campo cambios"**, pero como historial completo.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `propiedad_id` | FK | |
| `fecha` | date | |
| `tipo` | enum | `precio` / `estado` / `atributo` |
| `campo` | text | |
| `valor_anterior`, `valor_nuevo` | text | |
| `variacion_pct` | numeric | solo para cambios de precio |

Ejemplo de lo que se ve en la ficha:

```
2026-08-04  precio  95.000 USD → 89.000 USD  (-6,3%)
2026-09-15  precio  89.000 USD → 85.000 USD  (-4,5%)
2026-10-02  estado  activa → finalizada
```

> Tres bajas consecutivas es una señal de dominio fuerte (dueño apurado o propiedad
> sobrevaluada de origen). Un solo campo "precio actual" perdería esa información.

### `evaluaciones`
**Tabla separada, escrita solo por vos.** Ningún re-scrapeo puede pisarla.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `propiedad_id` | FK | |
| `fecha_visita` | date | |
| `luz_natural` | int 1-5 | |
| `humedad` | enum | `no_detectada` / `leve` / `importante` |
| `orientacion` | enum | N / NE / E / SE / S / SO / O / NO |
| `estado_general` | int 1-5 | |
| `ruido_entorno` | int 1-5 | |
| `entorno` | text | |
| `requiere_refaccion` | bool | |
| `refaccion_estimada` | numeric | nullable |
| `notas` | text | |
| `fotos` | jsonb | URLs en Supabase Storage |

### `corridas`
Trazabilidad de cada ejecución semanal.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `inicio`, `fin` | timestamp | |
| `estado` | enum | `ok` / `parcial` / `error` |
| `nuevas`, `actualizadas`, `finalizadas` | int | |
| `errores` | jsonb | por fuente |

### `evaluacion_criterios`
Resultado del motor de criterios (sección 7) por propiedad y corrida.

| Campo | Tipo | Notas |
|---|---|---|
| `propiedad_id` | FK | |
| `criterio_id` | text | del catálogo YAML |
| `resultado` | enum | `ok` / `atencion` / `alerta` / `sin_datos` |
| `puntaje` | numeric | |
| `mensaje` | text | explicación legible |

### Métricas derivadas (vista SQL, no tabla)

**Por propiedad:** `precio_m2`, `dias_en_mercado`, `cantidad_bajas_precio`,
`variacion_total_pct`, `precio_m2_vs_mediana_zona`.

**De flujo de mercado (mensual):**

| Métrica | Cálculo | Para qué sirve |
|---|---|---|
| `altas_mes` | publicaciones nuevas en el mes | ¿entra oferta nueva o el mercado está quieto? |
| `bajas_mes` | publicaciones que dejaron de aparecer | proxy de ventas (ver advertencia) |
| `stock_activo` | propiedades activas a fin de mes | tamaño del mercado disponible |
| `tasa_absorcion` | `bajas_mes / stock_activo_promedio` | velocidad a la que se drena el stock |
| **`meses_inventario`** | `stock_activo / promedio_bajas_mensuales` | **la métrica clave** |
| `mediana_dias_hasta_baja` | mediana de `dias_en_mercado` de las que se fueron | cuánto tarda en venderse lo que se vende |
| `pct_bajas_con_reduccion` | % de las bajas que habían reducido precio antes | ¿hace falta bajar el precio para vender? |

**Cómo leer `meses_inventario`:**

| Valor | Interpretación | Consecuencia al negociar |
|---|---|---|
| < 6 meses | Mercado de vendedor | Poco margen. Ofertas cerca de pedido o se pierde la propiedad |
| 6 a 9 meses | Equilibrado | Margen de negociación moderado |
| > 9 meses | Mercado de comprador | Margen amplio. Se puede ofertar por debajo con confianza |

> ⚠️ **Advertencia metodológica — una baja NO es una venta.**
> Una publicación puede desaparecer por venta, por retiro del dueño, por vencimiento del
> aviso, o porque cambió de inmobiliaria. Es un **proxy**, y se documenta como tal.
>
> Se afina con dos señales: (a) una propiedad que desaparece tras 2-8 meses publicada y
> después de al menos una baja de precio es probablemente venta; (b) una que desaparece a
> los pocos días de publicada, no. La métrica se reporta con una banda de confianza, no
> como un número duro.
>
> ⚠️ **Reapariciones.** Si una propiedad marcada `finalizada` vuelve a aparecer, **no se
> vendió**: se reactiva el registro existente (no se crea uno nuevo) y se descuenta de las
> bajas del mes correspondiente. El campo `id_en_fuente` lo permite. Requiere un
> `reactivaciones` en el historial de `cambios`.
>
> ⚠️ **Arranque en frío.** En la primera corrida *todo* es un alta. Ese mes se excluye del
> cálculo de `altas_mes` o el gráfico miente. Las métricas de flujo recién son
> interpretables a partir del segundo mes completo.

---

## 5. Estructura de carpetas

```
relevamiento_casas/
├── README.md
├── PLAN.md                          este documento
├── CLAUDE.md                        contexto e instrucciones para trabajar el repo
├── pyproject.toml
├── .env.example
│
├── .github/workflows/
│   └── relevamiento-semanal.yml     cron + notificación de errores
│
├── config/
│   ├── fuentes/                     una fuente = un YAML (selectores CSS)
│   │   ├── _ejemplo.yaml
│   │   └── mas_hogares_bna.yaml
│   ├── criterios.yaml               catálogo de criterios de compra
│   └── filtros.yaml                 tipología, rango de precio, zona
│
├── src/relevamiento/
│   ├── config.py                    carga de YAML y variables de entorno
│   ├── modelos.py                   tablas SQLAlchemy
│   ├── esquemas.py                  modelos Pydantic de validación
│   ├── db.py                        conexión y sesiones
│   │
│   ├── scraping/
│   │   ├── base.py                  interfaz Adapter (contrato común)
│   │   ├── adapter_yaml.py          adapter genérico guiado por config
│   │   ├── descarga.py              httpx / playwright, reintentos, rate limit
│   │   └── fuentes/                 adapters con lógica propia (excepciones)
│   │
│   ├── normalizacion/
│   │   ├── precios.py               "U$S 95.000" → (95000, "USD")
│   │   ├── superficie.py            "120 m2 cub." → 120.0
│   │   └── ubicacion.py             barrio, localidad, geocoding
│   │
│   ├── pipeline/
│   │   ├── correr.py                orquestador de la corrida semanal
│   │   ├── persistir.py             upsert por identidad, sin duplicar
│   │   └── cambios.py               detección de cambios y finalizaciones
│   │
│   ├── criterios/
│   │   ├── motor.py                 evalúa el catálogo YAML
│   │   └── reglas.py                primitivas reutilizables
│   │
│   ├── analisis/
│   │   └── metricas.py              precio/m², tiempo en mercado, oportunidades
│   │
│   └── alertas.py                   avisa si una fuente se rompió
│
├── app/                             Streamlit
│   ├── Inicio.py                    resumen de la semana
│   └── pages/
│       ├── 1_Listado.py             tabla filtrable
│       ├── 2_Ficha.py               detalle + historial de precios
│       ├── 3_Mi_evaluacion.py       formulario de campos humanos
│       └── 4_Mercado.py             análisis del conjunto
│
├── tests/
│   ├── fixtures/html/               HTML real guardado por fuente
│   ├── test_adapters.py
│   ├── test_normalizacion.py
│   └── test_cambios.py
│
└── scripts/
    ├── explorar_fuente.py           ayuda a descubrir selectores de un sitio nuevo
    └── recalcular_criterios.py
```

---

## 6. Flujo de una corrida semanal

```
1. Abrir corrida (registro en `corridas`)
2. Por cada fuente activa:
     a. Descargar el listado (con rate limit y reintentos)
     b. Parsear según su YAML → datos crudos
     c. Validar con Pydantic → descartar y loguear lo inválido
     d. Normalizar precio, superficie, ubicación
     e. VERIFICACIÓN DE SALUD: ¿devolvió 0 resultados? ¿campos clave vacíos?
        → si sí: marcar fuente en error, NO tocar la base con esos datos
3. Persistir:
     - identidad (fuente_id, id_en_fuente)
     - nueva  → insertar en `propiedades` + `observaciones`
     - existente → actualizar `precio_actual`, `fecha_ultima_vista` + `observaciones`
     - ya no aparece → `estado = finalizada`, `fecha_finalizacion`
4. Derivar `cambios` comparando con la observación anterior
5. Evaluar el catálogo de criterios sobre las propiedades activas
6. Cerrar corrida con métricas
7. Si hubo fuentes en error → alerta
```

**El paso 2e es el que evita el peor escenario:** que una fuente cambie el HTML, devuelva
vacío, y el sistema marque todas sus propiedades como finalizadas. Si una fuente devuelve
menos del 50% de lo esperado, se aborta esa fuente sin escribir nada.

---

## 7. Manejo de fuentes que cambian de HTML

Es el punto más frágil de cualquier scraper. Tres defensas:

**1. Selectores en YAML, no en código.**

```yaml
nombre: Inmobiliaria X
tipo: inmobiliaria_local
url_base: https://ejemplo.com.ar
metodo: httpx          # o "playwright" si hace falta
listado:
  url: /propiedades?operacion=venta&pagina={pagina}
  item: "div.property-card"
  id_en_fuente: "a@href"
  paginacion:
    tipo: numerica
    max_paginas: 20
detalle:
  precio: ".price"
  m2_cubiertos: ".features li:nth-child(2)"
  ambientes: ".features li:nth-child(1)"
  antiguedad: ".antiquity"
  direccion: "h2.address"
  descripcion: ".description"
```

**2. Tests contra HTML guardado.** Cada fuente tiene una página real en `tests/fixtures/html/`.
Si un cambio rompe el parseo, los tests lo detectan antes de una corrida real.

**3. Alerta activa.** Si una fuente devuelve 0 resultados, o si un campo clave viene nulo en
más del 30% de los avisos, la corrida lo reporta. Es cómo se detecta una rotura **antes** de
perder semanas de datos.

**Nota operativa:** se respeta `robots.txt`, se usa un rate limit conservador (1 request cada
2-3 segundos) y un User-Agent identificable. Es uso personal y de bajo volumen.

---

## 8. Capa de criterio — el diferencial

Un catálogo versionado de criterios de arquitectura, construcción y errores comunes de compra.
Cada criterio es declarativo y explica su razonamiento.

```yaml
- id: relacion_cubierto_terreno
  aplica_a: [casa, ph]
  descripcion: >
    Relación entre metros cubiertos y superficie de terreno. Un cociente muy alto
    deja poco espacio libre y limita ampliaciones futuras; muy bajo puede implicar
    terreno subutilizado o costos de mantenimiento altos.
  regla: m2_cubiertos / m2_terreno
  umbrales:
    ok: [0.3, 0.6]
    atencion: [0.6, 0.75]
    alerta: [0.75, 1.0]

- id: antiguedad_vs_instalaciones
  aplica_a: [casa, ph, departamento]
  descripcion: >
    Propiedades de más de 40 años suelen requerir renovación completa de instalación
    eléctrica y sanitaria. Es el costo oculto más subestimado en una compra.
  regla: antiguedad_anios > 40
  resultado_si_true: atencion
  mensaje: "Presupuestar renovación de instalación eléctrica y sanitaria."

- id: senales_en_descripcion
  aplica_a: [casa, ph, departamento]
  descripcion: Frases del aviso que anticipan costos o restricciones.
  patrones:
    alerta: ["a refaccionar", "a reciclar", "requiere inversión", "sin escritura"]
    atencion: ["a estrenar", "apto crédito", "contrafrente"]
```

El motor devuelve, por propiedad, una lista de resultados con mensaje explicativo — **no un
número único**. Un score agregado esconde el razonamiento; la idea es lo contrario.

Cuando un criterio no puede evaluarse por falta de datos objetivos (luminosidad, humedad,
orientación real), el sistema lo marca `sin_datos` y lo empuja al formulario de evaluación
humana. **Así se conecta el límite explícito del sistema con la acción concreta.**

---

## 9. Fases de implementación

**Horizonte de compra: 3-6 meses mínimo** (sujeto a aprobación del crédito). Eso da entre 13 y
26 corridas semanales — suficiente para historial de precios útil y para las primeras métricas
de flujo, pero no sobra. El orden prioriza **empezar a acumular datos cuanto antes**.

| Fase | Qué entrega | Por qué en este orden |
|---|---|---|
| **0. Cimientos** | Repo, entorno con `uv`, Supabase conectado, modelos SQLAlchemy, migración inicial, tests corriendo | Sin base no hay historial, y el historial solo se construye con el tiempo |
| **1. Primera fuente real** | 1 inmobiliaria local end-to-end: descarga → parseo → normalización → persistencia | Valida el diseño completo con el mínimo de código. Acá se aprende lo que ningún plan anticipa |
| **2. Resto de fuentes + historial** | Las 4 fuentes HTML, detección de cambios de precio, finalizaciones y reactivaciones | Con esto **el reloj ya está corriendo**: cada semana suma valor aunque no se toque más el código |
| **3. Automatización** ⬆ | GitHub Actions semanal + alertas si una fuente se rompe | **Adelantada.** Una corrida manual olvidada es una semana de datos perdida para siempre. Automatizar vale más que tener linda la interfaz |
| **4. +Hogares BNA** ⬆ | Descubrir la API o Playwright | **Adelantada.** Son propiedades pre-validadas para crédito BNA — es justo el crédito que estás gestionando. Alta relevancia pese a la dificultad técnica |
| **5. Interfaz** | Streamlit: listado, ficha con historial, formulario de evaluación, deploy | Primer momento en que el sistema es **usable**. Habilita cargar evaluaciones desde el celular en las visitas |
| **6. Métricas de mercado** | Altas/bajas mensuales, absorción, meses de inventario, precio/m² por zona | Necesita 2+ meses de historial para ser interpretable. Llega justo para la etapa de negociación |
| **7. Criterios de compra** | Catálogo YAML + motor + integración en la ficha | La capa diferencial. Va acá porque los umbrales se calibran con datos reales de la zona, no en abstracto |
| **8. Opcional: LLM** | Extracción de señales del texto libre de los avisos | Solo si las reglas se quedan cortas, sobre una base determinística ya funcionando |

**Objetivo de las fases 0-3: tenerlas listas lo antes posible.** A partir de la fase 3 el
sistema acumula solo, sin intervención. Todo lo demás se puede construir después sobre datos
que ya se están juntando — pero el historial no se puede recuperar hacia atrás.

**Entregable de valor más temprano: fase 5.** A partir de ahí el sistema ya sirve aunque el
resto no exista.

> El tiempo de espera del crédito no es tiempo muerto: es exactamente el período en que el
> sistema acumula el historial que después se usa para negociar.

---

## 10. Operación

- **Cuándo corre:** lunes 08:00 (cron de GitHub Actions), y se puede disparar a mano.
- **Cómo se sabe si falló:** la corrida deja registro en `corridas`; si hay fuentes en error,
  el workflow falla visiblemente y notifica.
- **Qué hacer si una fuente se rompió:** correr sus tests, comparar el HTML actual contra el
  fixture guardado, actualizar los selectores en su YAML. No requiere tocar código Python.
- **Backup:** Supabase tiene backups automáticos; además se exporta un dump semanal como
  artifact del workflow.

---

## 11. Decisiones abiertas

- [x] ~~Fuentes concretas~~ — definidas en 2.b. Zona: Morón y alrededores. 5 fuentes.
- [x] ~~¿Milano Antonio = Marcelo Milano?~~ — son inmobiliarias distintas, se relevan ambas.
- [x] ~~Rango de precio~~ — techo de 150.000 USD (ver 1.b).
- [ ] **Encontrar la API de +Hogares** — evita depender de Playwright. Tarea de fase 6.
- [ ] **Horizonte de compra** — condiciona qué fases tienen sentido priorizar.
- [ ] **Unificación de duplicados entre fuentes** — pospuesta (D9). Revisar cuando haya
      evidencia de qué tan frecuente es.
- [ ] **Geocoding** — definir proveedor cuando se llegue al análisis por zona.
- [ ] **Fotos de visitas** — Supabase Storage, a definir en fase 3.
```

