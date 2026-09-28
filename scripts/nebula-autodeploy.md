# Despliegue automático (server2)

`scripts/nebula-autodeploy.sh` se ejecuta cada hora por cron en server2 y despliega
cuando aparece un tag nuevo:

| Tag | Quién lo crea | Qué significa |
| --- | --- | --- |
| `vX.Y.Z` | BLB3DPrinting (upstream) | Release oficial de FilaOps |
| `nebula-*` | Nosotros, en `Nebula-Syst/filaops` | Release propia de la rama `nebula` |

Se despliega **el último tag `nebula-*` fusionado con la última release `vX.Y.Z`**.

## Publicar una versión propia

```bash
git switch nebula && git pull
git tag nebula-v1.1.0 && git push origin nebula-v1.1.0
```

En menos de una hora estará en https://gestion.glprintworks.com.

## Qué pasa si algo va mal

- **Conflicto** al fusionar la release de upstream: no se despliega. Resuélvelo en local
  con `scripts/sync-upstream.sh`, sube `nebula` y crea un tag `nebula-*` nuevo.
- **La versión nueva no arranca sana** (backend no healthy o la web no responde en 5 min):
  vuelve sola a las imágenes y la base de datos anteriores.
- Antes de cada despliegue se hace `pg_dump` en `~/filaops-deploy/backups/` (se guardan 7).

## Estado y logs (en server2)

```bash
cat ~/filaops-deploy/status.json     # ok | unchanged | conflict | rolled_back | broken
tail -50 ~/filaops-deploy/deploy.log
~/filaops-deploy/autodeploy.sh --force   # desplegar ya, aunque no haya tag nuevo
```

## Instalación

Cron ejecuta una **copia** del script (el script hace `git checkout` y no puede
reescribirse a sí mismo mientras corre):

```bash
mkdir -p ~/filaops-deploy
cp ~/filaops/scripts/nebula-autodeploy.sh ~/filaops-deploy/autodeploy.sh
chmod +x ~/filaops-deploy/autodeploy.sh
git -C ~/filaops config user.name "Nebula autodeploy"
git -C ~/filaops config user.email "autodeploy@nebulasyst.com"
( crontab -l 2>/dev/null; echo '17 * * * * $HOME/filaops-deploy/autodeploy.sh >/dev/null 2>&1' ) | crontab -
```

Tras cambiar el script en el repo, vuelve a copiarlo.
