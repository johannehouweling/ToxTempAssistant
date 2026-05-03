#!/usr/bin/env bash
set -euo pipefail

# Set BACKUP_SCHEDULE to a cron expression like "0 2 * * *" (every day at 2am) or "0 */6 * * *" (every 6 hours).:
: "${BACKUP_SCHEDULE:="0 2 * * *"}"
# backup.sh is baked into the image — no longer mounted from the host repo.
: "${BACKUP_CMD:=/usr/local/bin/backup.sh}"
: "${CRON_LOG:=/var/log/cron.log}"

if [[ ! -S /var/run/docker.sock ]]; then
  echo "ERROR: /var/run/docker.sock not mounted. Can't run docker/compose." >&2
  exit 1
fi

if [[ ! -x "$BACKUP_CMD" ]]; then
  echo "ERROR: backup script not executable at: $BACKUP_CMD" >&2
  exit 1
fi

mkdir -p "$(dirname "$CRON_LOG")"
touch "$CRON_LOG"

echo "Schedule (cron): ${BACKUP_SCHEDULE}"
echo "Backup cmd:      ${BACKUP_CMD}"
echo "Cron log:        ${CRON_LOG}"

CRONTAB_FILE=/etc/crontab
printf "%s\n" "${BACKUP_SCHEDULE} ${BACKUP_CMD} >> ${CRON_LOG} 2>&1" > "$CRONTAB_FILE"

echo "Installed cron job:"
cat "$CRONTAB_FILE"

exec /usr/local/bin/supercronic "$CRONTAB_FILE"
