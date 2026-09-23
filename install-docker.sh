#!/bin/sh
# Install one immutable Full release using only curl, sha256sum and Docker Compose.
set -eu

VERSION=
REPOSITORY=ZombieBox-tv/zombiebox-gateway-full
DESTINATION=$PWD
DESTINATION_MODE=current
CHANNEL_URL=${ZOMBIE_INSTALL_CHANNEL_URL:-"https://raw.githubusercontent.com/$REPOSITORY/main/install-channel.txt"}

usage() {
    printf 'Usage: sh install-docker.sh [--version vX.Y.Z] [--directory PATH | --user-data]\n' >&2
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
            [ "$DESTINATION_MODE" = current ] || usage
            DESTINATION=$2
            DESTINATION_MODE=directory
            shift 2
            ;;
        --user-data)
            [ "$DESTINATION_MODE" = current ] || usage
            DESTINATION_MODE=user-data
            shift
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

if [ "$DESTINATION_MODE" = user-data ]; then
    DESTINATION=${XDG_DATA_HOME:-"$HOME/.local/share"}/zombiebox/full/releases/$VERSION
fi
mkdir -p "$DESTINATION"
TARGET=$(cd "$DESTINATION" && pwd -P)
BASE=${ZOMBIE_RELEASE_BASE_URL:-"https://github.com/$REPOSITORY/releases/download/$VERSION"}

if [ ! -f "$TARGET/SHA256SUMS" ]; then
    for asset in compose.yaml seccomp.json release.lock.json README.md LICENSE NOTICE SHA256SUMS; do
        if [ -e "$TARGET/$asset" ] || [ -L "$TARGET/$asset" ]; then
            printf 'Installation file already exists: %s\nUse a clean directory or --directory PATH.\n' "$TARGET/$asset" >&2
            exit 1
        fi
    done
    STAGING=$(mktemp -d "$TARGET/.zombiebox-download.XXXXXXXX")
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
    for asset in compose.yaml seccomp.json release.lock.json README.md LICENSE NOTICE SHA256SUMS; do
        mv "$STAGING/$asset" "$TARGET/$asset"
    done
else
    (cd "$TARGET" && sha256sum --quiet --check SHA256SUMS)
fi
if ! grep -Fq '"publicationReady": true' "$TARGET/release.lock.json"; then
    printf 'Release manifest has not passed the publication gate.\n' >&2
    exit 1
fi
if ! grep -Fq '"zombieboxVersion": "'"$VERSION"'"' "$TARGET/release.lock.json"; then
    printf 'Existing installation differs from the selected release. Use another directory.\n' >&2
    exit 1
fi

printf 'Starting ZombieBox Full %s from %s\n' "$VERSION" "$TARGET"
(cd "$TARGET" && docker compose pull && docker compose up -d)
printf 'Compose files: %s\nFrom that directory, read the private operator code with: docker compose exec gateway cat /config/operator.code\n' "$TARGET"
