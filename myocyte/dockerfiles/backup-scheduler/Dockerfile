FROM alpine:3.23

# pg_dump matches the postgres:17-alpine server major version. mc is fetched
# from the official MinIO release channel rather than alpine's `minio-mc`
# package because the latter installs the binary as `mcli` (to avoid a name
# collision with midnight-commander), and our script invokes `mc`.
RUN apk add --no-cache \
    bash \
    coreutils \
    findutils \
    grep \
    sed \
    gzip \
    tar \
    tzdata \
    postgresql17-client \
    ca-certificates \
    curl

RUN curl -fsSLo /usr/local/bin/mc https://dl.min.io/client/mc/release/linux-amd64/mc \
 && chmod +x /usr/local/bin/mc

# Latest releases available at https://github.com/aptible/supercronic/releases
ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.2.43/supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=f97b92132b61a8f827c3faf67106dc0e4467ccf2 \
    SUPERCRONIC=supercronic-linux-amd64

RUN curl -fsSLO "$SUPERCRONIC_URL" \
 && echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - \
 && chmod +x "$SUPERCRONIC" \
 && mv "$SUPERCRONIC" "/usr/local/bin/${SUPERCRONIC}" \
 && ln -s "/usr/local/bin/${SUPERCRONIC}" /usr/local/bin/supercronic

WORKDIR /work

# Bake the backup script into the image so the container is self-contained:
# no `./:/work:ro` mount of the host repo is needed at runtime. Required for
# Docker Swarm, where each node has no notion of "the repo on this server".
COPY backup.sh /usr/local/bin/backup.sh
COPY myocyte/dockerfiles/backup-scheduler/entrypoint.sh /entrypoint.sh
RUN chmod +x /usr/local/bin/backup.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]