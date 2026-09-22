#!/usr/bin/env python3
"""Prepare a source-free installation bundle from reviewed image digests. No publishing."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from lib.bundle_assets import checksums, copy_assets
from lib.compose_bundle import portable_networks

ROOT = Path(__file__).resolve().parents[1]
SERVICES = {
    "gateway",
    "discovery",
    "youtube",
    "youtube-receiver",
    "spotify",
    "airplay",
    "threadfin",
    "rebrowser",
}


def release_compose(compose, images):
    if set(images) != SERVICES:
        raise ValueError(
            "Provide an image digest for every first-party service, including optional workers"
        )
    for value in images.values():
        if not re.fullmatch(r"ghcr\.io/[a-z0-9./_-]+@sha256:[a-f0-9]{64}", value):
            raise ValueError("Release images must use reviewed GHCR sha256 digests")
    if images["gateway"] != images["discovery"]:
        raise ValueError("Gateway and discovery must use the same image")
    portable_networks(compose)
    for name, service in compose["services"].items():
        service.pop("build", None)
        if name in images:
            service["image"] = images[name]
        for mount in service.get("volumes", []):
            # Compose cannot infer bind mounts while placeholders are unexpanded.
            if mount.get("source", "").startswith(
                ("${ZOMBIE_RUNTIME_ROOT", "${ZOMBIE_CORE_DIR")
            ):
                mount["type"] = "bind"
                mount.pop("volume", None)
                mount.setdefault("bind", {})["create_host_path"] = False
    return compose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core = Path(
        subprocess.check_output(
            ["python3", "scripts/dependencies.py", "check", "gateway-core"],
            cwd=ROOT,
            text=True,
        ).strip()
    )
    compose = json.loads(
        subprocess.check_output(
            [
                "docker",
                "compose",
                "-f",
                "compose.yaml",
                "--profile",
                "*",
                "config",
                "--no-interpolate",
                "--no-path-resolution",
                "--format",
                "json",
            ],
            cwd=ROOT,
            text=True,
        )
    )
    compose = release_compose(compose, json.loads(args.images.read_text()))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    provenance = {
        "schemaVersion": 1,
        "coreCommit": subprocess.check_output(
            ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
        ).strip(),
        "fullCommit": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip(),
        "fullDirty": bool(
            subprocess.check_output(
                ["git", "-C", str(ROOT), "status", "--porcelain"], text=True
            ).strip()
        ),
        "publicationReady": False,
    }
    (output / "release.json").write_text(json.dumps(provenance, indent=2) + "\n")
    (output / "release.compose.json").write_text(json.dumps(compose, indent=2) + "\n")
    copy_assets(ROOT, core, output)
    checksums(output)
    print(
        f"Prepared {output}; images, signing, publication and physical acceptance are separate gates."
    )


if __name__ == "__main__":
    main()
