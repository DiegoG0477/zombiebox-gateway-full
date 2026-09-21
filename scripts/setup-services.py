#!/usr/bin/env python3
"""Prepare optional service configuration; credentials and custom inputs are retained."""

import argparse
import json
import os
import secrets
from pathlib import Path

from lib.private_config import configure_provider, ensure_config, write_json
from lib.source_archive import prepare_sources
from lib.spotify import prepare_spotify


def prepare_receiver(root, providers, enabled):
    config = ensure_config(
        root / ".local/youtube-receiver/receiver.json",
        {
            "token": secrets.token_hex(32),
            "listen": "0.0.0.0",
            "port": 8095,
            "dialPort": 8096,
        },
    )
    configure_provider(
        providers,
        "youtube_receiver",
        "http://host.docker.internal:8095",
        config["token"],
        enabled == "youtube_receiver",
    )


def prepare_browser(root, providers, enabled):
    config = ensure_config(
        root / ".local/rebrowser/browser.json", {"token": secrets.token_hex(32)}
    )
    configure_provider(
        providers,
        "rebrowser",
        "http://rebrowser:8094",
        config["token"],
        enabled == "rebrowser",
    )


def prepare_media_worker(root, providers, name, port, enabled):
    folder = root / ".local" / name
    (folder / "state").mkdir(parents=True, exist_ok=True, mode=0o700)
    defaults = {
        "mode": name,
        "listen": f"0.0.0.0:{port}",
        "token": secrets.token_hex(32),
        "stateDir": "/state",
    }
    if name == "airplay":
        defaults["pin"] = f"{secrets.randbelow(10000):04d}"
    config = ensure_config(folder / "worker.json", defaults)
    host = "host.docker.internal" if name == "airplay" else name
    configure_provider(
        providers, name, f"http://{host}:{port}", config["token"], enabled == name
    )
    if name == "spotify":
        prepare_spotify(folder)
    folder.chmod(0o700)
    (folder / "state").chmod(0o700)
    (folder / "worker.json").chmod(0o600)


def prepare_threadfin(root, providers, enabled):
    (root / ".local/threadfin").mkdir(exist_ok=True)
    if enabled != "threadfin":
        return
    current = providers.get("iptv", {})
    if current.get("url") and "/m3u/threadfin.m3u" not in current["url"]:
        raise ValueError(
            "Existing IPTV input preserved. Import it in Threadfin and explicitly select the Threadfin export in gateway settings."
        )
    providers["iptv"] = {
        "enabled": True,
        "url": "http://threadfin:34400/m3u/threadfin.m3u",
        "epgUrl": "http://threadfin:34400/xmltv/threadfin.xml",
    }


def prepare(root, enabled=None, sources=False):
    provider_file = root / ".local/gateway/config/providers.json"
    providers = json.loads(provider_file.read_text())
    prepare_receiver(root, providers, enabled)
    prepare_browser(root, providers, enabled)
    prepare_media_worker(root, providers, "spotify", 8092, enabled)
    prepare_media_worker(root, providers, "airplay", 8093, enabled)
    prepare_threadfin(root, providers, enabled)
    write_json(provider_file, providers)
    if sources:
        prepare_sources(root, {"go-librespot", "uxplay", "threadfin"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--enable",
        choices=("spotify", "airplay", "threadfin", "rebrowser", "youtube_receiver"),
    )
    parser.add_argument("--sources", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        prepare(
            Path(
                os.environ.get(
                    "ZOMBIE_RUNTIME_ROOT", Path(__file__).resolve().parents[1]
                )
            ),
            args.enable,
            args.sources,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print(
        "Optional service configuration prepared; secrets and existing provider inputs preserved."
    )


if __name__ == "__main__":
    main()
