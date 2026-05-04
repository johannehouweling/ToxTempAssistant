# Swarm Deployment

This document describes how ToxTempAssistant runs on the **Docker Swarm cluster**
(managed at `tgx1` / `81.169.246.233`) alongside the legacy single-host deployment,
and the outstanding work to complete the migration.

## Status

**Current state:** running in parallel with legacy. Traefik on the cluster is configured to serve the **canonical hostname** (`toxtempassistant.vhp4safety.nl`) directly — there is no separate cutover/test subdomain.

| Side | URL | DNS | Status |
| --- | --- | --- | --- |
| Legacy | `https://toxtempassistant.vhp4safety.nl` | already pointed at legacy | canonical, currently serving real traffic |
| Swarm | same hostname (when DNS flips) | not yet pointed at the cluster | reachable from a laptop only via `/etc/hosts` override during cutover testing; serving Traefik's self-signed cert until DNS lands |

**Cutover is a pure DNS change.** When the admin updates the A record for `toxtempassistant.vhp4safety.nl` to point at `81.169.246.233`, Traefik's Let's Encrypt resolver issues a real cert via HTTP-01 and the swarm starts serving real public traffic. No further Traefik / compose edits required.

## Architecture

### Services

Five services in the `toxtempass` stack:

| Service | Image | Replicas | Notes |
| --- | --- | --- | --- |
| `djangoapp` | `ghcr.io/johannehouweling/toxtempassistant:vX.Y.Z` | 1 | Gunicorn on port 8000, Traefik-exposed |
| `postgres_for_django` | `postgres:17-alpine` | 1 | Stateful, single replica with gluster failover |
| `minio` | `minio/minio:RELEASE.2025-09-07T16-13-09Z` | 1 | Single-node FS mode |
| `minio_init` | `ghcr.io/johannehouweling/toxtempassistant-minio-init:vX.Y.Z` | 1 (one-shot) | Creates bucket / user / policy then exits |
| `backup` | `ghcr.io/johannehouweling/toxtempassistant-backup:vX.Y.Z` | 1 | Cron-driven via supercronic; off-cluster DR to HiDrive |

### Networks

- `core` (external overlay, cluster-managed) — Traefik attaches here. djangoapp joins for ingress.
- `db_network` (overlay, attachable) — postgres ↔ djangoapp / backup
- `data_network` (overlay, attachable) — minio ↔ djangoapp / minio_init / restore tooling

### Storage layout

All paths follow the cluster developer-guide convention `/<filesystem>/docker/<service>/{data,config}/`.

```
/mnt/gluster/docker/toxtempassistant/
├── data/
│   ├── db_data/              # postgres /var/lib/postgresql/data
│   ├── minio_blob_data/      # minio /data
│   └── myocyte/
│       ├── logs/             # gunicorn-*.log + backup-cron.log
│       └── static/           # collected static (admin/, …)
└── config/
    └── .env                  # mode 600, owned by jhouweling

/mnt/gluster/backups/toxtempassistant/   # postgres dumps + minio mirrors
```

The cluster's monthly cronjob automatically mirrors all of `/mnt/gluster/backups/` to off-cluster HiDrive — individual services don't write to hidrive directly.

Rationale:

- **gluster** is replicated across nodes (replica 2). A rescheduled task finds its data on whichever node it lands on.
- **`/mnt/gluster/backups/<service>/`** is the per-service backup target. Cluster admin's monthly job syncs this whole tree to HiDrive for off-site DR.

### Traefik routing

`docker-stack.yml` attaches djangoapp to the `core` network and labels it for Traefik:

```yaml
deploy:
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.toxtempassistant.rule=Host(`toxtempassistant.vhp4safety.nl`)"
    - "traefik.http.routers.toxtempassistant.entrypoints=websecure"
    - "traefik.http.routers.toxtempassistant.tls=true"
    - "traefik.http.routers.toxtempassistant.tls.certresolver=letsencrypt"
    - "traefik.http.services.toxtempassistant.loadbalancer.server.port=8000"
    - "traefik.docker.network=core"
```

After cutover, change the `Host(...)` rule to `toxtempassistant.vhp4safety.nl`.

## CI/CD chain

A push to `main` self-drives the full release-and-deploy chain:

