FROM alpine:3.23

RUN apk add --no-cache \
    bash \
    coreutils \
    findutils \
    grep \
    sed \
    gzip \
    tar \
    git \
    tzdata \
    dcron \
    docker-cli \
    docker-cli-compose

WORKDIR /work

COPY myocyte/dockerfiles/backup-scheduler/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]