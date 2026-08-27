# Traductor de EPUB

Aplicación Python para traducir libros EPUB preservando el marcado HTML inline.

## ¿Qué hace?

Este proyecto descompone un EPUB en sus partes, extrae el texto traducible reemplazando tags inline (`<b>`, `<i>`, `<span>`, `<a>`, etc.) por placeholders, traduce el contenido y reconstruye el EPUB final.

## Instalación rápida

Requisitos:

- Python 3.12+
- `lxml`

```bash
pip install lxml
```

## Uso rápido

```bash
# 1. Descomponer
python3 main.py deconstruct libros/Developer.epub --output output/Developer

# 2. Traducir (motor dummy para probar)
python3 main.py translate output/Developer --engine dummy --expansion 1.25

# 3. Reconstruir
python3 main.py reconstruct output/Developer --output output/Developer_es.epub --language es
```

## Documentación

- [Guía de usuario](docs/user-guide.md) — instalación, flujo de trabajo, motores de traducción, glosarios y solución de problemas.
- [Arquitectura](docs/architecture.md) — pipeline interno, modelos de datos y decisiones de diseño.
- [Referencia de API](docs/api-reference.md) — clases y funciones públicas de `epub_toolkit`.
- [Guía de desarrollo](docs/development.md) — tests, convenciones y cómo extender el proyecto.
- [Decisiones técnicas](docs/decisions.md) — registro de decisiones de diseño y arquitectura.
- [Backlog](BACKLOG.md) — historial, tareas pendientes y próximas mejoras.
- [Estado actual](STATUS.md) — contexto para retomar el proyecto después de un `/clear`.

## Agentes y skills de Kimi Code

El proyecto incluye roles y skills para que Kimi Code trabaje de forma consistente:

- [`AGENTS.md`](AGENTS.md) — reglas generales para todos los agentes.
- [`.agents/epub-translator.md`](.agents/epub-translator.md) — rol de traducción de EPUBs.
- [`.agents/quality-reviewer.md`](.agents/quality-reviewer.md) — rol de revisión de calidad y tests.
- [`.agents/release-manager.md`](.agents/release-manager.md) — rol de gestión de releases.
- [`skills/epub-pipeline.md`](skills/epub-pipeline.md) — skill para ejecutar el pipeline completo.
- [`skills/glossary.md`](skills/glossary.md) — skill para mantener y usar glosarios técnicos.
- [`skills/run-tests.md`](skills/run-tests.md) — skill para ejecutar tests.
- [`skills/create-release.md`](skills/create-release.md) — skill para preparar releases.

## Estado actual

- **Rama activa:** `master`
- **PRs abiertos:** #2, #3, #4, #5 (entregas 5–8)
- **Entregas completadas:** 8 de 8
- **Tests:** 59 tests OK

Para retomar el proyecto después de un `/clear`, ejecuta:

```bash
bash scripts/resume.sh
```

Ver [`STATUS.md`](STATUS.md) para más detalles.

## Funcionalidades principales

- Traducción con múltiples motores: `dummy`, `LibreTranslate`, `openai-compatible` (OpenAI, Groq, Mistral, etc.) y `Ollama`.
- Traducción por lotes agrupada por archivo XHTML para mejorar coherencia y reducir llamadas a API.
- Soporte de glosarios para términos técnicos consistentes.
- Preservación de tags inline mediante placeholders numerados.
- Segmentación de texto plano para LibreTranslate, evitando que el servicio destruya los marcadores de placeholders.
- Validación de respuestas de LLM: reintento estricto y fallback al original si se pierden placeholders.
- Modo `--dry-run` para estimar volumen antes de traducir.
- Barra de progreso visual (`tqdm`) con fallback a texto plano.
- Actualización del idioma en el archivo `.opf`.
- Tests de roundtrip que verifican la validez del EPUB reconstruido.
- Integración continua con GitHub Actions.

## Tests

```bash
python3 -m unittest discover tests -v
```
