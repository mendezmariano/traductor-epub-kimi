# Referencia de API

Documentación de las clases y funciones públicas del paquete `epub_toolkit`.

## Módulo `epub_toolkit.deconstructor`

### `Deconstructor`

```python
class Deconstructor(epub_path, output_dir, clean=True)
```

Descompone un EPUB en un directorio de trabajo.

**Parámetros**

- `epub_path` (`str | Path`): ruta al EPUB de entrada.
- `output_dir` (`str | Path`): directorio donde se extraerá el contenido.
- `clean` (`bool`): si es `True`, borra `output_dir` antes de extraer.

**Métodos**

- `deconstruct() -> tuple[Path, str]`
  - Extrae el EPUB y devuelve `(directorio_extraído, ruta_relativa_opf)`.

---

## Módulo `epub_toolkit.extractor`

### `Extractor`

```python
class Extractor(extracted_dir, opf_path)
```

Extrae unidades de traducción de los archivos XHTML de un EPUB descomprimido.

**Parámetros**

- `extracted_dir` (`str | Path`): directorio con el EPUB extraído.
- `opf_path` (`str`): ruta relativa del `.opf` dentro del directorio extraído.

**Métodos**

- `extract(source_epub) -> ExtractedDocument`
  - Recorre los XHTML, genera las unidades de traducción y devuelve un `ExtractedDocument`.
  - Persiste atributos `data-tmp-id` en los XHTML para el reconstructor.

---

## Módulo `epub_toolkit.reconstructor`

### `Reconstructor`

```python
class Reconstructor(extracted_dir, translation_units_path)
```

Reconstruye un EPUB a partir de un directorio extraído y un JSON de unidades traducidas.

**Parámetros**

- `extracted_dir` (`str | Path`): directorio con el EPUB extraído.
- `translation_units_path` (`str | Path`): ruta a `translation_units.json`.

**Métodos**

- `reconstruct(output_epub, update_language=None) -> Path`
  - Genera el EPUB reconstruido en `output_epub`.
  - Si `update_language` no es `None`, actualiza `<dc:language>` en el `.opf`.
  - Devuelve la ruta del EPUB generado.

---

## Módulo `epub_toolkit.models`

### `Placeholder`

```python
@dataclass
class Placeholder(tag, attrs, self_closing=False)
```

Representa un tag inline preservado dentro de una unidad de traducción.

**Atributos**

- `tag` (`str`): nombre del tag HTML.
- `attrs` (`dict[str, str]`): atributos del tag.
- `self_closing` (`bool`): indica si es un tag vacío (`<br>`, `<img>`, etc.).

### `TranslationUnit`

```python
@dataclass
class TranslationUnit(unit_id, xpath, original, placeholders=None,
                      translatable=True, translation=None, translatable_attrs=None)
```

Unidad de texto traducible extraída de un XHTML.

**Atributos**

- `unit_id` (`str`): identificador único, por ejemplo `"u1"`.
- `xpath` (`str`): XPath de referencia del elemento block.
- `original` (`str`): texto original con placeholders.
- `placeholders` (`dict[str, Placeholder]`): mapa de placeholder a tag inline.
- `translatable` (`bool`): indica si debe traducirse.
- `translation` (`str | None`): traducción resultante.
- `translatable_attrs` (`dict[str, dict[str, str]]`): atributos traducibles del elemento.
- `translated_attrs` (`dict[str, dict[str, str]]`): atributos traducidos. Tiene la misma estructura que `translatable_attrs`.

### `ExtractedFile`

```python
@dataclass
class ExtractedFile(path, units=None, context_title="")
```

Unidades extraídas de un archivo XHTML concreto.

**Atributos**

- `path` (`str`): ruta relativa del XHTML.
- `units` (`list[TranslationUnit]`): unidades del archivo.
- `context_title` (`str`): título representativo usado como contexto.

### `ExtractedDocument`

```python
@dataclass
class ExtractedDocument(source_epub, language, files)
```

Documento completo con todas las unidades extraídas de un EPUB.

**Atributos**

- `source_epub` (`str`): ruta al EPUB original.
- `language` (`str`): idioma declarado del EPUB.
- `files` (`dict[str, ExtractedFile]`): mapa de ruta XHTML a `ExtractedFile`.

**Métodos**

- `to_dict() -> dict[str, Any]`: serializa el documento a diccionario.
- `from_dict(data) -> ExtractedDocument`: deserializa un diccionario.

---

## Módulo `epub_toolkit.translator`

### `Translator`

```python
class Translator(ABC)
```

Clase base abstracta para motores de traducción.

**Métodos**

- `translate(text, source_lang, target_lang) -> str`
  - Traduce un texto individual.
- `translate_batch(texts, source_lang, target_lang, context_title="", glossary=None) -> list[str]`
  - Traduce un lote de textos. La implementación por defecto traduce uno a uno.

### `DummyTranslator`

