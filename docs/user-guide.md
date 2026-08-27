# Guía de usuario

Esta guía explica cómo usar el Traductor de EPUB desde la línea de comandos.

## Requisitos

- Python 3.12 o superior.
- `lxml` (si no está instalado: `pip install lxml`).

No se requieren dependencias adicionales para los motores basados en `urllib` (OpenAI, Ollama, LibreTranslate).

## Flujo de trabajo

El proceso consta de tres pasos:

1. **Descomponer** el EPUB original.
2. **Traducir** las unidades de texto.
3. **Reconstruir** el EPUB traducido.

```bash
python3 main.py deconstruct libros/Developer.epub --output output/Developer
python3 main.py translate output/Developer --engine dummy --expansion 1.25
python3 main.py reconstruct output/Developer --output output/Developer_es.epub --language es
```

---

## 1. Descomponer un EPUB

El subcomando `deconstruct` extrae el contenido del EPUB y genera el archivo de unidades de traducción.

```bash
python3 main.py deconstruct <ruta-al-epub> --output <directorio-de-trabajo>
```

Ejemplo:

```bash
python3 main.py deconstruct libros/Developer.epub --output output/Developer
```

Salida generada:

- `<directorio-de-trabajo>/extracted/` — contenido del EPUB descomprimido.
- `<directorio-de-trabajo>/translation_units.json` — unidades de traducción extraídas.

---

## 2. Traducir las unidades

El subcomando `translate` lee `translation_units.json`, traduce cada unidad y guarda el resultado en el mismo archivo.

```bash
python3 main.py translate <directorio-de-trabajo> --engine <motor> [opciones]
```

Opciones comunes:

| Opción | Descripción | Valor por defecto |
|--------|-------------|-------------------|
| `--engine` | Motor de traducción: `dummy`, `libretranslate`, `openai-compatible`, `ollama` | `dummy` |
| `--source` | Idioma origen | `en` |
| `--target` | Idioma destino | `es` |
| `--expansion` | Factor de expansión (dummy) o hint para LLMs | `1.25` |
| `--base-url` | URL base del servicio | depende del motor |
| `--api-key` | API key para OpenAI o LibreTranslate | — |
| `--delay` | Segundos entre peticiones (LibreTranslate) | — |
| `--model` | Modelo para `openai-compatible` u `ollama` (obligatorio para esos motores) | — |
| `--temperature` | Temperatura de muestreo para LLMs | — |
| `--retries` | Reintentros ante errores transitorios de API | `3` |
| `--glossary` | Ruta a un JSON de glosario | — |
| `--quiet` | No mostrar progreso | — |

### Motor dummy

Ideal para probar el flujo sin gastar tokens ni llamar a servicios externos.

```bash
python3 main.py translate output/Developer --engine dummy --expansion 1.25
```

El motor envuelve cada texto con `[ES]` y, si `expansion > 1`, repite el texto.

### LibreTranslate

Puede usarse una instancia pública o levantar una local con Docker:

```bash
docker run -it -p 5001:5001 libretranslate/libretranslate --port 5001
```

Si usas el entorno virtual del proyecto, el binario `libretranslate` ya está instalado:

```bash
source .venv/bin/activate
libretranslate --host 127.0.0.1 --port 5001
```

```bash
python3 main.py translate output/Developer --engine libretranslate \
  --source en --target es \
  --base-url http://localhost:5001 \
  --api-key $LIBRETRANSLATE_API_KEY \
  --delay 0.5
```

### OpenAI o compatible (Groq, Mistral, etc.)

El motor `openai-compatible` funciona con cualquier proveedor que use la API de chat completions de OpenAI. Requiere `--model` y `--api-key`.

```bash
python3 main.py translate output/Developer --engine openai-compatible \
  --source en --target es \
  --api-key $OPENAI_API_KEY \
  --base-url https://api.openai.com/v1 \
  --model gpt-4o-mini \
  --temperature 0.3 \
  --expansion 1.25
```

También funciona con proveedores compatibles como Groq:

```bash
python3 main.py translate output/Developer --engine openai-compatible \
  --source en --target es \
  --api-key $GROQ_API_KEY \
  --base-url https://api.groq.com/openai/v1 \
  --model llama-3.1-70b-versatile \
  --temperature 0.3 \
  --expansion 1.25
```

El motor `openai` sigue funcionando como alias de `openai-compatible` para mantener compatibilidad.

### Ollama (local)

```bash
python3 main.py translate output/Developer --engine ollama \
  --source en --target es \
  --base-url http://localhost:11434 \
  --model llama3.2 \
  --temperature 0.3 \
  --expansion 1.25
```

### Traducción manual

También puedes editar directamente `output/Developer/translation_units.json` y rellenar el campo `translation` de cada unidad. Luego ejecuta `reconstruct`.

---

## 3. Reconstruir el EPUB

El subcomando `reconstruct` genera el EPUB final a partir del directorio extraído y las traducciones guardadas.

```bash
python3 main.py reconstruct <directorio-de-trabajo> --output <ruta-epub-salida> --language <idioma>
```

Ejemplo:

```bash
python3 main.py reconstruct output/Developer \
  --output output/Developer_es.epub \
  --language es
```

La opción `--language` actualiza el valor de `<dc:language>` en el archivo `.opf`.

---

## Uso de glosarios

Puedes definir un glosario para forzar traducciones consistentes de términos técnicos. Crea un archivo `glossary.json`:

```json
{
  "large language model": "gran modelo de lenguaje",
  "prompt": "instrucción",
  "fine-tuning": "ajuste fino",
  "token": "token"
}
```

Y úsalo con cualquier motor:

```bash
python3 main.py translate output/Developer --engine libretranslate \
  --base-url http://localhost:5001 \
  --glossary glossary.json
```

El glosario funciona de dos maneras:

1. Con motores basados en LLM (`openai-compatible`, `ollama`), los términos se incluyen en el prompt de sistema.
2. Con `libretranslate`, el pipeline separa el texto plano de los placeholders, aplica el glosario a los segmentos planos ANTES de enviarlos al servicio y vuelve a aplicarlo después. Esto corrige términos técnicos incluso dentro de tags inline como `<i>pretrained</i>`.

---

## Solución de problemas

- **El traductor modifica placeholders**: con LibreTranslate el pipeline usa segmentación (`segment_placeholders=True`) para no enviar los marcadores al servicio. Si ves advertencias de placeholders perdidos, revisa que `epub_toolkit/translator.py` esté actualizado.
- **Términos técnicos dentro de tags inline no se corrigen**: usa `--glossary` y verifica que el término esté en el JSON. El glosario se aplica a los segmentos planos antes de la traducción.
- **Espacios perdidos alrededor de placeholders (`sonpreentrenamientosobre`)**: el pipeline reconstruye los espacios fuera de los tags inline. Si persiste, reporta el caso con el texto original y la traducción.
- **LibreTranslate devuelve errores de rate limit**: usa `--delay` para espaciar las peticiones.
- **El EPUB reconstruido no se abre**: ejecuta `python3 -m unittest tests.test_roundtrip` para verificar que el roundtrip básico funciona.
- **Faltan unidades**: los tags `<script>`, `<style>`, `<pre>`, `<svg>`, `<math>` y otros se ignoran por diseño (ver `epub_toolkit/utils.py`).
