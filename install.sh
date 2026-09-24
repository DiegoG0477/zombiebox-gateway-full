#!/usr/bin/env bash
# Source checkout or prebuilt release bundle; configuration lives outside either.
set -euo pipefail
component=$(cd "$(dirname "$0")" && pwd)
runtime_name=full
project_name=zombie-box-tv
if [[ -f "$component/images.lock.json" ]]; then
    runtime_name=full-test
    project_name=zombie-full-test
fi
export ZOMBIE_RUNTIME_ROOT=${ZOMBIE_RUNTIME_ROOT:-${XDG_DATA_HOME:-$HOME/.local/share}/zombiebox/$runtime_name}
export ZOMBIE_COMPOSE_PROJECT=${ZOMBIE_COMPOSE_PROJECT:-$project_name}
export ZOMBIE_FULL_DIR=$component
profiles=()
prepare_only=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            case ${2:-} in
                youtube | youtube-receiver | spotify | airplay | threadfin | rebrowser) profiles+=("$2") ;;
                *)
                    echo 'Unknown or missing optional profile.' >&2
                    exit 2
                    ;;
            esac
            shift 2
            ;;
        --prepare-only)
            prepare_only=true
            shift
            ;;
        *)
            echo 'Usage: bash install.sh [--prepare-only] [--profile youtube|youtube-receiver|spotify|airplay|threadfin|rebrowser]' >&2
            exit 2
            ;;
    esac
done
for program in python3 docker; do command -v "$program" >/dev/null; done
docker compose version >/dev/null
cd "$component"
if [[ -f release.compose.json ]]; then
    sha256sum --check --status SHA256SUMS || {
        echo 'Release file verification failed; configuration and services were not changed.' >&2
        exit 1
    }
    export ZOMBIE_CORE_DIR=$component/assets
    composition=$component/release.compose.json
else
    export ZOMBIE_CORE_DIR
    ZOMBIE_CORE_DIR=$(python3 scripts/dependencies.py fetch gateway-core)
    # The dependency helper may print progress; obtain the checked path separately.
    ZOMBIE_CORE_DIR=$(python3 scripts/dependencies.py check gateway-core)
    composition=$component/compose.yaml
fi
bash scripts/setup-runtime.sh
python3 scripts/setup-youtube.py
python3 scripts/setup-services.py
if [[ -f release.compose.json ]]; then
    python3 - "$component/assets/probes" "$ZOMBIE_RUNTIME_ROOT/.local/gateway/probes" <<'PYTHON'
import pathlib, shutil, sys
source, target = map(pathlib.Path, sys.argv[1:])
for fixture in source.iterdir():
    if fixture.is_file() and not (target / fixture.name).exists():
        shutil.copy2(fixture, target / fixture.name)
PYTHON
else
    python3 "$ZOMBIE_CORE_DIR/scripts/generate-probes.py" --output "$ZOMBIE_RUNTIME_ROOT/.local/gateway/probes"
    python3 "$ZOMBIE_CORE_DIR/scripts/generate-extended-probes.py" --output "$ZOMBIE_RUNTIME_ROOT/.local/gateway/probes"
fi
options=()
for profile in "${profiles[@]}"; do
    options+=(--profile "$profile")
    if [[ $profile == youtube ]]; then
        python3 scripts/setup-youtube.py --enable
    else
        python3 scripts/setup-services.py --enable "${profile//-/_}"
    fi
done
compose=(docker compose --project-name "$ZOMBIE_COMPOSE_PROJECT" --project-directory "$component" --env-file "$ZOMBIE_RUNTIME_ROOT/.local/gateway/compose.env" -f "$composition" "${options[@]}")
"${compose[@]}" config --quiet
if $prepare_only; then
    echo "Configuration prepared. Nothing started. Runtime: $ZOMBIE_RUNTIME_ROOT"
    exit
fi
if [[ -f images.lock.json ]]; then
    python3 scripts/load-images.py
elif [[ -f release.compose.json ]]; then
    "${compose[@]}" pull --quiet
else
    if [[ " ${profiles[*]} " =~ (spotify|airplay|threadfin) ]]; then
        python3 scripts/setup-services.py --sources
    fi
    "${compose[@]}" build
fi
"${compose[@]}" up -d --no-build --wait --wait-timeout 120
printf 'Gateway started. Open Client and select the discovered gateway, then configure providers in Settings.\nPrivate runtime: %s\n' "$ZOMBIE_RUNTIME_ROOT"
