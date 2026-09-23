"""Create build contexts from exactly the locked source, never a dirty checkout."""

import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


def prepare_sources(root, names):
    core = Path(os.environ["ZOMBIE_CORE_DIR"])
    lock = json.loads((core / "third_party/upstreams.lock.json").read_text())
    for entry in lock["repositories"]:
        if entry["name"] not in names:
            continue
        source = core / "third_party/sources" / entry["name"]
        actual = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != entry["commit"]:
            raise ValueError(f"Restore pinned {entry['name']} with make references")
        destination = root / ".local/build-sources" / entry["name"]
        if entry["name"] == "go-librespot":
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
                staged = Path(temporary) / "go-librespot"
                subprocess.run(
                    [
                        "python3",
                        str(core / "scripts/prepare-spotify-source.py"),
                        "--source",
                        str(source),
                        "--output",
                        str(staged),
                    ],
                    check=True,
                )
                if destination.exists():
                    shutil.rmtree(destination)
                staged.replace(destination)
            continue
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile() as archive:
            subprocess.run(
                ["git", "-C", str(source), "archive", actual],
                stdout=archive,
                check=True,
            )
            archive.seek(0)
            with tarfile.open(fileobj=archive) as content:
                content.extractall(destination, filter="data")
        (destination / "ZOMBIE_UPSTREAM_COMMIT").write_text(actual + "\n")
