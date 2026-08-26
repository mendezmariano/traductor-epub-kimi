# Skill: Ejecutar pipeline de traducción EPUB

## Cuándo usar

Cuando el usuario pida traducir un EPUB, descomponerlo, reconstruirlo o ejecutar cualquier paso del pipeline `deconstruct → translate → reconstruct`.

## Requisitos

- Python 3.12+
- `lxml` instalado (entorno base del proyecto).
- Para `libretranslate`: servidor LibreTranslate accesible (local o remoto).
- Para `openai-compatible`/`ollama`: URL y credenciales configuradas.

## Comandos

### Descomponer un EPUB

```bash
python3 main.py deconstruct libros/<libro>.epub --output output/<nombre>
```

### Estimar volumen (dry-run)

```bash
python3 main.py translate output/<nombre> --engine <motor> \
  --source en --target es --dry-run
```

### Traducir con LibreTranslate local

```bash
# Levantar servidor en segundo plano
source .venv/bin/activate
libretranslate --host 127.0.0.1 --port 5000 &

# Traducir
python3 main.py translate output/<nombre> --engine libretranslate \
  --base-url http://127.0.0.1:5000 --source en --target es \
  --delay 0.1 --retries 3
```

### Traducir con motor dummy (pruebas)

```bash
python3 main.py translate output/<nombre> --engine dummy \
  --source en --target es --expansion 1.25
```

### Reconstruir el EPUB

```bash
python3 main.py reconstruct output/<nombre> \
  --output output/<nombre>_es.epub --language es
```

### Pipeline completo con LibreTranslate

```bash
#!/bin/bash
set -e
LIBRO="Developer"
source .venv/bin/activate
libretranslate --host 127.0.0.1 --port 5000 &
LT_PID=$!
sleep 5
python3 main.py deconstruct "libros/${LIBRO}.epub" --output "output/${LIBRO}"
python3 main.py translate "output/${LIBRO}" --engine libretranslate \
  --base-url http://127.0.0.1:5000 --source en --target es --delay 0.1 --retries 3
python3 main.py reconstruct "output/${LIBRO}" --output "output/${LIBRO}_es.epub" --language es
kill $LT_PID
```

## Verificación

Después de reconstruir:

```bash
python3 -m unittest tests.test_roundtrip -v
# O para verificación estructural completa:
python3 -m unittest tests.test_full_roundtrip -v
```

## Consideraciones

- Si el libro es grande, usa `--delay` para no saturar LibreTranslate.
- El comando `translate` puede reanudarse repitiéndolo; escribe `translation_units.json` al finalizar.
- No commitees archivos generados en `output/`.
