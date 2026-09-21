#!/usr/bin/env python3
"""Prepare a source-free installation bundle from reviewed image digests. No publishing."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

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
    for filename in ("install.sh", "README.md", "LICENSE", "NOTICE"):
        shutil.copy2(ROOT / filename, output / filename)
    shutil.copytree(
        ROOT / "scripts",
        output / "scripts",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for filename in (
        "wrappers/mediamtx/mediamtx.yml",
        "wrappers/rebrowser/seccomp_profile.json",
    ):
        target = output / "assets" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(core / filename, target)
    subprocess.run(
        [
            "python3",
            str(core / "scripts/generate-probes.py"),
            "--output",
            str(output / "assets/probes"),
        ],
        check=True,
    )
    subprocess.run(
        [
            "python3",
            str(core / "scripts/generate-extended-probes.py"),
            "--output",
            str(output / "assets/probes"),
        ],
        check=True,
    )
    files = sorted(path for path in output.rglob("*") if path.is_file())
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output)}\n"
            for path in files
        )
    )
    print(
        f"Prepared {output}; images, signing, publication and physical acceptance are separate gates."
    )


if __name__ == "__main__":
    main()
