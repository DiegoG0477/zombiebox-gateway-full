#!/usr/bin/env bash
# Operate a prepared bundle using the same private runtime/project as install.sh.
set -euo pipefail
component=$(cd "$(dirname "$0")" && pwd)
runtime_name=full
project_name=zombie-box-tv
if [[ -f "$component/images.lock.json" ]]; then
    runtime_name=full-test
    project_name=zombie-full-test
fi
export ZOMBIE_RUNTIME_ROOT=${ZOMBIE_RUNTIME_ROOT:-${XDG_DATA_HOME:-$HOME/.local/share}/zombiebox/$runtime_name}
export ZOMBIE_FULL_DIR=$component
project=${ZOMBIE_COMPOSE_PROJECT:-$project_name}
action=${1:-status}
shift || true
case $action in
    status | logs | stop | down) ;;
    *)
        echo 'Usage: bash control.sh status|logs|stop|down [service ...]' >&2
        exit 2
        ;;
esac
for service in "$@"; do
    case $service in
        gateway | discovery | mediamtx | youtube | youtube-receiver | spotify | airplay | threadfin | rebrowser) ;;
        *)
            echo 'Unknown service.' >&2
            exit 2
            ;;
    esac
done
if [[ -f "$component/release.compose.json" ]]; then
    export ZOMBIE_CORE_DIR=$component/assets
    composition=$component/release.compose.json
else
    export ZOMBIE_CORE_DIR
    ZOMBIE_CORE_DIR=$(python3 "$component/scripts/dependencies.py" check gateway-core)
    composition=$component/compose.yaml
fi
compose=(docker compose --project-name "$project" --project-directory "$component" --env-file "$ZOMBIE_RUNTIME_ROOT/.local/gateway/compose.env" -f "$composition" --profile '*')
case $action in
    status) "${compose[@]}" ps --all "$@" ;;
    logs) "${compose[@]}" logs --tail 150 "$@" ;;
    stop) "${compose[@]}" stop "$@" ;;
    down)
        if [[ $# -gt 0 ]]; then
            echo 'down applies to this complete project; omit service names.' >&2
            exit 2
        fi
        "${compose[@]}" down
        ;;
esac
