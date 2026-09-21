"""Create build contexts from exactly the locked source, never a dirty checkout."""

import json
import subprocess
import tarfile
import tempfile


def prepare_sources(root, names):
    lock = json.loads((root / "third_party/upstreams.lock.json").read_text())
    for entry in lock["repositories"]:
        if entry["name"] not in names:
            continue
        source = root / "third_party/sources" / entry["name"]
        actual = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != entry["commit"]:
            raise ValueError(f"Restore pinned {entry['name']} with make references")
        destination = root / ".local/build-sources" / entry["name"]
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
