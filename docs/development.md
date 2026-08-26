# Guía de desarrollo

Esta guía está dirigida a quienes quieran entender, modificar o extender el Traductor de EPUB.

## Ejecutar tests

El proyecto usa `unittest`. Los tests están en el directorio `tests/`.

### Todos los tests

```bash
python3 -m unittest discover tests -v
```

### Solo un módulo

```bash
python3 -m unittest tests.test_roundtrip -v
python3 -m unittest tests.test_translator -v
python3 -m unittest tests.test_libretranslate_integration -v
```

## Estructura de tests

### `tests/test_roundtrip.py`

Prueba el flujo completo de descomposición y reconstrucción:

- Encuentra todos los EPUBs de `libros/`.
- Descompone y extrae unidades de cada EPUB.
- Reconstruye el EPUB sin traducir.
- Verifica que el resultado sea un ZIP válido.
- Comprueba que `mimetype` sea el primer archivo y vaya sin compresión.
- Comprueba que todos los XHTML del manifest estén presentes y sean parseables.

### `tests/test_translator.py`

Prueba el módulo `epub_toolkit.translator`:

- Protección y restauración de placeholders.
- Comportamiento del `DummyTranslator` (expansión, sin expansión).
- Traducción de documentos y lotes.
- Factoría de traductores.
- Prompts para LLM.
- Parseo de respuestas numeradas.
- Glosario.

### `tests/test_libretranslate_integration.py`

Levanta un servidor HTTP mock que simula la API de LibreTranslate y prueba:

- Traducción directa.
- Traducción de una unidad preservando placeholders.

## Convenciones de código

- Python 3.12+ con anotaciones de tipo.
- Importar `from __future__ import annotations` en todos los módulos.
- Usar `pathlib.Path` para rutas.
- Usar `lxml` para manipulación de XML/XHTML.
- Mantener docstrings en español.
- Evitar dependencias externas innecesarias; se prefiere `urllib` sobre SDKs.

## Cómo añadir un nuevo motor de traducción

1. Crea una clase que herede de `Translator` en `epub_toolkit/translator.py`:

```python
class MiTraductor(Translator):
    def __init__(self, **kwargs) -> None:
        ...

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        ...

    def translate_batch(self, texts, source_lang, target_lang,
                        context_title="", glossary=None) -> list[str]:
        ...
```

2. Registra el motor en `create_translator`:

```python
if engine == "mi_motor":
    return MiTraductor(**kwargs)
```

3. Añade el nombre del motor a las `choices` del CLI en `main.py`:

```python
tr.add_argument("--engine", default="dummy",
                choices=["dummy", "libretranslate", "openai", "ollama", "mi_motor"],
                help="Motor de traducción.")
```

4. Añade tests en `tests/test_translator.py`.

## Estructura del proyecto

```
traductor-epub-kimi/
├── epub_toolkit/          # paquete principal
│   ├── __init__.py
│   ├── deconstructor.py
│   ├── extractor.py
│   ├── models.py
│   ├── reconstructor.py
│   ├── translator.py
│   └── utils.py
├── tests/                 # tests con unittest
├── libros/                # EPUBs de ejemplo
├── output/                # salida generada por el CLI
├── docs/                  # documentación
├── main.py                # punto de entrada CLI
└── README.md              # página de inicio
```

## Depuración

Para inspeccionar las unidades extraídas:

```bash
python3 main.py deconstruct libros/Developer.epub --output output/Developer
python3 -c "import json; print(json.load(open('output/Developer/translation_units.json'), indent=2))"
```

Para probar un motor sin reconstruir:

```python
from epub_toolkit.models import ExtractedDocument
from epub_toolkit.translator import create_translator, translate_document

import json
with open("output/Developer/translation_units.json") as f:
    doc = ExtractedDocument.from_dict(json.load(f))

t = create_translator("dummy", expansion=1.25)
translate_document(t, doc, progress=False)
```

## Opciones útiles del CLI

- `--dry-run` en `translate` estima el volumen (unidades, caracteres y tokens aproximados) sin traducir ni escribir `translation_units.json`.
- `--quiet` desactiva el progreso; sin `--quiet`, se usa `tqdm` si está instalado, o progreso textual como fallback.

## Retomar después de un `/clear`

Si retomas el proyecto sin contexto de conversión previo:

1. Ejecuta el script de resumen:
   ```bash
   bash scripts/resume.sh
   ```
2. Revisa [`STATUS.md`](../STATUS.md) para conocer la rama activa, los PRs abiertos y la entrega pendiente.
3. Revisa [`BACKLOG.md`](../BACKLOG.md) para ver el plan de entregas y el detalle de cada una.
4. Asegúrate de estar en la rama correcta:
   ```bash
   git status
   git branch
   ```
5. Si hay entregas `READY`, continúa con la primera; de lo contrario, revisa/mergea los PRs abiertos.

## Contribuciones

- Mantén los cambios mínimos y enfocados.
- Añade tests para nuevas funcionalidades.
- Actualiza la documentación en `docs/` si cambias la API o el comportamiento del CLI.
- Actualiza [`BACKLOG.md`](../BACKLOG.md) y [`STATUS.md`](../STATUS.md) al finalizar una entrega.
- Asegúrate de que `python3 -m unittest discover tests -v` pase antes de finalizar.
