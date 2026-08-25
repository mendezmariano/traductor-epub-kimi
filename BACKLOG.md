> **Nota:** Este backlog se actualiza por cada entrega. Los cambios sin commitear se marcan con el estado actual correspondiente.

# Backlog del proyecto

## Resumen visual

| Estado | Cantidad |
|--------|----------|
| Completado | 11 |
| En progreso | 0 |
| Por hacer | 6 |

---

## Plan de entregas

| Entrega | ID | Tarea | Prioridad | Estado |
|---------|----|-------|-----------|--------|
| 1 | EPUB-010 | Traducir atributos traducibles (`alt`, `title`, `aria-label`, `placeholder`) | Alta | `DONE` |
| 2 | EPUB-017 | Descomposición y reconstrucción completa del EPUB (DOM + CSS) | Alta | `DONE` |
| 3 | EPUB-008 | Fortalecer tests de LibreTranslate | Media | `DONE` |
| 4 | EPUB-009 | Implementar reintentos en traductores API | Media | `DONE` |
| 5 | EPUB-014 | Validación de respuestas de LLM | Media | `READY` |
| 6 | EPUB-012 | Modo dry-run | Baja | `READY` |
| 7 | EPUB-011 | Barra de progreso visual | Baja | `IN REVIEW` |
| 8 | EPUB-016 | Integración continua (GitHub Actions) | Baja | `IN REVIEW` |

---

## Estado del desarrollo

- **Rama activa:** `feature/entregas-010-017-008-009`
- **Pull Request abierto:** https://github.com/mendezmariano/traductor-epub-kimi/pull/1
- **Última verificación de tests:** 45 tests OK.

## Cómo continuar

1. Si el PR #1 aún no está mergeado, revisarlo o mergearlo.
2. Crear una nueva rama para la siguiente entrega, por ejemplo:
   ```bash
   git checkout master
   git pull origin master
   git checkout -b feature/EPUB-014-validacion-llm
   ```
3. Implementar **EPUB-014 — Validación de respuestas de LLM**.
4. Ejecutar tests: `python3 -m unittest discover tests -v`.
5. Actualizar este backlog y `STATUS.md`.
6. Commitear, pushear y abrir un nuevo PR.

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

- Verificar que la respuesta conserve todos los placeholders.
- Fallback automático a traducción uno a uno si falla.
- Registrar advertencias.

---

### Entrega 6 — Modo dry-run (EPUB-012)

**Objetivo:** permitir estimar costos antes de traducir.

**Qué se implementa**

- Opción `--dry-run` en `translate`.
- Contar unidades y estimar caracteres/tokens.
- No escribir `translation_units.json` si está activo.

---

### Entrega 7 — Barra de progreso (EPUB-011)

**Objetivo:** mejorar la experiencia visual en traducciones largas.

**Qué se implementa**

- Integrar `tqdm` como dependencia opcional.
- Mostrar barra de progreso por archivo/unidad.
- Fallback a texto plano si no está instalado.

---

### Entrega 8 — Integración continua (EPUB-016)

**Objetivo:** prevenir regresiones automáticamente.

**Qué se implementa**

- Workflow de GitHub Actions en Python 3.12.
- Disparadores en push a `main` y pull requests.

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

---

## Decisiones técnicas

Ver [`docs/decisions.md`](docs/decisions.md).
