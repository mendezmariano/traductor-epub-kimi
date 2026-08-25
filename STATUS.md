> **Propósito:** Este archivo permite retomar el proyecto después de un `/clear` o de cerrar la sesión. Contiene el estado actual, la rama activa, el PR abierto y el próximo paso recomendado.

# Estado del proyecto

## Rama activa

```
feature/entregas-010-017-008-009
```

## Pull Request abierto

- **URL:** https://github.com/mendezmariano/traductor-epub-kimi/pull/1
- **Título:** Entregas 1-4: atributos traducibles, roundtrip DOM+CSS, tests LibreTranslate y reintentos API
- **Estado:** abierto
- **Base:** `master`

## Entregas completadas

| Entrega | ID | Tarea | Commit |
|---------|----|-------|--------|
| 1 | EPUB-010 | Traducir atributos traducibles (`alt`, `title`, `aria-label`, `placeholder`) | `11789d7` |
| 2 | EPUB-017 | Descomposición y reconstrucción completa del EPUB (DOM + CSS) | `2ffb5a9` |
| 3 | EPUB-008 | Fortalecer tests de LibreTranslate | `6ade166` |
| 4 | EPUB-009 | Reintentos en traductores API | `606dca4` |

## Entregas pendientes

| Entrega | ID | Tarea | Prioridad | Estado |
|---------|----|-------|-----------|--------|
| 5 | EPUB-014 | Validación de respuestas de LLM | Media | `READY` |
| 6 | EPUB-012 | Modo dry-run | Baja | `READY` |
| 7 | EPUB-011 | Barra de progreso visual | Baja | `IN REVIEW` |
| 8 | EPUB-016 | Integración continua (GitHub Actions) | Baja | `IN REVIEW` |

Ver detalles completos en [`BACKLOG.md`](BACKLOG.md).

## Próximo paso recomendado

**Entrega 5 — EPUB-014: Validación de respuestas de LLM**

Objetivo: evitar reconstruir EPUBs con placeholders rotos.

Tareas:

1. Verificar que la respuesta de un LLM conserve todos los placeholders.
2. Si no, aplicar fallback automático a traducción uno a uno con prompt más estricto.
3. Registrar advertencias cuando se detecten placeholders perdidos.
4. Añadir tests con mock que devuelva respuesta sin placeholders.

Archivo principal: `epub_toolkit/translator.py`.

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

Última verificación: **45 tests OK**.

## Notas importantes

- Los cambios de las entregas 1-4 están en la rama `feature/entregas-010-017-008-009` y aún no se mergearon a `master`.
- El PR #1 está abierto y listo para revisión/merge.
- Antes de continuar con la entrega 5, conviene mergear el PR o seguir trabajando sobre la misma rama.
- Si se mergea el PR, crear una nueva rama para la entrega 5 (ej. `feature/EPUB-014-validacion-llm`).
