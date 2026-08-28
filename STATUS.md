> **Propósito:** Este archivo permite retomar el proyecto después de un `/clear` o de cerrar la sesión. Contiene el estado actual, la rama activa, el PR abierto y el próximo paso recomendado.

# Estado del proyecto

## Rama activa

```
master
```

## Pull Requests abiertos

| PR | Entrega | Rama | URL |
|----|---------|------|-----|
| #2 | EPUB-014 — Validación de respuestas de LLM | `feature/EPUB-014-llm-validation` | https://github.com/mendezmariano/traductor-epub-kimi/pull/2 |
| #3 | EPUB-012 — Modo dry-run | `feature/EPUB-012-dry-run` | https://github.com/mendezmariano/traductor-epub-kimi/pull/3 |
| #4 | EPUB-011 — Barra de progreso visual | `feature/EPUB-011-progress-bar` | https://github.com/mendezmariano/traductor-epub-kimi/pull/4 |
| #5 | EPUB-016 — Integración continua (GitHub Actions) | `feature/EPUB-016-ci` | https://github.com/mendezmariano/traductor-epub-kimi/pull/5 |

> El PR #1 (entregas 1–4) ya fue mergeado a `master`.

## Entregas completadas

| Entrega | ID | Tarea | Commit/PR |
|---------|----|-------|-----------|
| 1 | EPUB-010 | Traducir atributos traducibles (`alt`, `title`, `aria-label`, `placeholder`) | `11789d7` |
| 2 | EPUB-017 | Descomposición y reconstrucción completa del EPUB (DOM + CSS) | `2ffb5a9` |
| 3 | EPUB-008 | Fortalecer tests de LibreTranslate | `6ade166` |
| 4 | EPUB-009 | Reintentos en traductores API | `606dca4` |
| 5 | EPUB-014 | Validación de respuestas de LLM | PR #2 |
| 6 | EPUB-012 | Modo dry-run | PR #3 |
| 7 | EPUB-011 | Barra de progreso visual | PR #4 |
| 8 | EPUB-016 | Integración continua (GitHub Actions) | PR #5 |
| — | — | Agentes/skills de Kimi Code y segmentación para LibreTranslate | `f8acb54` |

## Entregas pendientes

Ninguna. Todas las entregas planificadas están implementadas y pendientes de merge.

Ver detalles completos en [`BACKLOG.md`](BACKLOG.md).

## Próximo paso recomendado

Revisar y mergear los PRs #2 a #5. Después del merge, ejecutar:

```bash
python3 -m unittest discover tests -v
```

## Cómo verificar el estado actual

Ejecuta el script de resumen:

```bash
bash scripts/resume.sh
```

Esto muestra la rama activa, el PR abierto, los últimos commits, el estado del proyecto y ejecuta los tests.

También puedes hacerlo manualmente:

```bash
# Cambiar a la rama activa si no estás en ella
git checkout feature/entregas-010-017-008-009

# Ver commits recientes
git log --oneline -5

# Ver PR abierto
gh pr view 1

# Ejecutar tests
python3 -m unittest discover tests -v
```

## Tests actuales

```bash
python3 -m unittest discover tests -v
```

Última verificación: **59 tests OK** en `master`.

## Notas importantes

- El PR #1 (entregas 1–4) ya fue mergeado a `master`.
- Las entregas 5–8 están en PRs separados (#2 a #5) listos para revisión/merge.
- Cada rama de entrega pasa `python3 -m unittest discover tests -v`.
- El workflow `.github/workflows/ci.yml` ejecutará los tests automáticamente en push/PR a `master`/`main`.
- Commit `f8acb54` agrega agentes/skills de Kimi Code y segmentación para LibreTranslate; traduce `Developer.epub` localmente a `output/Developer_es.epub`.
- Cambios listos para commitear:
  - `epub_toolkit/translator.py`: añade motores `DeepLTranslator`, `AzureTranslator`, `GoogleTranslator`, `FallbackTranslator` y `QuotaExceededError`.
  - `main.py`: soporta `--engine deepl|azure|google`, `--region` y `--fallback-config`.
  - Tests de integración para DeepL, Azure, Google y fallback.
  - Documentación actualizada (`docs/`, `skills/`, `README.md`, `.agents/`).
  - Tests: 90 OK.




