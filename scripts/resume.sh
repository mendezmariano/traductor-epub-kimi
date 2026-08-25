#!/usr/bin/env bash
# resume.sh — Script para retomar el proyecto después de un /clear.
# Uso: bash scripts/resume.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

echo "=========================================="
echo "  Traductor de EPUB — Resumen de estado"
echo "=========================================="
echo

# Rama actual
echo "→ Rama actual:"
git branch --show-current
echo

# Estado del working tree
echo "→ Estado del working tree:"
if git status --short | grep -q .; then
    git status --short
else
    echo "   Limpio."
fi
echo

# Últimos commits
echo "→ Últimos commits:"
git log --oneline -5
echo

# PR abierto (si gh está disponible)
if command -v gh &> /dev/null; then
    echo "→ Pull Request abierto:"
    gh pr view --json title,url,state,headRefName --jq '. | "   \(.title)\n   \(.url)\n   Estado: \(.state)\n   Rama: \(.headRefName)"' 2>/dev/null || echo "   No se pudo obtener el PR."
    echo
else
    echo "→ 'gh' no está disponible. Instálalo para ver el PR abierto."
    echo
fi

# Contenido de STATUS.md (primera sección relevante)
if [[ -f STATUS.md ]]; then
    echo "→ Estado del proyecto (STATUS.md):"
    awk '/^## Rama activa/,/^## Cómo verificar/' STATUS.md | sed '$d'
    echo
fi

# Ejecutar tests
echo "→ Ejecutando tests..."
if python3 -m unittest discover tests -v; then
    echo
    echo "✅ Todos los tests pasaron."
else
    echo
    echo "❌ Algunos tests fallaron. Revisa el output arriba."
    exit 1
fi

echo
echo "=========================================="
echo "  Próximo paso recomendado"
echo "=========================================="
if [[ -f STATUS.md ]]; then
    awk '/^## Próximo paso recomendado/,/^## Cómo verificar/' STATUS.md | sed '$d'
else
    echo "Revisa BACKLOG.md para ver la siguiente entrega."
fi

echo
