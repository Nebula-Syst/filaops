#!/usr/bin/env bash
# Despliegue automático de FilaOps (fork Nebula) en server2.
#
# Cron lo lanza cada hora. Despliega cuando aparece un tag nuevo:
#   - vX.Y.Z      → release oficial de FilaOps (BLB3DPrinting/filaops)
#   - nebula-*    → release propia (tag en Nebula-Syst/filaops, sobre la rama nebula)
#
# Lo que se despliega = último tag nebula-* (o origin/nebula si aún no hay ninguno)
# fusionado con la última release vX.Y.Z de upstream.
#
# Seguridad:
#   - Conflicto al fusionar → no se despliega nada (queda en el log y en status).
#   - Copia de la base de datos antes de cada despliegue (se guardan las 7 últimas).
#   - Si la versión nueva no arranca sana → vuelve a la anterior (imágenes + BD).
#
# Instalación: ver scripts/nebula-autodeploy.md
set -euo pipefail

REPO="${FILAOPS_REPO:-$HOME/filaops}"
STATE="${FILAOPS_DEPLOY_STATE:-$HOME/filaops-deploy}"
HEALTH_URL="${FILAOPS_HEALTH_URL:-http://127.0.0.1:13003/api/v1/setup/status}"
FORCE="${1:-}"
LOG="$STATE/deploy.log"
SERVICES=(backend frontend migrate)

mkdir -p "$STATE/backups"
exec 9>"$STATE/lock"
flock -n 9 || exit 0

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
status() { printf '{"time":"%s","result":"%s","target":"%s","detail":"%s"}\n' "$(date -Is)" "$1" "$2" "$3" > "$STATE/status.json"; }

cd "$REPO"
git fetch -q origin --tags --prune --force
git fetch -q upstream --tags --force

latest_up=$(git tag -l 'v*' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
latest_own=$(git tag -l 'nebula-*' | sort -V | tail -1)
base="${latest_own:-origin/nebula}"
target="${latest_own:-nebula}+${latest_up}"

if [[ "$FORCE" != "--force" && "$target" == "$(cat "$STATE/last-target" 2>/dev/null)" ]]; then
  exit 0
fi

log "=== Nuevo objetivo: $target (antes: $(cat "$STATE/last-target" 2>/dev/null || echo ninguno))"
prev_commit=$(git rev-parse HEAD)

# 1. Preparar el código: base propia + release de upstream
git checkout -q -B deploy "$base"
if ! git merge -q --no-edit -m "Autodeploy: merge $latest_up en $base" "$latest_up" >>"$LOG" 2>&1; then
  git merge --abort || true
  git checkout -q -B deploy "$prev_commit"
  log "CONFLICTO al fusionar $latest_up en $base. No se despliega. Resuélvelo con scripts/sync-upstream.sh y crea un tag nebula-* nuevo."
  status conflict "$target" "merge conflict $latest_up into $base"
  echo "$target" > "$STATE/last-target"   # no reintentar cada hora el mismo conflicto
  exit 1
fi
new_commit=$(git rev-parse HEAD)
if [[ "$FORCE" != "--force" && "$new_commit" == "$prev_commit" ]]; then
  log "El código no cambia ($new_commit); nada que desplegar."
  status unchanged "$target" "$new_commit"
  echo "$target" > "$STATE/last-target"
  exit 0
fi
log "Código: $prev_commit → $new_commit"

# 2. Copia de la base de datos
dump="$STATE/backups/filaops-$(date +%Y%m%d-%H%M%S).dump"
docker exec filaops-db pg_dump -U postgres -Fc filaops > "$dump"
log "Backup BD: $dump ($(du -h "$dump" | cut -f1))"
ls -1t "$STATE"/backups/*.dump | tail -n +8 | xargs -r rm -f

# 3. Guardar las imágenes actuales para poder volver atrás
for s in "${SERVICES[@]}"; do
  docker image inspect "filaops-$s:latest" >/dev/null 2>&1 && docker tag "filaops-$s:latest" "filaops-$s:rollback"
done

healthy() {
  for _ in $(seq 1 60); do
    if [[ "$(docker inspect -f '{{.State.Health.Status}}' filaops-backend 2>/dev/null)" == healthy ]] \
      && curl -sf -o /dev/null "$HEALTH_URL"; then
      return 0
    fi
    sleep 5
  done
  return 1
}

# 4. Desplegar
if docker compose up -d --build >>"$LOG" 2>&1 && healthy; then
  log "OK: desplegado $target ($new_commit)"
  status ok "$target" "$new_commit"
  echo "$target" > "$STATE/last-target"
  docker image prune -f >/dev/null 2>&1 || true
  exit 0
fi

# 5. Algo ha fallado: volver a la versión anterior
log "FALLO: la versión nueva no arranca sana. Restaurando $prev_commit y la BD."
git checkout -q -B deploy "$prev_commit"
docker compose stop backend frontend >>"$LOG" 2>&1 || true
docker exec -i filaops-db pg_restore -U postgres -d filaops --clean --if-exists < "$dump" >>"$LOG" 2>&1 || true
for s in "${SERVICES[@]}"; do
  docker image inspect "filaops-$s:rollback" >/dev/null 2>&1 && docker tag "filaops-$s:rollback" "filaops-$s:latest"
done
docker compose up -d >>"$LOG" 2>&1 || true
if healthy; then
  log "Restaurada la versión anterior ($prev_commit)."
  status rolled_back "$target" "restored $prev_commit"
else
  log "ATENCIÓN: la versión anterior tampoco arranca. Revisión manual necesaria."
  status broken "$target" "rollback failed"
fi
echo "$target" > "$STATE/last-target"   # no reintentar en bucle una versión rota
exit 1
