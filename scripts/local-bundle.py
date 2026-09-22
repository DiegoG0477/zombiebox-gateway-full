#!/usr/bin/env python3
"""Preserve every Full service image for private, compiler-free offline installation."""

import argparse
import json
import subprocess
from pathlib import Path

from lib.bundle_assets import checksums, copy_assets
from lib.image_snapshot import freeze, validate

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
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
    frozen, images = freeze(compose)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schemaVersion": 1,
        "distributionMode": "local-offline",
        "images": images,
        "archive": "images.tar",
        "configurationCoreCommit": subprocess.check_output(
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
        "physicalValidation": False,
    }
    # Saving by immutable IDs avoids racing a concurrently replaced development tag.
    subprocess.run(
        [
            "docker",
            "image",
            "save",
            "-o",
            str(output / "images.tar"),
            *sorted({v["imageId"] for v in images.values()}),
        ],
        check=True,
    )
    if validate(manifest):
        raise ValueError("An image disappeared during snapshot creation")
    (output / "images.lock.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "release.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "release.compose.json").write_text(json.dumps(frozen, indent=2) + "\n")
    copy_assets(ROOT, core, output)
    checksums(output)
    print(f"Prepared private offline bundle: {output}. Nothing deployed or published.")


if __name__ == "__main__":
    main()
