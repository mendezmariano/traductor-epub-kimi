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

## Estado actual

- **Rama activa:** `feature/entregas-010-017-008-009`
- **PR abierto:** https://github.com/mendezmariano/traductor-epub-kimi/pull/1
- **Entregas completadas:** 4 de 8
- **Tests:** 45 tests OK

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
- Actualización del idioma en el archivo `.opf`.
- Tests de roundtrip que verifican la validez del EPUB reconstruido.

## Tests

```bash
python3 -m unittest discover tests -v
```
