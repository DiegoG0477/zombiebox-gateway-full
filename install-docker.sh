#!/bin/sh
# Install one immutable Full release using only curl, sha256sum and Docker Compose.
set -eu

VERSION=
REPOSITORY=ZombieBox-tv/zombiebox-gateway-full
DESTINATION=${XDG_DATA_HOME:-"$HOME/.local/share"}/zombiebox/full/releases
CHANNEL_URL=${ZOMBIE_INSTALL_CHANNEL_URL:-"https://raw.githubusercontent.com/$REPOSITORY/main/install-channel.txt"}

usage() {
    printf 'Usage: sh install-docker.sh [--version vX.Y.Z] [--directory PATH]\n' >&2
    exit 2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --version)
            [ "$#" -ge 2 ] || usage
            VERSION=$2
            shift 2
            ;;
        --directory)
            [ "$#" -ge 2 ] || usage
            DESTINATION=$2
            shift 2
            ;;
        *) usage ;;
    esac
done

for required in curl sha256sum docker mktemp; do
    command -v "$required" >/dev/null 2>&1 || {
        printf 'Missing required command: %s\n' "$required" >&2
        exit 1
    }
done

if [ -z "$VERSION" ]; then
    VERSION=$(curl --fail --location --silent --show-error --retry 3 \
        --connect-timeout 10 --max-time 30 --max-filesize 128 "$CHANNEL_URL") || {
        printf 'Could not resolve the current installable Full release.\n' >&2
        exit 1
    }
fi
case "$VERSION" in
    v[0-9]*.[0-9]*.[0-9]*) ;;
    *) usage ;;
esac
case "$VERSION" in
    *[!a-zA-Z0-9.-]*) usage ;;
esac

docker compose version >/dev/null

mkdir -p "$DESTINATION"
DESTINATION=$(cd "$DESTINATION" && pwd -P)
TARGET=$DESTINATION/$VERSION
BASE=${ZOMBIE_RELEASE_BASE_URL:-"https://github.com/$REPOSITORY/releases/download/$VERSION"}

if [ ! -d "$TARGET" ]; then
    STAGING=$(mktemp -d "$DESTINATION/.download.XXXXXXXX")
    trap 'rm -rf "$STAGING"' EXIT HUP INT TERM
    for asset in compose.yaml seccomp.json release.lock.json README.md LICENSE NOTICE SHA256SUMS; do
        curl --fail --location --silent --show-error --retry 3 \
            --connect-timeout 10 --max-time 120 \
            "$BASE/$asset" -o "$STAGING/$asset"
    done
    (cd "$STAGING" && sha256sum --quiet --check SHA256SUMS)
    if ! grep -Fq '"publicationReady": true' "$STAGING/release.lock.json"; then
        printf 'Release manifest has not passed the publication gate.\n' >&2
        exit 1
    fi
    if ! grep -Fq '"zombieboxVersion": "'"$VERSION"'"' "$STAGING/release.lock.json"; then
        printf 'Release manifest version differs from requested version.\n' >&2
        exit 1
    fi
    mv "$STAGING" "$TARGET"
    trap - EXIT HUP INT TERM
else
    (cd "$TARGET" && sha256sum --quiet --check SHA256SUMS)
fi

printf 'Starting ZombieBox Full %s from %s\n' "$VERSION" "$TARGET"
(cd "$TARGET" && docker compose pull && docker compose up -d)
printf 'Read the private operator code: docker compose -f "%s/compose.yaml" exec gateway cat /config/operator.code\n' "$TARGET"
