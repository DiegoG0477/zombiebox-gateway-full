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
python3 - "$runtime/compose.env" "$runtime/config/operator.code" <<'PYTHON'
import pathlib
import re
import secrets
import sys

env_path, code_path = map(pathlib.Path, sys.argv[1:])
lines = env_path.read_text().splitlines()
if not any(line.startswith("ZOMBIE_RELAY_ADMIN_TOKEN=") for line in lines):
    lines.append("ZOMBIE_RELAY_ADMIN_TOKEN=" + secrets.token_hex(32))

configured = [line.partition("=")[2] for line in lines if line.startswith("ZOMBIE_PAIRING_CODE=")]
if len(configured) > 1:
    raise SystemExit("Duplicate ZOMBIE_PAIRING_CODE values in private Compose environment")
if code_path.exists():
    code = code_path.read_text().strip()
elif configured and configured[0]:
    code = configured[0]
else:
    code = str(secrets.randbelow(900000) + 100000)
if not re.fullmatch(r"[0-9]{6}", code):
    raise SystemExit("Invalid private operator code; expected six digits")
if configured and configured[0] and configured[0] != code:
    raise SystemExit("Private operator code differs from Compose environment")
if not code_path.exists():
    code_path.write_text(code + "\n")
    code_path.chmod(0o600)
if not configured or not configured[0]:
    lines = [line for line in lines if not line.startswith("ZOMBIE_PAIRING_CODE=")]
    lines.append("ZOMBIE_PAIRING_CODE=" + code)
env_path.write_text("\n".join(lines) + "\n")
PYTHON
chmod 700 "$runtime" "$runtime/state" "$runtime/config" "$runtime/media"
chmod 600 "$runtime/config/providers.json" "$runtime/compose.env"
chmod 600 "$runtime/config/operator.code"
printf 'Runtime prepared at %s\n' "$runtime"
printf 'Configure providers through client Settings or config/providers.json. Existing configuration is preserved.\n'

mkdir -p "$runtime/probes"
