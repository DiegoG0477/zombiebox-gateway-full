#!/usr/bin/env bash
set -euo pipefail
repo=${ZOMBIE_RUNTIME_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
umask 077
runtime="$repo/.local/gateway"
mkdir -p "$runtime/state" "$runtime/config" "$runtime/media"
if [[ ! -f "$runtime/config/providers.json" ]]; then
    printf '{}\n' >"$runtime/config/providers.json"
fi
if [[ ! -f "$runtime/compose.env" ]]; then
    printf 'ZOMBIE_UID=%s\nZOMBIE_GID=%s\n' "$(id -u)" "$(id -g)" >"$runtime/compose.env"
fi
python3 - "$runtime/compose.env" <<'PYTHON'
import pathlib,secrets,sys
p=pathlib.Path(sys.argv[1]);text=p.read_text()
if not any(line.startswith('ZOMBIE_RELAY_ADMIN_TOKEN=') for line in text.splitlines()):
    with p.open('a') as f:f.write('\nZOMBIE_RELAY_ADMIN_TOKEN='+secrets.token_hex(32)+'\n')
PYTHON
chmod 700 "$runtime" "$runtime/state" "$runtime/config" "$runtime/media"
chmod 600 "$runtime/config/providers.json" "$runtime/compose.env"
printf 'Runtime prepared at %s\n' "$runtime"
printf 'Configure providers through client Settings or config/providers.json. Existing configuration is preserved.\n'

mkdir -p "$runtime/probes"
