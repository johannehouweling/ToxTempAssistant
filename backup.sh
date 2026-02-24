#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Backup script (NO duplicate .env entries required)
#
# Uses existing keys from your .env:
#   POSTGRES_USER
#   POSTGRES_PASSWORD
#   POSTGRES_DB
#   POSTGRES_HOST        (docker-compose service name for postgres container)
#   POSTGRES_PORT        (optional, default 5432; not strictly needed for exec)
#
#   AWS_S3_ENDPOINT_URL  (e.g. http://minio:9000)  <-- used for MinIO endpoint
#   MINIO_ROOT_USER
#   MINIO_ROOT_PASSWORD
#
# Optional (safe defaults if missing):
#   BACKUP_ROOT          default: ./backups (next to script)
#   RETENTION_DAYS       default: 14
#   MEDIA_DIR            default: ./myocyte/media (next to script)
#   MINIO_BUCKET         default: empty => all buckets
#
# What it does:
# - Postgres: pg_dump (logical backup) from inside the postgres container
# - Media: tar.gz of MEDIA_DIR on the host
# - MinIO: mc mirror (object-level backup) using minio/mc container
#
# Requirements:
# - docker + docker compose
# - tar, gzip, find, grep, sed
###############################################################################

# -------------------- Load .env (next to this script) --------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # Load KEY=VALUE lines, ignore comments and blank lines.
  # shellcheck disable=SC1090
  source <(grep -v '^\s*#' "$ENV_FILE" | sed '/^\s*$/d')
  set +a
else
  echo "ERROR: .env not found at: $ENV_FILE" >&2
  exit 1
fi

# -------------------- Defaults (do NOT require new .env keys) --------------------
BACKUP_ROOT="${BACKUP_ROOT:-$SCRIPT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-${BACKUP_RETENTION_DAYS:-14}}"
MEDIA_DIR="${MEDIA_DIR:-${BACKUP_MEDIA_DIR:-$SCRIPT_DIR/myocyte/media}}"
MINIO_BUCKET="${MINIO_BUCKET:-}"

