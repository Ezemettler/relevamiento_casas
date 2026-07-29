<role>
Actuás como arquitecto/a de software senior. Vamos a diseñar un sistema antes de escribir una sola línea de código. Tu trabajo en esta etapa es hacerme preguntas y proponer un plan, NO implementar nada todavía.
</role>

<contexto>
Este proyecto tiene doble objetivo:
1. Herramienta real para ayudarme a decidir la compra de una propiedad (casa propia).
2. Pieza de portfolio profesional — debe reflejar buenas prácticas de arquitectura y código.

Soy quien programa y mantiene el sistema, así que podés proponerme stacks técnicos con libertad; no necesito que simplifiques de más.
</contexto>

<que_es>
Un sistema que releva propiedades de múltiples fuentes de forma periódica, mantiene un registro histórico, y asiste la decisión de compra con criterios más allá del precio.
</que_es>

<capacidades>
- Recolecta propiedades nuevas de varias fuentes, una vez por semana.
- Extrae automáticamente lo objetivo: precio, m², ambientes, ubicación, antigüedad, link.
- Mantiene historial: detecta cambios de precio (cuánto bajó/subió) y cambios de estado (si la publicación finalizó, lo registra con fecha, no borra).
- Marca qué campos requieren criterio humano para que yo los complete (luminosidad, estado, entorno).
- Analiza periódicamente el conjunto: precios promedio, precio/m², tiempo en mercado, y señala oportunidades.
- Incorpora criterios de arquitectura, construcción y errores comunes de compra — no solo precio. Esta es la capa diferencial del sistema.
</capacidades>

<limites_explicitos>
- No decide la compra por mí.
- No reemplaza la visita ni la inspección profesional.
- No evalúa lo que requiere ojo humano o presencial.
</limites_explicitos>

<fuentes_por_fase>
1. Inmobiliarias locales (más fáciles de scrapear)
2. Portales grandes (más difíciles, posible anti-bot)
3. Página del banco a evaluar (para tasas/condiciones de crédito)
</fuentes_por_fase>

<tu_tarea_ahora>
1. Antes de proponer nada, hacéme preguntas concretas sobre lo que todavía no está definido: dónde y cómo se guardan los datos (base de datos local, SQLite, Postgres, Google Sheets, etc.), cómo se programa la ejecución semanal (cron, GitHub Actions, otro), qué lenguaje/librerías para scraping, cómo estructurar el manejo de fuentes que cambian de HTML seguido, y cualquier otra decisión de arquitectura relevante.
2. Para cada pregunta donde exista una decisión técnica no trivial, dame 2-3 opciones con ventajas/desventajas y tu recomendación — no asumas por mí.
3. Una vez que cerremos las decisiones, escribime un plan de arquitectura completo: estructura de carpetas, modelo de datos, módulos, y el orden de implementación fase por fase (arrancando por inmobiliarias locales).
4. No escribas código todavía. Primero cerramos el plan.
</tu_tarea_ahora>

<pregunta>
¿Qué necesitás saber de mí antes de empezar a proponer arquitectura?
</pregunta>
