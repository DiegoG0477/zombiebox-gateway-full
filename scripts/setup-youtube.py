#!/usr/bin/env python3
"""Prepare an opt-in worker without printing or replacing existing secrets."""

import argparse
import json
import os
import secrets
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--enable", action="store_true")
parser.add_argument("--native", action="store_true")
args = parser.parse_args()
root = Path(os.environ.get("ZOMBIE_RUNTIME_ROOT", Path(__file__).resolve().parents[1]))
os.umask(0o077)
directory = root / ".local/youtube"
directory.mkdir(parents=True, exist_ok=True)
directory.chmod(0o700)
worker = directory / "youtube.json"
if not worker.exists():
    worker.write_text(
        json.dumps(
            {
                "token": secrets.token_urlsafe(32),
                "cookie": "",
                "poToken": "",
                "visitorData": "",
            },
            indent=2,
        )
        + "\n"
    )
worker.chmod(0o600)
config = json.loads(worker.read_text())
if not isinstance(config.get("token"), str) or len(config["token"]) < 32:
    raise SystemExit("Existing worker token is invalid; preserved configuration.")
providers = root / ".local/gateway/config/providers.json"
data = json.loads(providers.read_text())
if "youtube" not in data:
    data["youtube"] = {
        "enabled": args.enable,
        "url": "http://127.0.0.1:8091" if args.native else "http://youtube:8091",
        "token": config["token"],
        "catalogId": "",
    }
elif args.enable:
    data["youtube"]["enabled"] = True
    if data["youtube"].get("url") in ("http://127.0.0.1:8091", "http://youtube:8091"):
        data["youtube"]["url"] = (
            "http://127.0.0.1:8091" if args.native else "http://youtube:8091"
        )
temporary = providers.with_suffix(".tmp")
temporary.write_text(json.dumps(data, indent=2) + "\n")
temporary.replace(providers)
providers.chmod(0o600)
print(
    "Private YouTube worker configuration prepared. Existing credentials and addresses were preserved."
)