```
git push (feat:/fix:)
  └─ CI                          → build + tests in djangoapp container
       └─ release.yml             → semantic-release tags vX.Y.Z (PAT-credentialed push)
            └─ tag push triggers publish-image.yml
                 ├─ matrix builds 3 images:
                 │     - ghcr.io/.../toxtempassistant
                 │     - ghcr.io/.../toxtempassistant-backup
                 │     - ghcr.io/.../toxtempassistant-minio-init
                 └─ release job creates GitHub Release (PAT-credentialed)
                      └─ release-published triggers deploy.yml
                           ├─ deploy-legacy (SSH compose pull && up -d)
                           └─ deploy-swarm (SSH-orchestrated `docker stack deploy`)
```

### Workflow files

- `.github/workflows/ci.yml` — pytest in djangoapp container; skips on bot-commits and workflow-only/markdown-only pushes
- `.github/workflows/release.yml` — `semantic-release version`; uses PAT so tag push fires downstream workflows
- `.github/workflows/publish-image.yml` — matrix builds + creates GH Release (gates deploy)
- `.github/workflows/deploy.yml` — two parallel jobs:
  - `deploy-legacy` — SSH to legacy, `compose pull && up -d`. Only fires on `release` events.
  - `deploy-swarm` — SSH to manager, `compose config | python-strip-profiles | docker stack deploy`. Fires on both `release` and `workflow_dispatch`. Has `continue-on-error: true` during cutover (release events only); `workflow_dispatch` runs fail loudly.

### `workflow_dispatch` for ad-hoc swarm deploys

Repo → Actions → **Deploy** → **Run workflow**, branch `main`, tag input = an existing release tag (e.g. `v3.16.3`). Use this to:

