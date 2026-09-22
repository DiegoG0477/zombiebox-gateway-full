#!/usr/bin/env python3
"""Restore the private bundle's exact images without registry access or tag fallback."""

import json
import subprocess
from pathlib import Path

from lib.image_snapshot import validate

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "images.lock.json").read_text())
if (
    manifest.get("distributionMode") != "local-offline"
    or manifest.get("archive") != "images.tar"
):
    raise SystemExit("Unsupported image lock")
if validate(manifest):
    subprocess.run(
        ["docker", "image", "load", "-i", str(root / "images.tar")], check=True
    )
if validate(manifest):
    raise SystemExit("Image restore incomplete; services were not started")
print("All frozen images are available locally; no registry pull is required.")
