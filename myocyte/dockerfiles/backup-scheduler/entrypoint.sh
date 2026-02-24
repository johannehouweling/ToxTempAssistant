#!/usr/bin/env bash
set -euo pipefail

# Set BACKUP_SCHEDULE to a cron expression like "0 2 * * *" (every day at 2am) or "0 */6 * * *" (every 6 hours).:
: "${BACKUP_SCHEDULE:="0 2 * * *"}"
# Defined (also) in docker-compose.yml, docker-compose takes precedence.
: "${BACKUP_CMD:=/work/backup.sh}"
: "${CRON_LOG:=/var/log/cron.log}"

if [[ ! -S /var/run/docker.sock ]]; then
  echo "ERROR: /var/run/docker.sock not mounted. Can't run docker/compose." >&2
  exit 1
fi

if [[ ! -f "$BACKUP_CMD" ]]; then
  echo "ERROR: backup script not found at: $BACKUP_CMD" >&2
  exit 1
fi

# backup.sh insists on loading /work/.env
if [[ ! -f "/work/.env" ]]; then
  echo "ERROR: /work/.env not found. Mount your host .env to /work/.env:ro" >&2
  exit 1
fi

# /work is mounted read-only in your compose; chmod would fail. Make it non-fatal.
chmod +x "$BACKUP_CMD" 2>/dev/null || true

mkdir -p "$(dirname "$CRON_LOG")"
touch "$CRON_LOG"

echo "Schedule (cron): ${BACKUP_SCHEDULE}"
echo "Backup cmd:      ${BACKUP_CMD}"
echo "Cron log:        ${CRON_LOG}"

# Run from /work so `docker compose` finds the compose file in the repo root.
printf "%s\n" "${BACKUP_SCHEDULE} cd /work && ${BACKUP_CMD} >> ${CRON_LOG} 2>&1" > /etc/crontabs/root

echo "Installed cron job:"
cat /etc/crontabs/root

exec crond -f -l 2