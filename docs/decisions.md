# Registro de decisiones

Este documento registra las decisiones técnicas y de diseño tomadas en el proyecto. Se actualiza cada vez que se introduce un cambio arquitectónico significativo.

## DEC-001: Lenguaje y versión de Python

**Decisión:** Usar Python 3.12+ con anotaciones de tipo.

**Motivación:**
- Las anotaciones de tipo mejoran la mantenibilidad y permiten usar herramientas como `mypy` en el futuro.
- `from __future__ import annotations` simplifica las referencias a clases no aún definidas.

**Consecuencias:**
- El proyecto no es compatible con Python 3.11 o anteriores.

---

## DEC-002: Biblioteca para procesar XHTML

**Decisión:** Usar `lxml` para parsear y serializar XHTML.

**Motivación:**
- `lxml` es robusta, maneja namespaces y es común en entornos Python.
- Permite trabajar tanto con XML bien formado como con HTML más permisivo mediante fallback a `lxml.html`.

**Consecuencias:**
- `lxml` es la única dependencia obligatoria del proyecto.

---

## DEC-003: Preservación de tags inline con placeholders

**Decisión:** Reemplazar tags inline (`<b>`, `<i>`, `<span>`, etc.) por tokens del estilo `{phN}` al extraer el texto.

**Motivación:**
- Los servicios de traducción no deben modificar el marcado HTML.
- Representar apertura y cierre con el mismo token simplifica la reconstrucción posterior.

**Consecuencias:**
- El traductor recibe texto plano con marcadores y debe devolverlos intactos.
- Se requiere lógica de protección/restauración si el servicio altera los marcadores.

---

## DEC-004: Traducción por lotes agrupada por archivo XHTML

**Decisión:** Agrupar las unidades de traducción por archivo XHTML y enviarlas juntas al traductor.

**Motivación:**
- Reduce el número de llamadas a la API.
- Mejora la coherencia terminológica dentro de un mismo capítulo o sección.
- Permite incluir el título del capítulo como contexto en los prompts de LLM.

**Consecuencias:**
- Cada motor implementa `translate_batch`; por defecto traduce uno a uno.
- Si un lote falla, se pierde todo el lote (sin lógica de reintento parcial aún).

---

## DEC-005: Dependencias mínimas para motores de traducción

**Decisión:** Usar `urllib` en lugar de SDKs de terceros para llamar a servicios de traducción.

**Motivación:**
- Evita instalar dependencias adicionales (`openai`, `requests`, etc.).
- Reduce la superficie de mantenimiento y conflictos de versiones.

**Consecuencias:**
- Se implementa a manejo de headers, serialización JSON y errores HTTP.
- No hay funcionalidades avanzadas del SDK como streaming o reintentos automáticos.

---

## DEC-006: Motor genérico OpenAI-compatible

**Decisión:** Crear `OpenAICompatibleTranslator` como motor genérico para cualquier API que use el endpoint `/chat/completions` de OpenAI.

**Motivación:**
- Permite usar OpenAI, Groq, Mistral y otros proveedores compatibles sin cambiar código.
- El usuario solo necesita `--base-url`, `--model` y `--api-key`.

**Consecuencias:**
- `OpenAITranslator` se mantiene como alias para no romper compatibilidad.
- Se requiere que el usuario conozca el nombre exacto del modelo en el proveedor elegido.

---

## DEC-007: Soporte de LibreTranslate como opción local

**Decisión:** Soportar LibreTranslate como motor autoalojado, además de las instancias públicas.

**Motivación:**
- Para EPUBs completos, una instancia local evita límites y costos de APIs públicas.
- El endpoint `/translate` es simple y estándar.

**Consecuencias:**
- Se documenta el uso con Docker.
- Las instancias públicas (como `https://es.libretranslate.com/`) suelen requerir API key.

---

## DEC-008: Almacenamiento del estado de traducción en JSON

**Decisión:** Guardar las unidades extraídas y sus traducciones en `translation_units.json`.

**Motivación:**
- Permite revisar, editar o auditar las traducciones antes de reconstruir el EPUB.
- Facilita la traducción incremental y la recuperación ante fallos.

**Consecuencias:**
- El archivo puede ser grande para EPUBs extensos.
- Cualquier cambio en el formato requiere migración.

---

## DEC-009: Identificación robusta de unidades con `data-tmp-id`

**Decisión:** Marcar cada elemento block extraído con un atributo temporal `data-tmp-id`.

**Motivación:**
- El XPath puede volverse inestable después de traducir o modificar el documento.
- Un ID temporal permite localizar la unidad de forma determinista durante la reconstrucción.

**Consecuencias:**
- El atributo se elimina del EPUB final.
- Los XHTML extraídos contienen atributos temporales hasta la reconstrucción.

---

## DEC-010: Glosario protegido con marcadores

**Decisión:** Proteger los términos del glosario con marcadores `___GLSN___` antes de enviarlos al traductor.

**Motivación:**
- Garantiza traducciones consistentes de términos técnicos.
- Funciona con todos los motores (LibreTranslate, OpenAI-compatible, Ollama, dummy).

**Consecuencias:**
- Si un término del glosario aparece dentro de un tag inline, también se traduce según el glosario.

---

## DEC-011: Preservación completa del EPUB durante la reconstrucción

**Decisión:** Copiar todo el directorio extraído durante la reconstrucción y modificar únicamente los XHTML y atributos traducibles.

**Motivación:**
- Garantiza que CSS, fuentes, imágenes y otros recursos no se alteren ni pierdan.
- Evita tener que representar explícitamente cada elemento del DOM; el ZIP ya es la representación completa.

**Verificación:**
- Se implementó `epub_toolkit/analyzer.py` para comparar EPUBs originales y reconstruidos.
- El test `tests/test_full_roundtrip.py` verifica equivalencia estructural para todos los EPUBs de `libros/`.
- No se detectaron discrepancias en elementos, atributos, nodos de texto, CSS ni recursos binarios.

**Consecuencias:**
- No se requiere un modelo explícito del DOM completo ni de las CSS.
- Cualquier manipulación futura debe limitarse a modificar XHTML ya extraídos.