if [[ "$BACKUP_ROOT" != /* ]]; then
  BACKUP_ROOT="$SCRIPT_DIR/$BACKUP_ROOT"
fi

# -------------------- Validate required existing .env keys --------------------
: "${POSTGRES_USER:?Missing POSTGRES_USER in .env}"
: "${POSTGRES_PASSWORD:?Missing POSTGRES_PASSWORD in .env}"
: "${POSTGRES_DB:?Missing POSTGRES_DB in .env}"
: "${POSTGRES_HOST:?Missing POSTGRES_HOST in .env (should be the docker-compose postgres service name)}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}" # kept for completeness; not used by docker exec

: "${AWS_S3_ENDPOINT_URL:?Missing AWS_S3_ENDPOINT_URL in .env (e.g. http://minio:9000)}"
: "${MINIO_ROOT_USER:?Missing MINIO_ROOT_USER in .env}"
: "${MINIO_ROOT_PASSWORD:?Missing MINIO_ROOT_PASSWORD in .env}"

# -------------------- Helpers --------------------
ts() { date +"%Y-%m-%d_%H%M%S"; }
log() { printf "[%s] %s\n" "$(date -Is)" "$*"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

mkdirp() { mkdir -p "$1"; }

# -------------------- Pre-flight --------------------
require_cmd docker
require_cmd tar
require_cmd gzip
require_cmd find
require_cmd sed
require_cmd grep

mkdirp "$BACKUP_ROOT"
STAMP="$(ts)"
OUTDIR="$BACKUP_ROOT/$STAMP"
mkdirp "$OUTDIR"

log "Backup root: $BACKUP_ROOT"
log "This run:     $OUTDIR"

# -------------------- 1) Postgres backup (logical) --------------------
PG_SERVICE="$POSTGRES_HOST"
PG_OUT="$OUTDIR/postgres_${POSTGRES_DB}.sql.gz"

log "Backing up Postgres via pg_dump (service=$PG_SERVICE db=$POSTGRES_DB user=$POSTGRES_USER) ..."

docker compose exec -T \
  -e GIT_HASH="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
  -e GIT_TAG="$(git describe --tags --abbrev=0 2>/dev/null || echo 'unknown')" \
  -e PGPASSWORD="$POSTGRES_PASSWORD" \
  "$PG_SERVICE" \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip -9 > "$PG_OUT"

log "Postgres dump written: $PG_OUT"

# -------------------- 2) Django media backup --------------------
log "Backing up Django media directory (host): $MEDIA_DIR ..."

if [[ ! -d "$MEDIA_DIR" ]]; then
  echo "ERROR: MEDIA_DIR does not exist or is not a directory: $MEDIA_DIR" >&2
  exit 1
fi

MEDIA_OUT="$OUTDIR/media.tar.gz"
MEDIA_PARENT="$(cd "$(dirname "$MEDIA_DIR")" && pwd)"
MEDIA_BASE="$(basename "$MEDIA_DIR")"

tar -C "$MEDIA_PARENT" -czf "$MEDIA_OUT" "$MEDIA_BASE"
log "Media archive written: $MEDIA_OUT"

# -------------------- 3) MinIO backup (mc mirror) --------------------
# Uses AWS_S3_ENDPOINT_URL (e.g. http://minio:9000) and runs mc in a container
# attached to the same network as the MinIO container.
MINIO_ENDPOINT="$AWS_S3_ENDPOINT_URL"
MC_ALIAS="local"

log "Backing up MinIO via mc mirror (endpoint=$MINIO_ENDPOINT) ..."

# Derive service name from endpoint host if possible (http(s)://<host>[:port])
# This is used to find the container & network. If parsing fails, default to "minio".
MINIO_HOST="$(printf "%s" "$MINIO_ENDPOINT" | sed -E 's#^https?://([^/:]+).*#\1#')"
MINIO_SERVICE="${MINIO_HOST:-minio}"

MINIO_CONTAINER_ID="$(docker compose ps -q "$MINIO_SERVICE" || true)"
if [[ -z "$MINIO_CONTAINER_ID" ]]; then
  echo "ERROR: Could not find a running container for MinIO service '$MINIO_SERVICE'." >&2
  echo "This was derived from AWS_S3_ENDPOINT_URL host='$MINIO_HOST'." >&2
  echo "Fix by setting AWS_S3_ENDPOINT_URL to use the docker-compose service name as host (e.g. http://minio:9000)." >&2
  exit 1
fi

MINIO_NET="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$MINIO_CONTAINER_ID" | head -n 1)"
if [[ -z "$MINIO_NET" ]]; then
  echo "ERROR: Could not determine MinIO container network." >&2
  exit 1
fi

log "MinIO service:  $MINIO_SERVICE"
log "MinIO network:  $MINIO_NET"

MINIO_DEST="$OUTDIR/minio"
mkdirp "$MINIO_DEST"

if [[ -z "$MINIO_BUCKET" ]]; then
  SRC_PATH="${MC_ALIAS}/"               # all buckets
  DEST_PATH="/backup/all-buckets"
  MIRROR_LABEL="ALL buckets"
else
  SRC_PATH="${MC_ALIAS}/${MINIO_BUCKET}"
  DEST_PATH="/backup/${MINIO_BUCKET}"
  MIRROR_LABEL="bucket '$MINIO_BUCKET'"
fi

log "Mirroring: $MIRROR_LABEL"

docker run --rm \
  --entrypoint /bin/sh \
  --network "$MINIO_NET" \
  -v "$(cd "$MINIO_DEST" && pwd)":/backup \
  -e MINIO_ENDPOINT="$MINIO_ENDPOINT" \
  -e MINIO_USER="$MINIO_ROOT_USER" \
  -e MINIO_PASS="$MINIO_ROOT_PASSWORD" \
  -e SRC_PATH="$SRC_PATH" \
  -e DEST_PATH="$DEST_PATH" \
  minio/mc:latest \
  -lc '
    set -euo pipefail
    mc alias set local "$MINIO_ENDPOINT" "$MINIO_USER" "$MINIO_PASS" >/dev/null
    mkdir -p "$DEST_PATH"
    mc mirror --overwrite --remove --preserve "$SRC_PATH" "$DEST_PATH"
  '

log "MinIO mirror written under: $MINIO_DEST"

# -------------------- Manifest --------------------
log "Writing manifest ..."
(
  cd "$OUTDIR"
  {
    echo "timestamp=$STAMP"
    echo "backup_root=$BACKUP_ROOT"
    echo "retention_days=$RETENTION_DAYS"
    echo "postgres_service=$PG_SERVICE"
    echo "postgres_db=$POSTGRES_DB"
    echo "postgres_user=$POSTGRES_USER"
    echo "media_dir=$MEDIA_DIR"
    echo "minio_endpoint=$MINIO_ENDPOINT"
    echo "minio_service=$MINIO_SERVICE"
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

# Extra guard: BACKUP_ROOT must exist and be a directory
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
#   gunzip -c backups/<STAMP>/postgres_<DB>.sql.gz | docker compose exec -T <POSTGRES_HOST> psql -U <POSTGRES_USER> <POSTGRES_DB>
#
# Media:
#   tar -xzf backups/<STAMP>/media.tar.gz -C <parent-of-MEDIA_DIR>
#
# MinIO:
#   Run mc mirror in reverse:
#     - All buckets:  mc mirror /backup/all-buckets/ local/
#     - One bucket:   mc mirror /backup/<bucket>/ local/<bucket>
###############################################################################