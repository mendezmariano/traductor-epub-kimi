# Skill: Ejecutar tests del proyecto

## Cuándo usar

Antes de dar por terminada cualquier tarea de código, o cuando el usuario pida verificar el estado del proyecto.

## Comandos

### Suite completa

```bash
python3 -m unittest discover tests -v
```

### Tests por módulo

```bash
python3 -m unittest tests.test_roundtrip -v
python3 -m unittest tests.test_full_roundtrip -v
python3 -m unittest tests.test_translator -v
python3 -m unittest tests.test_libretranslate_integration -v
python3 -m unittest tests.test_retries -v
python3 -m unittest tests.test_openai_compatible_integration -v
```

### Verificación rápida del proyecto

```bash
bash scripts/resume.sh
```

## Qué significan los resultados

- **OK:** la suite pasa. Puedes continuar.
- **FAIL / ERROR:** hay una regresión. No marques la tarea como terminada.
  - Lee el traceback.
  - Identifica el archivo y la función afectada.
  - Corrige o escala al usuario si no puedes resolverlo.

## Reglas

1. Ejecuta la suite completa después de cualquier cambio funcional.
2. Si solo hiciste cambios en documentación, alcanza con `bash scripts/resume.sh`.
3. No ignores advertencias (`warnings.warn`) relacionadas con placeholders perdidos sin investigar.
4. Si un test necesita un servidor LibreTranslate, asegúrate de que esté levantado o usa el mock del test.
