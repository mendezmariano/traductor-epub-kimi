# Arquitectura

Este documento describe cómo funciona internamente el Traductor de EPUB.

## Pipeline de alto nivel

```
EPUB original
     │
     ▼
┌─────────────┐
│ Deconstructor │  extrae el ZIP a un directorio
└──────┬──────┘
       ▼
┌─────────────┐
│  Extractor   │  identifica bloques traducibles y reemplaza tags inline por placeholders
└──────┬──────┘
       ▼
translation_units.json
       │
       ▼
┌─────────────┐
│  Translator  │  traduce por lotes agrupados por archivo XHTML
└──────┬──────┘
       ▼
┌─────────────┐
│ Reconstructor│  reinserta las traducciones y empaqueta el EPUB
└─────────────┘
       │
       ▼
 EPUB traducido
```

## 1. Deconstructor

Ubicación: `epub_toolkit/deconstructor.py`

La clase `Deconstructor` descomprime el EPUB (que no es más que un ZIP) en un directorio de trabajo, manteniendo la estructura original. También localiza el archivo `.opf` leyendo `META-INF/container.xml`.

Salida:

- Directorio `extracted/` con el contenido del EPUB.
- Ruta relativa del `.opf` para que el resto del pipeline sepa dónde está el manifest.

## 2. Extractor

Ubicación: `epub_toolkit/extractor.py`

La clase `Extractor` recorre los archivos XHTML listados en el manifest del `.opf` y construye unidades de traducción.

### ¿Qué es una unidad de traducción?

Una unidad es un bloque de texto contenido en un tag de bloque (`<p>`, `<h1>`, `<li>`, etc.) que cumple estas condiciones:

- El tag está en `BLOCK_TAGS`.
- No está en `SKIPPED_TAGS` (`<script>`, `<style>`, `<pre>`, `<svg>`, `<math>`, etc.).
- Contiene texto visible.
- Sus hijos elemento son todos tags inline (de `INLINE_TAGS`).

Si un bloque contiene tags anidados de bloque, no se convierte en una unidad; el extractor sigue recorriendo hasta encontrar bloques válidos.

### Placeholders para tags inline

Cuando una unidad contiene tags inline (`<b>`, `<i>`, `<span>`, `<a>`, `<br>`, etc.), el extractor los reemplaza por tokens del estilo `{ph0}`. Cada placeholder aparece dos veces en el texto: abre y cierra el tag. Los tags vacíos (void) aparecen una sola vez.

Ejemplo:

```html
<p>About <b>the Authors</b></p>
```

Se convierte en:

```json
{
  "id": "u1",
  "xpath": "/html[1]/body[1]/div[1]/section[1]/header[1]/h1[1]",
  "original": "About {ph0}the Authors{ph0}",
  "placeholders": {
    "{ph0}": {
      "tag": "b",
      "attrs": {},
      "self_closing": false
    }
  }
}
```

El extractor también deja un atributo temporal `data-tmp-id` en cada elemento block extraído. Este atributo permite al reconstructor localizar la unidad de forma robusta.

### Contexto por archivo

Para cada archivo XHTML se extrae un `context_title`: el primer `<h1>` o `<h2>` con texto, o el `<title>` del `<head>` como fallback. Ese título se incluye en los prompts enviados a los motores de LLM.

## 3. Modelos de datos

Ubicación: `epub_toolkit/models.py`

- `Placeholder`: representa un tag inline preservado.
- `TranslationUnit`: una unidad de traducción con su texto original, placeholders, atributos traducibles y traducción.
- `ExtractedFile`: conjunto de unidades extraídas de un archivo XHTML.
- `ExtractedDocument`: documento completo con todos los archivos y metadatos.

El documento se serializa a `translation_units.json` mediante `to_dict()` y se restaura con `from_dict()`.

## 4. Translator

Ubicación: `epub_toolkit/translator.py`

La traducción se realiza por lotes agrupados por archivo XHTML. Esto reduce el número de llamadas a la API y mejora la coherencia terminológica.

### Protección de placeholders

Antes de enviar texto a un servicio, los placeholders `{phN}` se reemplazan por marcadores `___PHN___` que los traductores suelen respetar. Después se restauran.

### Validación de respuestas de LLM

Tras recibir un lote traducido, `translate_batch_for_file` valida que cada texto conservé los mismos placeholders `{phN}` que el original. Si detecta placeholders perdidos:

1. Reintenta la traducción de ese texto en modo estricto (`strict=True`), que añade una advertencia explícita al prompt.
2. Si el reintento también falla, conserva el texto original y emite una advertencia con `warnings.warn`.

