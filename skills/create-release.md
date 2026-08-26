# Skill: Preparar una release

## Cuándo usar

Cuando el usuario indique que una entrega está lista para mergear o cuando se quiera publicar una nueva versión del proyecto.

## Prerrequisitos

- Todos los tests pasan: `python3 -m unittest discover tests -v`.
- La documentación está actualizada (`README.md`, `docs/`, `STATUS.md`, `BACKLOG.md`).
- Los cambios están commiteados en una rama de feature.

## Pasos

1. **Verificar estado**
   ```bash
   bash scripts/resume.sh
   python3 -m unittest discover tests -v
   ```

2. **Actualizar backlog y estado**
   - Abre `BACKLOG.md`.
   - Marca la entrega como `DONE`.
   - Añade nota de lo que se implementó, archivos afectados y tests.
   - Abre `STATUS.md`.
   - Actualiza PRs abiertos/cerrados y próximo paso recomendado.

3. **Solicitar confirmación al usuario**
   - Pregunta si puede procederse con el merge/push.
   - No ejecutes comandos git sin autorización.

4. **Merge (solo con aprobación)**
   ```bash
   git checkout master
   git pull origin master
   git merge --no-ff <rama-feature>
   git push origin master
   ```

5. **Tag de release (opcional, solo con aprobación)**
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

## Reglas

1. No hagas push sin confirmación explícita.
2. No crees tags de release sin que el usuario lo solicite.
3. Si hay PRs abiertos en GitHub, usa `gh pr merge` solo con autorización.
4. Asegúrate de que no se commiteen archivos de `output/` ni EPUBs traducidos.

## Archivos a revisar

- `BACKLOG.md`
- `STATUS.md`
- `README.md`
- `.github/workflows/ci.yml`
- `.gitignore`
