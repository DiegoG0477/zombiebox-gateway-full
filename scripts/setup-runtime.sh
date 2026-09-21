#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
umask 077
runtime="$repo/.local/gateway"
mkdir -p "$runtime/state" "$runtime/config" "$runtime/media"
if [[ ! -f "$runtime/config/providers.json" ]]; then
  printf '{}\n' > "$runtime/config/providers.json"
fi
if [[ ! -f "$runtime/compose.env" ]]; then
  printf 'ZOMBIE_UID=%s\nZOMBIE_GID=%s\n' "$(id -u)" "$(id -g)" > "$runtime/compose.env"
fi
chmod 700 "$runtime" "$runtime/state" "$runtime/config" "$runtime/media"
chmod 600 "$runtime/config/providers.json" "$runtime/compose.env"
printf 'Runtime prepared at %s\n' "$runtime"
printf 'Configure providers through client Settings or config/providers.json. Existing configuration is preserved.\n'
