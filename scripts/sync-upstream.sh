#!/usr/bin/env bash
# Trae las novedades de FilaOps (BLB3DPrinting/filaops) a la rama nebula.
# main = espejo limpio de upstream; nebula = nuestra versión.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

git fetch upstream --tags
git switch main
git merge --ff-only upstream/main
git push origin main --tags

git switch nebula
git merge main -m "Merge upstream FilaOps $(git describe --tags --abbrev=0 main 2>/dev/null || echo main)"
echo "Listo. Revisa conflictos/cambios y haz: git push origin nebula"