```python
class DummyTranslator(expansion=1.25, expansion_hint=None)
```

Traductor de prueba. Envuelve el texto con `[<IDIOMA_DESTINO>]` y repite el texto según el factor de expansión.

### `LibreTranslateTranslator`

```python
class LibreTranslateTranslator(base_url="https://libretranslate.de",
                               api_key=None, delay=0.0, expansion_hint=None,
                               retries=3)
```

Traductor mediante LibreTranslate. `retries` controla los reintentros ante errores transitorios (5xx, 429, errores de conexión).

### `OpenAICompatibleTranslator`

```python
class OpenAICompatibleTranslator(api_key, base_url="https://api.openai.com/v1",
                                 model="gpt-4o-mini", temperature=0.3,
                                 expansion_hint=None, retries=3)
```

Traductor mediante cualquier API compatible con el endpoint `/chat/completions` de OpenAI (OpenAI, Groq, Mistral, etc.). `retries` controla los reintentros ante errores transitorios.

### `OpenAITranslator`

Alias de `OpenAICompatibleTranslator` mantenido por compatibilidad con versiones anteriores.

### `OllamaTranslator`

```python
class OllamaTranslator(base_url="http://localhost:11434",
                       model="llama3.2", temperature=0.3, expansion_hint=None,
                       retries=3)
```

Traductor mediante Ollama ejecutándose localmente. `retries` controla los reintentros ante errores transitorios.

### `create_translator`

```python
create_translator(engine, **kwargs) -> Translator
```

Factoría de traductores. `engine` puede ser `"dummy"`, `"libretranslate"`, `"openai"`, `"openai-compatible"` o `"ollama"`.

### Funciones de traducción de documentos

- `translate_unit(translator, unit, source_lang, target_lang, glossary=None) -> str`
  - Traduce una única `TranslationUnit`.
- `translate_batch_for_file(translator, file, source_lang, target_lang, glossary=None) -> list[str]`
  - Traduce todas las unidades traducibles de un `ExtractedFile`.
- `translate_document(translator, document, source_lang="en", target_lang="es", progress=True, glossary=None) -> None`
  - Traduce todas las unidades de un `ExtractedDocument`, guardando el resultado en cada unidad.

---

## Módulo `epub_toolkit.utils`

### Constantes de tags

- `INLINE_TAGS`: tags inline preservados dentro de una unidad.
- `BLOCK_TAGS`: tags que definen una unidad de traducción.
- `SKIPPED_TAGS`: tags cuyo contenido no se traduce.
- `VOID_TAGS`: tags vacíos (self-closing).
- `TRANSLATABLE_ATTRS`: atributos que pueden contener texto traducible.

### Funciones principales

- `find_opf_path(extracted_dir) -> str`
  - Lee `META-INF/container.xml` y devuelve la ruta relativa del `.opf`.

- `list_xhtml_files(extracted_dir, opf_path=None) -> list[str]`
  - Devuelve las rutas relativas de los XHTML listados en el manifest.

- `opf_dir(opf_path) -> str`
  - Devuelve el directorio base del `.opf`.

- `parse_xhtml(path) -> etree._ElementTree`
  - Parsea un XHTML respetando namespaces; usa `lxml.html` como fallback.

- `serialize_xhtml(tree, path, xml_declaration=None) -> None`
  - Serializa un árbol XHTML respetando la declaración XML y los finales de línea del archivo original.

- `package_epub(source_dir, output_epub) -> None`
  - Empaqueta un directorio extraído en un EPUB válido, colocando `mimetype` primero y sin compresión.

- `make_placeholder(index) -> str`
  - Genera un token `{phN}`.

- `split_text_with_placeholders(text) -> list[tuple[str, str | None]]`
  - Divide un texto en segmentos de texto plano y placeholders.

- `clean_text(text) -> str`
  - Normaliza espacios en blanco de un texto extraído.

---

## Módulo `epub_toolkit.analyzer`

### `analyze_epub(epub_path) -> dict[str, Any]`

Extrae el EPUB a un directorio temporal y devuelve un resumen estructural completo:

- Lista de archivos con tipo y tamaño.
- Análisis de cada XHTML: elementos, atributos, nodos de texto, estilos inline.
- Análisis de cada CSS: tamaño, hash SHA-256, cantidad de líneas.
- Análisis de archivos binarios: tamaño y hash SHA-256.

### `compare_epubs(original_path, rebuilt_path) -> dict[str, Any]`

Compara dos EPUBs y devuelve un reporte con diferencias estructurales:

- Archivos faltantes o sobrantes.
- Diferencias en elementos, atributos o nodos de texto de XHTML.
- Diferencias de contenido en CSS.
- Diferencias de hash en recursos binarios.

Campos del resultado:

- `differences`: lista de diferencias detectadas.
- `difference_count`: cantidad de diferencias.
- `equivalent`: `True` si no hay diferencias.
