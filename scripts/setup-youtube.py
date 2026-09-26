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
parser.add_argument(
    "--pot", action="store_true", help="Enable optional per-video PO token HD resolver"
)
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

if args.pot:
    pot_directory = root / ".local/youtube-pot"
    pot_directory.mkdir(parents=True, exist_ok=True)
    pot_directory.chmod(0o700)
    pot_worker = pot_directory / "pot.json"
    upstream_url = "http://127.0.0.1:8091" if args.native else "http://youtube:8091"
    bgutil_url = (
        "http://127.0.0.1:4416" if args.native else "http://bgutil-provider:4416"
    )
    if not pot_worker.exists():
        pot_worker.write_text(
            json.dumps(
                {
                    "token": config["token"],
                    "upstream_url": upstream_url,
                    "bgutil_url": bgutil_url,
                    "cooldown_seconds": 300,
                    "timeout_seconds": 12,
                },
                indent=2,
            )
            + "\n"
        )
    pot_worker.chmod(0o600)
    pot_config = json.loads(pot_worker.read_text())
    if (
        pot_config.get("token") != config["token"]
        or pot_config.get("upstream_url") != upstream_url
        or pot_config.get("bgutil_url") != bgutil_url
    ):
        raise SystemExit(
            "Existing YouTube PO resolver identity or route does not match; "
            "preserved configuration. Reconcile it before enabling the profile."
        )

target_url = (
    ("http://127.0.0.1:8097" if args.native else "http://youtube-pot:8097")
    if args.pot
    else ("http://127.0.0.1:8091" if args.native else "http://youtube:8091")
)

providers = root / ".local/gateway/config/providers.json"
data = json.loads(providers.read_text())
if args.pot and "youtube" in data and data["youtube"].get("token") != config["token"]:
    raise SystemExit(
        "Existing gateway YouTube token does not match its worker; "
        "preserved configuration. Reconcile it before enabling the profile."
    )
managed_urls = (
    "http://127.0.0.1:8091",
    "http://youtube:8091",
    "http://127.0.0.1:8097",
    "http://youtube-pot:8097",
)
if args.pot and "youtube" in data and data["youtube"].get("url") not in managed_urls:
    raise SystemExit(
        "Existing gateway YouTube route is custom; preserved configuration. "
        "Reconcile it before enabling the profile."
    )
if "youtube" not in data:
    data["youtube"] = {
        "enabled": args.enable,
        "url": target_url,
        "token": config["token"],
        "catalogId": "",
    }
else:
    if args.enable:
        data["youtube"]["enabled"] = True
    if args.pot:
        data["youtube"]["url"] = target_url
    elif args.enable and data["youtube"].get("url") in managed_urls:
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
