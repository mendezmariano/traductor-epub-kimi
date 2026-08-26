> **Nota:** Este backlog se actualiza por cada entrega. Los cambios sin commitear se marcan con el estado actual correspondiente.

# Backlog del proyecto

## Resumen visual

| Estado | Cantidad |
|--------|----------|
| Completado | 16 |
| En progreso | 0 |
| Por hacer | 0 |

---

## Plan de entregas

| Entrega | ID | Tarea | Prioridad | Estado |
|---------|----|-------|-----------|--------|
| 1 | EPUB-010 | Traducir atributos traducibles (`alt`, `title`, `aria-label`, `placeholder`) | Alta | `DONE` |
| 2 | EPUB-017 | Descomposición y reconstrucción completa del EPUB (DOM + CSS) | Alta | `DONE` |
| 3 | EPUB-008 | Fortalecer tests de LibreTranslate | Media | `DONE` |
| 4 | EPUB-009 | Implementar reintentos en traductores API | Media | `DONE` |
| 5 | EPUB-014 | Validación de respuestas de LLM | Media | `DONE` |
| 6 | EPUB-012 | Modo dry-run | Baja | `DONE` |
| 7 | EPUB-011 | Barra de progreso visual | Baja | `DONE` |
| 8 | EPUB-016 | Integración continua (GitHub Actions) | Baja | `DONE` |

---

## Estado del desarrollo

- **Rama activa:** `master`
- **Pull Requests abiertos:**
  - EPUB-014: https://github.com/mendezmariano/traductor-epub-kimi/pull/2
  - EPUB-012: https://github.com/mendezmariano/traductor-epub-kimi/pull/3
  - EPUB-011: https://github.com/mendezmariano/traductor-epub-kimi/pull/4
  - EPUB-016: https://github.com/mendezmariano/traductor-epub-kimi/pull/5
- **Última verificación de tests:** 58 tests OK en `master`.

## Cómo continuar

1. Revisar y mergear los PRs #2 a #5.
2. Ejecutar tests en `master`: `python3 -m unittest discover tests -v`.
3. Actualizar `STATUS.md` después del merge.

### Nota del trabajo ad-hoc (agentes/skills y segmentación LibreTranslate)

- Se crearon `AGENTS.md`, `.agents/*.md` y `skills/*.md` para estandarizar el trabajo de Kimi Code en el proyecto.
- Se detectó que LibreTranslate destruye los marcadores `___PHN___`, dejando sin traducir las unidades con tags inline.
- Se implementó traducción segmentada en `epub_toolkit/translator.py`: separa texto plano y placeholders, traduce los segmentos planos en lotes y reconstruye la unidad conservando el marcado.
- Se añadieron tests de segmentación y de glosario directo.
- Se tradujo `libros/Developer.epub` con LibreTranslate local; resultado en `output/Developer_es.epub`.
- Commit/push a `master`: `f8acb54`.

### Nota de la entrega 1

Implementada la traducción de atributos traducibles. Los atributos `alt`, `title`, `aria-label` y `placeholder` de los elementos block e inline ahora se extraen, traducen en lote y restauran durante la reconstrucción. Se añadió el campo `translated_attrs` a `TranslationUnit`.

### Nota de la entrega 2

Se creó el analizador estructural `epub_toolkit/analyzer.py` y el test `tests/test_full_roundtrip.py`. Se verificó que los EPUBs de `libros/` se descomponen y reconstruyen preservando:

- DOM de cada XHTML (mismo número de elementos, atributos y nodos de texto).
- Contenido de las hojas CSS.
- Hashes de recursos binarios (imágenes, fuentes).

**No se detectaron discrepancias estructurales.** No fue necesario corregir el pipeline existente.

### Nota de la entrega 3

Se fortaleció `tests/test_libretranslate_integration.py` con un mock configurable. Se añadieron tests para:

- Traducción por lote (`translate_batch`).
- Traducción de archivo completo (`translate_batch_for_file` y `translate_document`).
- Envío de `api_key`.
- Funcionamiento del parámetro `delay`.
- Manejo de errores HTTP 404, HTTP 500, respuesta sin `translatedText` y cantidad inesperada de textos.

Se mejoró el mensaje de error cuando falta `translatedText`.

### Nota de la entrega 4

Se implementaron reintentros exponenciales en `_post_json_with_retry` para los motores de API:

- Reintenta ante errores HTTP 5xx, 429 y errores de conexión.
- No reintenta ante errores 4xx (salvo 429).
- `LibreTranslateTranslator`, `OpenAICompatibleTranslator` y `OllamaTranslator` aceptan `retries` (por defecto 3).
- El CLI acepta `--retries`.
- Se añadió `tests/test_retries.py` con mocks de fallos transitorios.

### Nota de la entrega 5

Se añadió validación de placeholders después de recibir respuestas de LLM:

