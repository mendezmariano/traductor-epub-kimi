# Skill: Mantener y usar glosarios técnicos

## Cuándo usar

Cuando el usuario quiera mejorar la traducción de términos técnicos (IA, ciberseguridad, desarrollo, etc.) o cuando se detecten términos mal traducidos dentro o fuera de tags inline.

## Formato del glosario

El archivo debe ser un JSON de pares `término -> traducción`:

```json
{
  "reverse engineering": "ingeniería inversa",
  "pretrained": "preentrenado",
  "fine-tuning": "ajuste fino",
  "large language model": "modelo de lenguaje grande",
  "LLMs": "modelos de lenguaje grande"
}
```

Reglas para evitar artefactos:

1. No incluyas espacios iniciales/finales en los términos.
2. Ordena de más largo a más corto cuando haya términos contenidos en otros.
3. Si una abreviatura (p. ej. `LLMs`) aparece siempre junto a su forma expandida, considera omitirla para evitar duplicaciones como `modelos de lenguaje grande (modelos de lenguaje grande)`.
4. El pipeline aplica el glosario antes y después de la traducción; por eso los términos se traducen aunque estén dentro de tags inline.

## Cómo aplicarlo

```bash
python3 main.py translate output/<nombre> --engine libretranslate \
  --base-url http://127.0.0.1:5001 --source en --target es \
  --glossary output/glossary.json
```

## Cómo probar un término aislado

```bash
cd /home/dartmendez/src/AI/kimik3/traductor-epub-kimi
source .venv/bin/activate
python3 - <<'PY'
from epub_toolkit.translator import LibreTranslateTranslator, translate_unit
from epub_toolkit.models import TranslationUnit

tr = LibreTranslateTranslator(base_url='http://127.0.0.1:5001')
glossary = {"pretrained": "preentrenado"}
unit = TranslationUnit(unit_id='u1', xpath='//p', original='A <i>pretrained</i> model.')
print(translate_unit(tr, unit, 'en', 'es', glossary))
PY
```

## Dónde actúa el glosario

- En texto plano entre placeholders.
- En atributos traducibles (`alt`, `title`, `aria-label`, `placeholder`).
- El contenido dentro de placeholders (tags inline) se traduce como texto plano, por lo que el glosario también lo corrige.
- Funciona con todos los motores: `libretranslate`, `deepl`, `azure`, `google`, `openai-compatible`, `ollama`.

## Dónde NO actúa el glosario

- No corrige errores semánticos generales del motor de traducción (p. ej. "invertir el ingeniero").
- No mejora la calidad literaria del texto circundante.
