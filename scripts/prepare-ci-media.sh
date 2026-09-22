#!/usr/bin/env bash
# Use the packaged FFmpeg in fresh CI runners; never require a host codec install.
set -euo pipefail
component=$(cd "$(dirname "$0")/.." && pwd)
cd "$component"
core=$(python3 scripts/dependencies.py check gateway-core)
docker build --file Dockerfile --tag zombie-box-tv/ci-media:dev35 "$core"
image=$(docker image inspect --format '{{.Id}}' zombie-box-tv/ci-media:dev35)
mkdir -p .local/ci-tools
for tool in ffmpeg ffprobe; do
    cat >".local/ci-tools/$tool" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
exec docker run --rm --network none --user "\$(id -u):\$(id -g)" \\
    --volume "\$PWD:\$PWD" --workdir "\$PWD" --entrypoint "$tool" "$image" "\$@"
SCRIPT
    chmod +x ".local/ci-tools/$tool"
done
if [[ -n ${GITHUB_PATH:-} ]]; then
    printf '%s\n' "$component/.local/ci-tools" >>"$GITHUB_PATH"
fi
