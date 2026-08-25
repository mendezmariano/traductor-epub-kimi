# Traductor de EPUB

Aplicación Python para descomponer EPUBs en sus componentes, extraer el texto
traducible preservando los tags HTML inline, y reconstruir el EPUB una vez
proporcionadas las traducciones.

## Funcionalidad actual

- **Descomponer**: extrae un EPUB a un directorio de trabajo, genera un
  `translation_units.json` con las unidades de traducción.
- **Extraer**: recorre los XHTML, identifica bloques de texto traducibles y
  reemplaza los tags inline (`<b>`, `<i>`, `<span>`, `<a>`, etc.) por
  placeholders numerados para que el traductor no los toque.
- **Traducir**: soporta varios motores:
  - `dummy` (pruebas)
  - `libretranslate` (API REST)
  - `openai` (OpenAI y compatibles: Groq, Mistral, etc.)
  - `ollama` (LLM local)
- **Reconstruir**: lee el JSON de unidades (campo `translation`) y vuelve a
  empaquetar el EPUB, reinsertando los tags inline en su posición original.

## Requisitos

- Python 3.12+
- `lxml` (ya suele estar disponible; si no, instalar con `pip install lxml`)

## Uso

```bash
# 1. Descomponer un EPUB
python3 main.py deconstruct libros/Developer.epub --output output/Developer

# Genera:
#   output/Developer/extracted/         # contenido del EPUB
#   output/Developer/translation_units.json

# 2. Traducir
#
# Opción A: motor dummy (para pruebas; simula expansión del ~25 %)
python3 main.py translate output/Developer --engine dummy --expansion 1.25

# Opción B: LibreTranslate
# Nota: las instancias públicas suelen requerir API key. Para traducir EPUBs
# completos se recomienda levantar una instancia local:
#   docker run -it -p 5000:5000 libretranslate/libretranslate
python3 main.py translate output/Developer --engine libretranslate \
  --source en --target es \
  --base-url http://localhost:5000 \
  --api-key $LIBRETRANSLATE_API_KEY \
  --delay 0.5

# Opción C: OpenAI o compatible (Groq, Mistral, etc.)
python3 main.py translate output/Developer --engine openai \
  --source en --target es \
  --api-key $OPENAI_API_KEY \
  --base-url https://api.openai.com/v1 \
  --model gpt-4o-mini \
  --temperature 0.3 \
  --expansion 1.25

# Opción D: Ollama (LLM local)
python3 main.py translate output/Developer --engine ollama \
  --source en --target es \
  --base-url http://localhost:11434 \
  --model llama3.2 \
  --temperature 0.3 \
  --expansion 1.25

# Opción E: editar output/Developer/translation_units.json manualmente y
# rellenar el campo "translation" de cada unidad.

# 3. Reconstruir el EPUB
python3 main.py reconstruct output/Developer --output output/Developer_es.epub --language es
```

## Formato del JSON de unidades

Cada unidad tiene este aspecto:

```json
{
  "id": "u1",
  "xpath": "/html[1]/body[1]/div[1]/section[1]/header[1]/h1[1]",
  "original": "{ph0}{ph0}About the Authors",
  "placeholders": {
    "{ph0}": {
      "tag": "span",
      "attrs": { "aria-label": "vii", "id": "pgvii", "role": "doc-pagebreak" },
      "self_closing": false
    }
  },
  "translatable": true,
  "translation": null
}
```

Los placeholders aparecen dos veces en el texto: abren y cierran el tag inline
al que representan. El traductor debe conservarlos tal cual.

## Traducción por lotes con contexto

La traducción se realiza agrupando las unidades por archivo XHTML (capítulo o
sección). Esto mejora la coherencia terminológica y reduce el número de
llamadas a la API.

Para cada archivo se extrae automáticamente un `context_title` (el primer
`<h1>`, `<h2>` o `<title>` del XHTML) y se incluye en el prompt enviado a
OpenAI/Ollama. LibreTranslate recibe el lote completo en el campo `q`.

## Glosario de términos técnicos

Puedes definir un glosario para forzar traducciones consistentes de términos
clave. El glosario funciona con todos los motores (LibreTranslate, OpenAI,
Ollama y dummy).

Crea un archivo `glossary.json`:

```json
{
  "large language model": "gran modelo de lenguaje",
  "prompt": "instrucción",
  "fine-tuning": "ajuste fino",
  "token": "token"
}
```

Y úsalo al traducir:

```bash
python3 main.py translate output/Developer --engine libretranslate \
  --base-url http://localhost:5000 \
  --glossary glossary.json
```

Los términos se protegen antes de enviar el texto al traductor y se restauran
con su traducción al final, incluso cuando aparecen dentro de tags inline como
`<b>prompt</b>`.

## Tests

```bash
# Todos los tests
python3 -m unittest discover tests -v

# Solo roundtrip
python3 -m unittest tests.test_roundtrip -v
```

El test de roundtrip descompone y reconstruye cada EPUB de `libros/`,
verificando que el resultado sea un ZIP válido con `mimetype` sin compresión
al inicio y que todos los XHTML sean parseables.

## Notas

- El español suele expandir el texto ~25 %. Todos los motores reciben el
  parámetro `--expansion` como hint; para `dummy` controla la repetición, y
  para LLMs se incluye en el prompt de sistema.
- Antes de enviar texto a un servicio de traducción, los placeholders como
  `{ph0}` se reemplazan por marcadores (`___PH0___`) y se restauran después,
  para que el traductor no modifique los tags inline.
- El prompt de sistema para LLM incluye la instrucción explícita de no traducir
  los marcadores `{phN}` y de mantener el formato.
- La traducción por lotes agrupa unidades por archivo XHTML e incluye el
  título del capítulo como contexto, mejorando la coherencia terminológica.
- El glosario se aplica a todos los motores protegiendo los términos con
  marcadores antes de la traducción y restaurándolos después.
- El extractor deja atributos `data-tmp-id` en los XHTML extraídos para poder
  reconstruir cada unidad de forma robusta. Se eliminan automáticamente al
  reconstruir.
- Los motores de LLM se comunican mediante `urllib` (sin dependencias extra);
  para OpenAI solo hace falta una API key.