- `_collect_placeholder_ids` y `_validate_translated_texts` comparan los placeholders del original con los de la traducción.
- Si un lote pierde placeholders, se reintenta en modo estricto (`strict=True`) uno a uno.
- Si el reintento también falla, se conserva el texto original y se emite `warnings.warn`.
- La misma validación se aplica a los atributos traducibles.
- Se añadió `PlaceholderValidationTestCase` en `tests/test_translator.py`.

### Nota de la entrega 6

Se implementó el modo dry-run en el comando `translate`:

- Opción `--dry-run` que solo estima volumen sin traducir ni escribir `translation_units.json`.
- Función `estimate_document()` en `epub_toolkit/translator.py` que cuenta unidades, caracteres y tokens estimados.
- Tests de la estimación y del CLI en `tests/test_translator.py`.

### Nota de la entrega 7

Se mejoró la experiencia visual de progreso:

- `translate_document` usa `tqdm` como barra de progreso cuando está disponible.
- Si `tqdm` no está instalado, se mantiene el progreso textual.
- `--quiet` desactiva cualquier salida de progreso.
- `tqdm` sigue siendo una dependencia opcional.

### Nota de la entrega 8

Se añadió integración continua:

- Workflow `.github/workflows/ci.yml`.
- Ejecuta tests en Python 3.12 ante push y pull requests a `master`/`main`.
- Instala `lxml` y corre `python3 -m unittest discover tests -v`.

---

## Detalle de entregas

### Entrega 1 — Atributos traducibles (EPUB-010)

**Objetivo:** completar el campo `translatable_attrs` que existe en el modelo pero no se usa.

**Qué se implementa**

- Extraer atributos traducibles de cada unidad.
- Incluirlos en el lote enviado al traductor.
- Restaurarlos durante la reconstrucción.

**Archivos**

- `epub_toolkit/extractor.py`
- `epub_toolkit/translator.py`
- `epub_toolkit/reconstructor.py`

**Tests**

- Atributos se protegen, traducen y restauran.
- EPUB reconstruido conserva atributos traducidos.

**Impacto**

Traducciones más completas: imágenes con `alt` en español, elementos accesibles con `aria-label`, tooltips con `title`.

---

### Entrega 2 — Descomposición y reconstrucción completa del EPUB (DOM + CSS) (EPUB-017)

**Objetivo:** garantizar que el EPUB se pueda descomponer en todos sus elementos (DOM + CSS) y reconstruir exactamente igual, antes de continuar con mejoras de traducción.

**Contexto**

Actualmente el pipeline descomprime el EPUB completo y reconstruye copiando todos los archivos, pero la extracción solo representa textualmente los bloques traducibles. El usuario necesita una descomposición explícita del DOM completo y las hojas de estilo, con capacidad de reconstrucción idéntica.

**Qué se investiga e implementa**

1. Representar cada archivo XHTML como árbol DOM completo (no solo unidades traducibles).
2. Extraer y representar las hojas de estilo CSS asociadas (archivos `.css` y estilos inline).
3. Reconstruir el EPUB a partir de esa representación.
4. Comparar el EPUB original con el reconstruido usando los ejemplos de `libros/`.
5. Determinar qué partes no son idénticas y por qué (ej. namespaces, espacios en blanco, orden de atributos).

**Archivos esperados**

- `epub_toolkit/dom_extractor.py` (nuevo)
- `epub_toolkit/css_extractor.py` (nuevo)
- `epub_toolkit/dom_reconstructor.py` (nuevo)
- `tests/test_full_roundtrip.py` (nuevo)

**Tests**

- Para cada EPUB en `libros/`: descomponer, reconstruir y verificar que el contenido es equivalente.
- Comparación byte-a-byte opcional; como mínimo, equivalencia estructural (mismo número de archivos, mismos XHTML parseables, mismos recursos).

**Impacto**

Base sólida para cualquier manipulación futura del EPUB. Permite traducir sin perder estilo ni estructura.

---

### Entrega 3 — Fortalecer tests de LibreTranslate (EPUB-008)

**Objetivo:** mayor confianza en el motor local más usado.

**Qué se implementa**

- Tests de traducción por lote con múltiples textos.
- Tests de manejo de errores HTTP (404, 500, respuesta sin `translatedText`).
- Tests del parámetro `--delay`.
- Tests de uso con `--api-key`.

**Archivo**

- `tests/test_libretranslate_integration.py`

---

### Entrega 4 — Reintentos en traductores API (EPUB-009)

**Objetivo:** reducir fallos por errores de red o rate limits.

**Qué se implementa**

- `_post_json_with_retry` con reintentos exponenciales.
- Aplicar en `LibreTranslateTranslator`, `OpenAICompatibleTranslator` y `OllamaTranslator`.
- Opción `--retries` en el CLI.

**Dependencia:** EPUB-008.

---

### Entrega 5 — Validación de respuestas de LLM (EPUB-014)

**Objetivo:** evitar reconstruir EPUBs con placeholders rotos.

**Qué se implementa**

