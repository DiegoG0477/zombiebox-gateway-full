#!/usr/bin/env bash
# Run synthetic HTTP A/V fixtures against the FFmpeg shipped in the Full image.
set -euo pipefail
full_dir=$(cd "$(dirname "$0")/.." && pwd)
core_dir=${ZOMBIE_CORE_DIR:-$full_dir/../gateway-core}
image=${ZOMBIE_SMOKE_IMAGE:-zombie-box-tv/gateway:0.1.0-dev.13}
fixture_dir=$(mktemp -d)
trap 'rm -rf "$fixture_dir"' EXIT
CGO_ENABLED=0 GOMAXPROCS=2 go -C "$core_dir/gateway" test -p 2 -c -o "$fixture_dir/media.test" ./internal/media
chmod 755 "$fixture_dir" "$fixture_dir/media.test"
docker run --rm --network none --read-only --memory 512m --cpus 2 --pids-limit 96 \
    --cap-drop ALL --security-opt no-new-privileges:true \
    --tmpfs /tmp:rw,nosuid,nodev,size=64m \
    -v "$fixture_dir:/fixtures:ro,Z" --entrypoint /fixtures/media.test \
    "$image" -test.v -test.run '^(TestRemote|TestLive)' -test.timeout 90s