- Re-deploy after editing `.env` on gluster (env changes don't auto-trigger redeploy)
- Smoke-test deploy.yml changes without cutting a real release
- Recover from a transient failure

`deploy-legacy` is skipped on dispatch (only fires on `release` events) — no risk of re-deploying legacy by accident.

## One-time setup (per cluster)

These are required before the first `deploy-swarm` will work. Many are admin-side.

### GitHub repo settings

1. **Settings → Environments → `legacy-server`** with vars `REMOTE_SERVER_ADDRESS`, `REMOTE_SERVER_USERNAME`, `REMOTE_SERVER_PATH` and secrets `PA_TOKEN`, `GIT_ACTIONS`.
2. **Settings → Environments → `tgx1-server`** with vars `TGX1_IP_ADDRESS`, `TGX1_USERNAME` and secret `TGX1_DEPLOY_KEY` (private key whose public counterpart sits in `~jhouweling/.ssh/authorized_keys` on the cluster, which is symlinked to `/mnt/gluster/ssh-keys/jhouweling/authorized_keys`).
3. **Repo-level secret `PA_TOKEN`** — Personal Access Token with `repo` scope. Used by `release.yml` to push tags so downstream workflows fire.

### Cluster-side prep

Run on any swarm node (gluster + hidrive are shared):

```bash
mkdir -p /mnt/gluster/docker/toxtempassistant/data/{db_data,minio_blob_data}
mkdir -p /mnt/gluster/docker/toxtempassistant/data/myocyte/{logs,static}
mkdir -p /mnt/gluster/docker/toxtempassistant/config
mkdir -p /mnt/gluster/backups/toxtempassistant
```

All four are user-writable on gluster — no sudo, no admin involvement needed.

### Production `.env` on gluster

The runner pipes the rendered compose to the manager, but the **`.env` file lives on gluster** so secrets never traverse GitHub. Pipe from legacy through your laptop (legacy can't reach tgx1 directly):

```bash
ssh JenteHouweling@81.169.225.178 'cat ~/ToxTempAssistant/.env' | \
  ssh jhouweling@81.169.246.233 \
    'cat > /mnt/gluster/docker/toxtempassistant/config/.env && \
     chmod 600 /mnt/gluster/docker/toxtempassistant/config/.env'
```

**Required `.env` adjustments for the swarm side:**

```
POSTGRES_HOST=postgres_for_django
ALLOWED_HOSTS=toxtempassistant.vhp4safety.nl
CSRF_TRUSTED_ORIGINS=https://toxtempassistant.vhp4safety.nl
```

(Single hostname — same as legacy. Both deploys serve the same canonical URL; pre-cutover the swarm is only reachable via `/etc/hosts` override.)

### Verify cluster prerequisites

```bash
docker network ls | grep core              # external overlay must exist
docker service ls | grep -i traefik        # Traefik should be running on `core`
ls -la /mnt/gluster/docker/toxtempassistant/config/.env  # mode 600, jhouweling owner
```

## Data hydration (one-time, plus on every restore-from-legacy)

When swarm services first come up, postgres has only the schema initdb created and minio has no buckets. Use the daily backup tarball from legacy.

### 1. Get the backup onto the manager

From your laptop (legacy → laptop → tgx1 pipe — no intermediate file):

```bash
TS=$(ssh JenteHouweling@81.169.225.178 'ls -t ~/ToxTempAssistant/backups | head -1')
ssh JenteHouweling@81.169.225.178 "cd ~/ToxTempAssistant/backups/$TS && tar c ." | \
  ssh jhouweling@81.169.246.233 "mkdir -p /tmp/restore/$TS && cd /tmp/restore/$TS && tar x"
```

### 2. Restore minio objects via mc mirror (API-level restore)

On the manager, write the helper:

```bash
cat > /tmp/mirror.sh << 'EOF'
set -e
mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mirror --overwrite --preserve /source/"$BUCKET"/ local/"$BUCKET"/
mc ls local/"$BUCKET" | head
EOF
```

```bash
TS=$(ls -t /tmp/restore | head -1)
set -a; source /mnt/gluster/docker/toxtempassistant/config/.env; set +a
docker run --rm --network toxtempass_data_network -v /tmp/restore/$TS/minio:/source:ro -v /tmp/mirror.sh:/mirror.sh:ro -e MINIO_ROOT_USER -e MINIO_ROOT_PASSWORD -e BUCKET=$AWS_STORAGE_BUCKET_NAME --entrypoint sh minio/mc:latest /mirror.sh
```

### 3. Restore postgres dump

```bash
TS=$(ls -t /tmp/restore | head -1)
set -a; source /mnt/gluster/docker/toxtempassistant/config/.env; set +a
gunzip -c /tmp/restore/$TS/postgres_*.sql.gz | docker run --rm -i --network toxtempass_db_network -e PGPASSWORD="$POSTGRES_PASSWORD" postgres:17-alpine psql -h postgres_for_django -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Sanity-check:

```bash
docker run --rm --network toxtempass_db_network -e PGPASSWORD="$POSTGRES_PASSWORD" postgres:17-alpine psql -h postgres_for_django -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) FROM toxtempass_person;"
```

### Resetting state (if creds drift between deploys)

If `.env` credentials change after postgres has already initialized, postgres won't re-read them. Wipe + reinit:

```bash
docker service scale toxtempass_postgres_for_django=0
docker run --rm -v /mnt/gluster/docker/toxtempassistant/data/db_data:/dest busybox sh -c 'rm -rf /dest/* /dest/.[!.]*'
docker service scale toxtempass_postgres_for_django=1
```

Same pattern for minio:

```bash
docker service scale toxtempass_minio=0
docker run --rm -v /mnt/gluster/docker/toxtempassistant/data/minio_blob_data:/dest busybox sh -c 'rm -rf /dest/* /dest/.[!.]*'
docker service scale toxtempass_minio=1
docker service update --force toxtempass_minio_init  # rerun bucket/user/policy setup
```

Then re-do steps 2 and 3 above.

## Operations

### Watching the cluster

```bash
docker service ls                                    # snapshot of all services
docker service ps toxtempass_djangoapp --no-trunc    # current task + recent history
docker service logs -f toxtempass_djangoapp          # tail logs across all replicas
```

### Smoke-testing without DNS

From your laptop (replace IP if cluster moves):

```bash
sudo sh -c 'echo "81.169.246.233 toxtempassistant.vhp4safety.nl" >> /etc/hosts'
# Visit https://toxtempassistant.vhp4safety.nl in browser. Accept the cert
# warning until DNS lands and Let's Encrypt can issue.
```

Or via curl:

```bash
curl -k --resolve toxtempassistant.vhp4safety.nl:443:81.169.246.233 https://toxtempassistant.vhp4safety.nl/
```

To bypass Traefik and hit djangoapp directly over the overlay (debugging):

```bash
docker run --rm --network core busybox wget -qO- http://djangoapp:8000/ | head
```

### Scaling

Stateless service (djangoapp) only:

```bash
docker service scale toxtempass_djangoapp=3
```

Don't scale `postgres_for_django`, `minio`, or `backup` past 1 — they're stateful or singleton-by-design.

### Bouncing for env changes

`.env` changes only take effect on a fresh deploy. Trigger via:

- **GitHub UI** → Actions → Deploy → Run workflow → tag input → Run
- (Avoid `docker service update --force` for env changes — it doesn't re-render the spec from `.env`.)

## Outstanding items

### Required before public cutover

- [ ] **Backup directory exists.** `/mnt/gluster/backups/toxtempassistant/` must exist; if the parent `/mnt/gluster/backups/` is also missing, ask the cluster admin to seed it. Once present, `docker service scale toxtempass_backup=1` and the cron sidecar starts. Cluster's monthly job mirrors `/mnt/gluster/backups/` to off-site HiDrive automatically.
- [ ] **Public DNS A record swap** for `toxtempassistant.vhp4safety.nl → 81.169.246.233`. Required for Let's Encrypt to issue a real cert via Traefik *and* for public traffic to arrive at the cluster. This is the single act of "cutover".

### Already in place (informational)

- [x] All three docker images publish to ghcr.io on tag push.
- [x] Stack overlay (`docker-stack.yml`) wired with gluster paths, Traefik labels, restart policies.
- [x] `deploy-swarm` parallel job in `deploy.yml` with `workflow_dispatch` for ad-hoc runs.
- [x] Production data restored on swarm (postgres dump + minio mirror, last refreshed `2026-05-03_020000`).
- [x] Whitenoise middleware added so `/static/*` serves from gunicorn (no external nginx needed). Harmless on legacy because legacy's external nginx wins on the request path.

## Cutover plan

When you're ready to cut over (after a final data sync, ideally during a maintenance window):

1. **Final data restore** from a fresh legacy backup (steps under "Data hydration"). This is the one critical pre-flight — minimizes data lag at the moment of swap.
2. **DNS swap.** Cluster admin updates the A record for `toxtempassistant.vhp4safety.nl` to point at `81.169.246.233`. From that moment, public traffic flows to Traefik on the cluster. Traefik already has the Host rule for the canonical name, so no compose / stack edit is needed — Traefik just starts serving. Within ~60 seconds, Let's Encrypt's HTTP-01 challenge succeeds and Traefik replaces the self-signed cert with a real one.
3. **Stop legacy** — `docker compose down` on the legacy server. Keep the host running with volumes intact for a few days as a rollback option.
4. **Drop the cutover scaffolding** in `deploy.yml`:
   - Delete the `deploy-legacy` job entirely.
   - Remove `continue-on-error: ${{ github.event_name == 'release' }}` from `deploy-swarm`.
5. **Refactor compose** (separate PR): replace the `compose config | python-strip-profiles | stack deploy` pipeline with a single `docker-compose.swarm.yml` written in stack-deploy-native form. Delete `docker-stack.yml` and the python filter. (This is a follow-up cleanup, not blocking.)
6. **Decommission legacy server** once the soak period after cutover is clean.

Rollback path (if anything is wrong post-cutover): re-point DNS back at legacy, restart `docker compose up -d` on legacy. No data loss because legacy's data wasn't deleted in step 3 — only stopped.

## Known caveats and follow-ups

- **`backup` uses `/var/run/docker.sock`.** Single-node-coupled — if backup and postgres land on different nodes, `docker exec postgres_for_django` from inside the backup container won't find postgres. Stopgap: pin both to the same node via `node.labels.storage == true` (commented placement blocks already in `docker-stack.yml`, ready to uncomment after labelling). Real fix (post-cutover): refactor `backup.sh` to use TCP (`pg_dump -h postgres_for_django`) and run minio mirror as a sibling task instead of `docker run` against the local socket.
- **GlusterFS POSIX locking quirks.** Postgres uses file locks. Gluster supports them but in rare situations of network partition you can see lock-contention errors. If postgres logs `could not acquire lock`, the recovery is usually to scale postgres to 0, wait for lock to clear, scale back to 1.
- **MinIO single-drive FS mode** is supported but Docker has been deprecating it in favor of erasure-coded distributed mode. Distributed mode needs ≥4 drives and is overkill for current load. Revisit if you ever get a multi-disk postgres setup.

---

For migration history and deferred-cleanup notes, see the swarm-migration entry in `~/.claude/projects/.../memory/swarm_migration.md`.