- `_collect_placeholder_ids` y `_validate_translated_texts` en `epub_toolkit/translator.py`.
- Reintento estricto (`strict=True`) uno a uno cuando un lote pierde placeholders.
- Fallback al texto original con `warnings.warn` si el reintento también falla.
- Validación aplicada también a atributos traducibles.

**Archivos**

- `epub_toolkit/translator.py`
- `tests/test_translator.py`

**Tests**

- Recuperación mediante reintento estricto.
- Advertencia y fallback al original cuando no se recupera.
- Validación correcta sin advertencias cuando los placeholders se conservan.
- Validación de atributos traducibles.

---

### Entrega 6 — Modo dry-run (EPUB-012)

**Objetivo:** permitir estimar costos antes de traducir.

**Qué se implementa**

- Opción `--dry-run` en el comando `translate` del CLI.
- Función `estimate_document()` que calcula unidades, caracteres y tokens estimados.
- No se traduce ni se escribe `translation_units.json` en dry-run.

**Archivos**

- `main.py`
- `epub_toolkit/translator.py`
- `tests/test_translator.py`

**Tests**

- Estimación correcta de unidades y caracteres incluyendo atributos.
- CLI dry-run no modifica el archivo de unidades.

---

### Entrega 7 — Barra de progreso (EPUB-011)

**Objetivo:** mejorar la experiencia visual en traducciones largas.

**Qué se implementa**

- Uso opcional de `tqdm` en `translate_document`.
- Barra de progreso por unidad con descripción "Traduciendo unidades".
- Fallback a progreso textual cuando `tqdm` no está instalado.
- `--quiet` desactiva toda salida de progreso.

**Archivos**

- `epub_toolkit/translator.py`
- `tests/test_translator.py`

**Tests**

- `progress=False` no produce salida.
- Fallback textual cuando `tqdm` no está disponible.

---

### Entrega 8 — Integración continua (EPUB-016)

**Objetivo:** prevenir regresiones automáticamente.

**Qué se implementa**

- Workflow `.github/workflows/ci.yml`.
- Ejecuta tests en Python 3.12 ante push y pull requests a `master`/`main`.
- Instala `lxml` como única dependencia.

**Archivos**

- `.github/workflows/ci.yml`

---

## Historial completado

- [x] **EPUB-001** — Aplicación base para traducir EPUBs  
  `commit: 36aba0e`

- [x] **EPUB-002** — Documentación inicial del proyecto  
  `commit: 36aba0e`

- [x] **EPUB-003** — Documentación completa en `docs/`  
  `sin commit`

- [x] **EPUB-004** — Motor genérico `openai-compatible`  
  `sin commit`

- [x] **EPUB-005** — Tests de integración para OpenAI-compatible  
  `sin commit`

- [x] **EPUB-006** — Registro de decisiones técnicas  
  `sin commit`

- [x] **EPUB-007** — Backlog del proyecto  
  `sin commit`

- [x] **EPUB-010** — Traducir atributos traducibles  
  `sin commit` — Entrega 1 completada.

- [x] **EPUB-017** — Descomposición y reconstrucción completa del EPUB (DOM + CSS)  
  `sin commit` — Entrega 2 completada. Se verificó roundtrip estructural sin discrepancias.

- [x] **EPUB-008** — Fortalecer tests de LibreTranslate  
  `sin commit` — Entrega 3 completada. Mock configurable y cobertura de errores.

- [x] **EPUB-009** — Reintentos en traductores API  
  `sin commit` — Entrega 4 completada. Backoff exponencial y tests con fallos transitorios.

- [x] **EPUB-014** — Validación de respuestas de LLM  
  PR #2 — Validación de placeholders, reintento estricto y fallback con advertencia.

- [x] **EPUB-012** — Modo dry-run  
  PR #3 — Estimación de volumen sin traducir ni escribir units.

- [x] **EPUB-011** — Barra de progreso visual  
  PR #4 — Barra `tqdm` opcional con fallback textual.

- [x] **EPUB-016** — Integración continua (GitHub Actions)  
  PR #5 — Workflow CI en Python 3.12.

- [x] **Agentes/skills de Kimi Code + segmentación LibreTranslate**  
  `commit: f8acb54` — Creados roles y skills para Kimi Code; implementada traducción segmentada en LibreTranslate para preservar placeholders; traducido `Developer.epub` a `output/Developer_es.epub`.

- [x] **Fix de espacios alrededor de placeholders en LibreTranslate**  
  `commit: 829cc62` — Conserva espacios entre texto plano y tags inline; evita artefactos como `sonpreentrenamientosobre`; re-traduce `Developer.epub`.

- [x] **Traducción de libros restantes con LibreTranslate**  
  Traducidos `Dissecting the Dark Web` y `Heavy.epub` a `output/Dissecting_the_Dark_Web_es.epub` y `output/Heavy_es.epub`.

---

## Decisiones técnicas

Ver [`docs/decisions.md`](docs/decisions.md).
