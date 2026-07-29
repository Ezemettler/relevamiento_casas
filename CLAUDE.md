# CLAUDE.md

Relevamiento semanal de propiedades en venta (partido de Morón) con historial de precios y
asistencia a la decisión de compra.

- **Por qué existe y qué aporta** → [README.md](README.md)
- **Arquitectura, modelo de datos y fases** → [PLAN.md](PLAN.md)

Antes de implementar cualquier cosa, leer la fase correspondiente del PLAN. Si algo del plan
resulta inviable al implementarlo, **decirlo y actualizar el PLAN** en vez de improvisar una
salida distinta en silencio.

## Cómo trabajar con el usuario

- Está aprendiendo a programar y a usar IA para desarrollo. **Explicar el porqué de cada
  decisión, no solo el qué.** Es un objetivo del proyecto, no una cortesía.
- Responder en castellano rioplatense. Jerga técnica solo si se explica la primera vez.
- Ante una decisión no trivial: dar opciones con ventajas y desventajas, y **una
  recomendación**. No delegar la decisión sin opinión.
- No dar por buena una implementación sin verificarla. Si algo falla, decirlo con el error.

## Reglas del dominio (no negociables)

Estas existen porque violarlas corrompe datos que no se pueden recuperar:

1. **Nunca borrar registros.** Una propiedad que desaparece de la fuente se marca
   `estado = finalizada` con fecha. Si vuelve a aparecer, se **reactiva** el registro existente.
2. **El scraping nunca escribe en `evaluaciones`.** Esa tabla es solo del usuario.
3. **Identidad = `(fuente_id, id_en_fuente)`.** Si ya existe, se actualiza; nunca se inserta
   un duplicado.
4. **Guardar siempre `payload_crudo`.** Permite reprocesar el histórico si mejora el parseo.
   Los avisos viejos ya no existen en la web.
5. **Verificación de salud antes de persistir.** Si una fuente devuelve 0 resultados o menos
   del 50% de lo esperado, abortar esa fuente **sin escribir nada**. Una fuente rota que
   devuelve vacío marcaría todas sus propiedades como vendidas.

## Convenciones técnicas

- **`uv`** para dependencias y entorno. No `pip` ni `venv` a mano.
- **Selectores CSS en `config/fuentes/*.yaml`**, nunca en código Python. El usuario tiene que
  poder arreglar una fuente rota editando texto.
- **Validar con Pydantic** en la frontera, antes de persistir. Un dato mal parseado contamina
  el historial para siempre.
- **Cambios de esquema con migración Alembic.** Nunca modificar tablas a mano en Supabase.
- **Cada fuente tiene un fixture HTML real** en `tests/fixtures/html/`. Los tests corren contra
  el fixture, no contra la web.
- **Rate limit de 2-3 segundos** entre requests, User-Agent identificable. Una corrida semanal.
- **Nombres de dominio en castellano** (`propiedades`, `cambios`, `evaluaciones`), código y
  librerías en inglés. Consistencia sobre preferencia.

## Comandos

```bash
uv sync                      # instalar / actualizar dependencias
uv run pytest -q             # correr los tests
uv run ruff check . --fix    # revisar y corregir estilo
uv run ruff format .         # formatear

uv run alembic revision --autogenerate -m "descripción"   # crear migración
uv run alembic upgrade head                               # aplicar a la base
uv run alembic downgrade -1                               # revertir la última
```

Los tests corren contra SQLite en memoria: **no necesitan Supabase ni internet**.
Solo Alembic requiere `DATABASE_URL` en el `.env`.
