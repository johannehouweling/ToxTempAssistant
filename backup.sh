#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Backup script — runs INSIDE the backup container.
#
# Reaches postgres + minio over the compose/swarm overlay networks (the
# backup service joins db_network + data_network in docker-compose.yml).
# No /var/run/docker.sock, no `docker exec`, no helper containers — works
# the same in Compose and Swarm regardless of which node the dependencies
# land on.
#
# Required env (injected via env_file: in compose):
#   POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB / POSTGRES_HOST
#   AWS_S3_ENDPOINT_URL                 (e.g. http://minio:9000)
#   MINIO_ROOT_USER / MINIO_ROOT_PASSWORD
#
# Optional:
#   POSTGRES_PORT       default 5432
#   BACKUP_ROOT         default /work/backups (matches the bind mount)
#   RETENTION_DAYS      default 14 (BACKUP_RETENTION_DAYS also recognised)
#   MINIO_BUCKET        default empty → mirror all buckets
###############################################################################

# -------------------- Defaults --------------------
BACKUP_ROOT="${BACKUP_ROOT:-/work/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-${BACKUP_RETENTION_DAYS:-14}}"
MINIO_BUCKET="${MINIO_BUCKET:-}"

if [[ "$BACKUP_ROOT" != /* ]]; then
  echo "ERROR: BACKUP_ROOT must be an absolute path: '$BACKUP_ROOT'" >&2
  exit 1
fi

# -------------------- Validate required env --------------------
: "${POSTGRES_USER:?Missing POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?Missing POSTGRES_PASSWORD}"
: "${POSTGRES_DB:?Missing POSTGRES_DB}"
: "${POSTGRES_HOST:?Missing POSTGRES_HOST}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

: "${AWS_S3_ENDPOINT_URL:?Missing AWS_S3_ENDPOINT_URL (e.g. http://minio:9000)}"
: "${MINIO_ROOT_USER:?Missing MINIO_ROOT_USER}"
: "${MINIO_ROOT_PASSWORD:?Missing MINIO_ROOT_PASSWORD}"

# -------------------- Helpers --------------------
ts() { date +"%Y-%m-%d_%H%M%S"; }
# Per-line timestamping is handled by the cron wrapper (entrypoint.sh pipes
# all output through `ts`), so the script just emits the message.
log() { printf "%s\n" "$*"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

# -------------------- Pre-flight --------------------
require_cmd pg_dump
require_cmd mc
require_cmd gzip
require_cmd find

mkdir -p "$BACKUP_ROOT"
STAMP="$(ts)"
OUTDIR="$BACKUP_ROOT/$STAMP"
mkdir -p "$OUTDIR"

log "Backup root: $BACKUP_ROOT"
log "This run:    $OUTDIR"

# -------------------- 1) Postgres backup (logical) --------------------
PG_OUT="$OUTDIR/postgres_${POSTGRES_DB}.sql.gz"

log "Backing up Postgres via pg_dump (host=$POSTGRES_HOST db=$POSTGRES_DB user=$POSTGRES_USER) ..."
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h "$POSTGRES_HOST" \
  -p "$POSTGRES_PORT" \
  -U "$POSTGRES_USER" \
  "$POSTGRES_DB" \
  | gzip -9 > "$PG_OUT"

log "Postgres dump written: $PG_OUT"

# -------------------- 2) MinIO backup (mc mirror) --------------------
MC_ALIAS="local"
MINIO_DEST="$OUTDIR/minio"
mkdir -p "$MINIO_DEST"

log "Backing up MinIO via mc mirror (endpoint=$AWS_S3_ENDPOINT_URL) ..."
mc alias set "$MC_ALIAS" "$AWS_S3_ENDPOINT_URL" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null

if [[ -z "$MINIO_BUCKET" ]]; then
  SRC_PATH="${MC_ALIAS}/"
  DEST_PATH="$MINIO_DEST"
  MIRROR_LABEL="ALL buckets"
else
  SRC_PATH="${MC_ALIAS}/${MINIO_BUCKET}"
  DEST_PATH="$MINIO_DEST/${MINIO_BUCKET}"
  MIRROR_LABEL="bucket '$MINIO_BUCKET'"
  mkdir -p "$DEST_PATH"
fi

log "Mirroring: $MIRROR_LABEL"
mc mirror --overwrite --preserve "$SRC_PATH" "$DEST_PATH"

log "MinIO mirror written under: $MINIO_DEST"

# -------------------- Manifest --------------------
log "Writing manifest ..."
(
  cd "$OUTDIR"
  {
    echo "timestamp=$STAMP"
    echo "backup_root=$BACKUP_ROOT"
    echo "retention_days=$RETENTION_DAYS"
    echo "postgres_host=$POSTGRES_HOST"
    echo "postgres_db=$POSTGRES_DB"
    echo "postgres_user=$POSTGRES_USER"
    echo "minio_endpoint=$AWS_S3_ENDPOINT_URL"
    echo "minio_bucket=${MINIO_BUCKET:-ALL}"
  } > manifest.txt
  ls -lah > files.txt
)

# -------------------- Retention cleanup --------------------
log "Applying retention: delete timestamped backup directories older than $RETENTION_DAYS days in $BACKUP_ROOT ..."

# Safety fuse: refuse obviously dangerous roots
case "$BACKUP_ROOT" in
  ""|"/"|"$HOME"|"/home"|"/root"|"/tmp"|"/var"|"/var/backups" \
  |"/bin"|"/boot"|"/data"|"/dev"|"/etc"|"/lib"|"/lib32"|"/lib64"|"/libx32" \
  |"/lost+found"|"/media"|"/mnt"|"/opt"|"/proc"|"/run"|"/sbin"|"/snap" \
  |"/srv"|"/sys"|"/usr")
    echo "ERROR: Refusing retention cleanup because BACKUP_ROOT looks unsafe: '$BACKUP_ROOT'" >&2
    exit 1
    ;;
esac

if [[ ! -d "$BACKUP_ROOT" ]]; then
  echo "ERROR: BACKUP_ROOT is not a directory: '$BACKUP_ROOT'" >&2
  exit 1
fi

# Only delete directories that match the script's timestamp naming: YYYY-MM-DD_HHMMSS
find "$BACKUP_ROOT" \
  -mindepth 1 -maxdepth 1 -type d \
  -regextype posix-extended \
  -regex '.*/[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{6}$' \
  -mtime +"$RETENTION_DAYS" \
  -print -exec rm -rf -- {} \;

log "Backup completed OK."
log "Output directory: $OUTDIR"

###############################################################################
# Restore hints:
#
# Postgres:
#   gunzip -c backups/<STAMP>/postgres_<DB>.sql.gz \
#     | docker exec -i <postgres-container> psql -U <user> <db>
#
# MinIO:
#   ALL buckets:        mc mirror <backup>/minio/ <alias>/
#   single bucket:      mc mirror <backup>/minio/<bucket>/ <alias>/<bucket>
###############################################################################