La misma validación se aplica a los atributos traducibles.

### Protección de glosario

Si se proporciona un glosario, sus términos se reemplazan por `___GLSN___` antes de la traducción y se restauran con su traducción después. Los términos se ordenan de más largo a más corto para evitar reemplazos parciales.

### Motores disponibles

- `DummyTranslator`: para pruebas. Envuelve el texto con `[ES]` y simula expansión.
- `LibreTranslateTranslator`: llama a `/translate` de una instancia de LibreTranslate.
- `OpenAITranslator`: usa `/chat/completions`. Envía prompts numerados y parsea respuestas numeradas.
- `OllamaTranslator`: usa `/api/generate` de Ollama local.

Todos los motores implementan la clase abstracta `Translator`.

### Prompts para LLM

El prompt de sistema (`_system_prompt`) instruye al modelo a:

- No traducir ni modificar marcadores `{phN}`, `___PHN___` ni `___GLSN___`.
- Mantener puntuación, formato y espacios.
- Respetar el factor de expansión si se proporciona.
- Usar el glosario si se proporciona.

El prompt de lote (`_batch_prompt`) enumera los textos y pide al modelo que responda con la misma cantidad de líneas numeradas.

### Progreso y dry-run

- `translate_document` muestra una barra de progreso con `tqdm` cuando está instalado; de lo contrario, imprime avance textual. `--quiet` desactiva cualquier salida.
- El CLI soporta `--dry-run` para estimar el volumen (unidades, caracteres y tokens aproximados) sin traducir ni escribir `translation_units.json`.

## 5. Reconstructor

Ubicación: `epub_toolkit/reconstructor.py`

La clase `Reconstructor`:

1. Copia el directorio extraído a un directorio temporal de trabajo.
2. Para cada archivo XHTML, localiza los elementos block por su `data-tmp-id`.
3. Reemplaza el contenido de cada elemento por la traducción, reconstruyendo los tags inline a partir de los placeholders.
4. Elimina los atributos `data-tmp-id` temporales.
5. Actualiza `<dc:language>` en el `.opf` si se proporcionó `--language`.
6. Empaqueta el directorio en un EPUB válido.

### Reconstrucción de tags inline

La función `_build_element` parsea el texto traducido y reconstruye el DOM usando una pila. Cuando encuentra un placeholder:

- Si es self-closing (`<br>`, `<img>`), crea el elemento y lo añade.
- Si el placeholder coincide con el tope de la pila, lo cierra.
- Si no, abre un nuevo elemento.

Esto permite manejar anidaciones como `{ph0}bold and {ph1}italic{ph1}{ph0}`.

## 6. Utilidades

Ubicación: `epub_toolkit/utils.py`

Funciones y constantes clave:

- `INLINE_TAGS`, `BLOCK_TAGS`, `SKIPPED_TAGS`, `VOID_TAGS`: conjuntos de tags usados por el extractor.
- `find_opf_path`: localiza el `.opf` desde `META-INF/container.xml`.
- `list_xhtml_files`: lista los archivos XHTML del manifest.
- `parse_xhtml` / `serialize_xhtml`: parseo y serialización respetando namespaces y declaración XML.
- `package_epub`: empaqueta el directorio en un EPUB/ZIP válido, colocando `mimetype` primero y sin compresión.
- `split_text_with_placeholders`: divide un texto en segmentos planos y placeholders.

## 7. Análisis y verificación de roundtrip

Ubicación: `epub_toolkit/analyzer.py`

El analizador estructural permite verificar que un EPUB reconstruido sea equivalente al original. Compara:

- Conjunto de archivos.
- DOM de cada XHTML: número de elementos, atributos y nodos de texto.
- Contenido de las hojas CSS.
- Hashes SHA-256 de recursos binarios (imágenes, fuentes).

El test `tests/test_full_roundtrip.py` ejecuta esta comparación para todos los EPUBs de `libros/`. Los resultados confirmaron que el pipeline actual preserva la estructura completa sin discrepancias.

## Decisiones de diseño

- **Lotes por archivo XHTML**: mejora coherencia y reduce llamadas a API.
- **Placeholders duplicados**: representan apertura y cierre de tags inline, lo que permite reconstruir la estructura original.
- **`data-tmp-id`**: permite reconstruir sin depender exclusivamente del XPath, que puede cambiar tras la traducción.
- **Sin dependencias de LLM**: se usa `urllib` para evitar instalar SDKs adicionales.
- **`lxml`**: biblioteca ya común en entornos Python; se usa para XML y HTML.
