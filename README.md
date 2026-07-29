# Relevamiento de propiedades — Morón y alrededores

Sistema de relevamiento periódico del mercado inmobiliario del oeste del GBA, con registro
histórico y asistencia a la decisión de compra.

**Estado:** en planificación. Ver [PLAN.md](PLAN.md) para la arquitectura.

---

## Por qué existe

Comprar una casa es la decisión económica más grande que la mayoría de las personas toma, y se
toma con la peor información disponible: tres visitas, dos recuerdos borrosos y el precio que
pide el vendedor.

El problema de fondo es que **el mercado inmobiliario no tiene memoria pública**. Los portales
muestran el precio de hoy. Nadie muestra que esa casa está publicada hace ocho meses ni que ya
bajó tres veces. Esa información existe, pasa delante de todos, y se evapora.

Este sistema la registra.

---

## Qué aporta concretamente

### 1. Historial de precios

**Es el núcleo del valor y no se puede conseguir de otra forma.** Los portales no lo guardan y
no se puede reconstruir hacia atrás: si no se registra cuando ocurre, se perdió.

Es información directamente accionable al momento de ofertar:

| Lo que se observa | Lo que significa |
|---|---|
| Tres bajas consecutivas en 6 meses | El vendedor necesita vender. Hay margen real de negociación |
| Cero cambios en 10 meses | Precio anclado a una expectativa irreal. Probablemente no valga la pena ofertar |
| Publicada hace 3 semanas, sin bajas | Recién sale al mercado. Poco margen todavía |

Llegar a negociar sabiendo *"esto lleva 7 meses publicado y bajó 12% en dos escalones"* es una
posición completamente distinta a llegar a ciegas.

### 2. Un precio de referencia propio de la zona

Frente a una casa de 95.000 USD no hay forma de responder *"¿está bien?"* sin un marco de
comparación. Con algunos meses de relevamiento se obtiene la mediana de precio/m² por zona y
tipología, y la pregunta pasa a ser respondible:

> *"Está 18% por encima de la mediana para casas de 3 ambientes en esta zona."*

Eso convierte una intuición en un número defendible — frente al vendedor y frente a uno mismo.

### 3. Estado del mercado, medido

Registrando cuántas publicaciones aparecen y cuántas desaparecen cada mes se calcula la métrica
que usa el rubro: **meses de inventario**, cuánto tardaría en venderse todo el stock publicado
al ritmo actual.

| Meses de inventario | Mercado | Margen para ofertar |
|---|---|---|
| < 6 | De vendedor | Bajo — ofertas cerca del pedido |
| 6 a 9 | Equilibrado | Moderado |
| > 9 | De comprador | Amplio — se puede ofertar por debajo |

En un solo número: cuánta agresividad se puede permitir al negociar.

> **Advertencia honesta:** una publicación que desaparece no es necesariamente una venta.
> Puede ser un retiro, un vencimiento o un cambio de inmobiliaria. Se trata como un **proxy**
> y se reporta como tal, no como un dato duro.

### 4. Memoria estructurada de las visitas

Después de quince casas en cuatro meses nadie recuerda cuál tenía humedad en el fondo ni cuál
tenía la cocina al sur. Sin registro, cada visita nueva se compara contra el recuerdo borroso
de las anteriores — que es exactamente cómo se toman malas decisiones.

El sistema separa deliberadamente **lo que puede medir** de **lo que no**:

| Lo extrae el sistema | Lo carga una persona, en la visita |
|---|---|
| Precio, m², ambientes, antigüedad | Luz natural, orientación real |
| Ubicación, link, fecha de publicación | Humedad, estado general |
| Historial de cambios de precio | Ruido, entorno, refacciones necesarias |

Los campos subjetivos se cargan desde el celular, parado adentro de la propiedad. Quedan
guardados junto al historial de precios, y permiten comparar la tercera visita con la doceava.

### 5. Un contrapeso al sesgo

Cuando una propiedad gusta, se dejan de ver los problemas. Una tabla con precio/m² comparado,
días en mercado y criterios de construcción en alerta no se enamora.

---

## Qué NO hace

Los límites son parte del diseño, no una omisión:

- **No decide la compra.** Ordena información para que la decida una persona.
- **No reemplaza la visita ni la inspección profesional.** Ninguna estructura, instalación o
  vicio oculto se evalúa desde una publicación web.
- **No evalúa lo que requiere ojo humano o presencial.** Cuando un criterio no puede
  resolverse con datos objetivos, el sistema lo marca como pendiente y lo deriva al formulario
  de evaluación manual.
- **No estima valuaciones ni predice precios.** Describe lo que el mercado publica; no lo
  pronostica.

---

## Alcance

**Zona objetivo:** partido de Morón — Morón, Castelar, Haedo, El Palomar y Villa Sarmiento.

**Zona de referencia:** las localidades vecinas (Ramos Mejía, Ituzaingó, Ciudadela, Hurlingham
y otras) se relevan pero **no se muestran en el listado**: se usan para comparar. Un precio/m²
sin punto de comparación no significa nada, y es lo que permite detectar si la zona elegida
está cara respecto de una vecina a diez minutos.

**Operación:** solo venta.

| Se releva | No se releva |
|---|---|
| Casas | Terrenos y lotes |
| PH | Departamentos de 1 y 2 ambientes |
| Departamentos de 3 ambientes o más | Alquileres |

Techo de referencia: 150.000 USD. Las propiedades por encima **se siguen registrando** — son
las que dan el marco de comparación — pero quedan fuera de la vista por defecto.

**Fuentes:** cuatro inmobiliarias de la zona y +Hogares del Banco Nación. Frecuencia semanal.

---

## Cómo está construido

Python, Postgres y una app de Streamlit. Un job semanal automatizado recolecta, normaliza y
detecta cambios; la interfaz permite explorar el listado, ver el historial de cada propiedad y
cargar las evaluaciones de las visitas.

El detalle de arquitectura, el modelo de datos y las decisiones técnicas con su fundamento
están en [PLAN.md](PLAN.md).

---

## Nota sobre el uso de las fuentes

Relevamiento personal, de bajo volumen y sin fines comerciales. Una corrida semanal, con
límite de velocidad conservador y agente identificable. No se republica ni se redistribuye el
contenido de las fuentes.
