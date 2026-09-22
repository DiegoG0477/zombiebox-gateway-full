#!/usr/bin/env bash
# Maintainer-only build: end users run the resulting image through Compose.
set -euo pipefail
full=$(cd "$(dirname "$0")/.." && pwd)
core=$(python3 "$full/scripts/dependencies.py" check gateway-core)
assets="$full/.local/bootstrap-assets"
mkdir -p "$assets/probes"
python3 "$core/scripts/generate-probes.py" --output "$assets/probes"
python3 "$core/scripts/generate-extended-probes.py" --output "$assets/probes"
cp "$core/wrappers/mediamtx/mediamtx.yml" "$assets/mediamtx.yml"
docker build --file "$full/Dockerfile.bootstrap" --build-context "assets=$assets" \
    --tag "${ZOMBIE_BOOTSTRAP_IMAGE:-zombie-box-tv/bootstrap:0.1.0-dev.45}" "$full"
