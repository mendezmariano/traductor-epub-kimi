# Instrucciones para agentes

Este archivo define las reglas generales que deben seguir todos los agentes de Kimi Code que trabajen en el proyecto **Traductor de EPUB**.

## Propósito del proyecto

Aplicación Python 3.12+ para traducir libros EPUB preservando el marcado HTML inline. El pipeline principal es:

```
deconstruct → translate → reconstruct
```

## Reglas generales

1. **Idioma:** escribe código, docstrings y comentarios en español. Los mensajes de commit y la documentación del repo también van en español.
2. **Python 3.12+** con anotaciones de tipo e `from __future__ import annotations` en cada módulo.
3. **Rutas:** usa `pathlib.Path`; evita cadenas de rutas.
4. **XML/XHTML:** usa `lxml`. No uses `xml.etree` ni BeautifulSoup para el pipeline principal.
5. **Dependencias:** evita añadir dependencias externas. Se prefiere `urllib` sobre SDKs. `tqdm` es opcional.
6. **Cambios mínimos:** no hagas refactorizaciones cosméticas ni limpiezas fuera del alcance de la tarea.
7. **Tests:** antes de dar por terminado cualquier cambio funcional, ejecuta `python3 -m unittest discover tests -v` y asegúrate de que pasa.
8. **Documentación:** si cambias la API pública o el CLI, actualiza `docs/` y `README.md`.
9. **Estado del proyecto:** al finalizar una entrega o tarea significativa, actualiza `STATUS.md` y `BACKLOG.md`.
10. **Git:** no ejecutes `git commit`, `git push`, `git reset`, `git rebase` ni otras mutaciones de git sin confirmación explícita del usuario. Pregunta antes.

## Estructura del proyecto

```
traductor-epub-kimi/
├── epub_toolkit/        # paquete principal
├── tests/               # tests con unittest
├── libros/              # EPUBs de ejemplo (no commitear nuevos EPUBs sin autorización)
├── output/              # salida generada (no commitear)
├── docs/                # documentación
├── .agents/             # roles de agentes de Kimi Code
├── skills/              # skills de Kimi Code
├── main.py              # CLI
├── README.md
├── STATUS.md
└── BACKLOG.md
```

## Cómo retomar el proyecto

1. Lee `STATUS.md` para saber la rama activa, PRs abiertos y próximo paso.
2. Lee `BACKLOG.md` para ver el plan de entregas.
3. Ejecuta `bash scripts/resume.sh` o `python3 -m unittest discover tests -v` para verificar el estado.
4. Consulta los roles en `.agents/` y los skills en `skills/` según la tarea asignada.

## Convenciones de estilo

- Nombres en español para dominio (`unidad`, `placeholder`, `reconstructor`).
- Type hints obligatorias en funciones y métodos públicos.
- Docstrings con triple comillas dobles.
- Máximo de lógica en funciones pequeñas; evita funciones de más de 60 líneas.
- Manejo de errores con excepciones propias o `ValueError`; evita capturar `Exception` genérico salvo en retries.
