#!/usr/bin/env python3
"""Close sources for a new gateway image that reuses frozen Full service images."""

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT.parent / "gateway-core"
SOURCE_BASE = "v0.1.0-dev.52"
SERVICE_SLOTS = {
    "gateway": "gateway-dev43",
    "discovery": "gateway-dev43",
    "initialize": "bootstrap",
    "youtube": "youtube",
    "youtube-receiver": "youtube-receiver",
    "spotify": "spotify",
    "airplay": "airplay",
    "threadfin": "threadfin",
    "rebrowser": "rebrowser",
    "mediamtx": "mediamtx",
}


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def clean_commit(checkout):
    if subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain"]):
        raise ValueError(f"Commit the source checkout before packaging: {checkout}")
    return subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()


def require_base_sources(underlying, inventory):
    paths = {entry["path"]: entry["sha256"] for entry in underlying["files"]}
    for source in inventory["requiredSources"]:
        path = f"staging/{source['origin']}-{source['aportsCommit'][:12]}/APKBUILD"
        if path not in paths:
            raise ValueError(f"New Alpine recipe needs a new source archive: {path}")
    for binary in inventory["goBinaries"]:
        standard = f"staging/go-stdlib-{binary['goVersion']}.tar.gz"
        if standard not in paths:
            raise ValueError(f"New Go toolchain source required: {standard}")
        for module in binary["dependencies"]:
            metadata = json.loads(
                subprocess.check_output(
                    [
                        "go",
                        "mod",
                        "download",
                        "-json",
                        module["path"] + "@" + module["version"],
                    ],
                    cwd=CORE / "gateway",
                    text=True,
                )
            )
            if metadata.get("Error") or metadata.get("Sum") != module["goSum"]:
                raise ValueError(f"Go module identity differs: {module['path']}")
            stem = re.sub(
                r"[^a-zA-Z0-9._-]", "_", module["path"] + "@" + module["version"]
            )
            for suffix, key in (("zip", "Zip"), ("mod", "GoMod")):
                path = "staging/" + stem + "." + suffix
                if paths.get(path) != digest(Path(metadata[key])):
                    raise ValueError(f"Frozen Go source differs: {path}")


def prepare(version, base, underlying, receipt, inventory_path, output):
    if not re.fullmatch(r"v0\.1\.0-dev\.[0-9]+", version):
        raise ValueError("Use a new explicit development checkpoint")
    if (
        base.get("version") != SOURCE_BASE
        or underlying.get("version") != "v0.1.0-dev.46"
        or not base.get("completeCorrespondingSources")
        or not underlying.get("completeCorrespondingSources")
    ):
        raise ValueError("Expected the complete reviewed dev.46 → dev.52 source chain")
    if set(receipt) != set(SERVICE_SLOTS):
        raise ValueError("Base receipt does not cover every runtime service")
    for service, slot in SERVICE_SLOTS.items():
        if receipt[service]["imageId"] != base["imageIds"][slot]:
            raise ValueError(f"Base image/source identity differs: {service}")
    core_commit = clean_commit(CORE)
    full_commit = clean_commit(ROOT)
    locked = json.loads((ROOT / "dependencies.lock.json").read_text())
    if locked["dependencies"]["gateway-core"]["commit"] != core_commit:
        raise ValueError("Full dependency lock differs from the Core checkout")
    inventory = json.loads(inventory_path.read_text())
    if (
        inventory.get("architecture") != "amd64"
        or len(inventory.get("goBinaries", [])) != 1
        or inventory["goBinaries"][0].get("imagePath") != "/zombied"
        or inventory.get("npmPackages")
    ):
        raise ValueError("Expected exactly one inventoried Go gateway executable")
    image = json.loads(
        subprocess.check_output(
            ["docker", "image", "inspect", inventory["imageId"]], text=True
        )
    )[0]
    if (
        image["Id"] != inventory["imageId"]
        or image["Architecture"] != inventory["architecture"]
        or image["RootFS"]["Layers"] != inventory["rootfsLayers"]
    ):
        raise ValueError("Gateway inventory differs from the selected local image")
    require_base_sources(underlying, inventory)
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="zombie-gateway-sources-") as temporary:
        staging = Path(temporary)
        files = [("inventory/gateway.json", inventory_path)]
        for name, checkout in (("gateway-full", ROOT), ("gateway-core", CORE)):
            path = staging / (name + ".tar")
            with path.open("wb") as archive:
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(checkout),
                        "archive",
                        "--prefix=" + name + "/",
                        "HEAD",
                    ],
                    stdout=archive,
                    check=True,
                )
            files.append(("source/" + path.name, path))
        part = output / f"full-sources-{version}-gateway-revision.tar"
        entries = []
        with tarfile.open(part, "w") as archive:
            for name, path in files:
                archive.add(path, arcname=name, recursive=False)
                entries.append(
                    {"path": name, "sha256": digest(path), "bytes": path.stat().st_size}
                )
    base_url = (
        "https://github.com/ZombieBox-tv/zombiebox-gateway-full/releases/download/"
        + SOURCE_BASE
        + "/"
    )
    parts = [dict(entry) for entry in base["parts"]]
    parts.append({"name": part.name, "sha256": digest(part), "url": part.name})
    image_ids = dict(base["imageIds"])
    # gateway-dev43 is the legacy publisher's service slot, not this image's version.
    image_ids["gateway-dev43"] = inventory["imageId"]
    index = {
        "schemaVersion": 3,
        "version": version,
        "completeCorrespondingSources": True,
        "physicalValidation": False,
        "baseSourceIndexSha256": base["sourceIndexSha256"],
        "baseSourceIndexUrl": base_url + "sources-index.json",
        "baseImageReceipt": {
            name: value["digestRef"] for name, value in receipt.items()
        },
        "fullCommit": full_commit,
        "coreCommit": core_commit,
        "imageIds": image_ids,
        "files": entries,
        "parts": parts,
    }
    index_path = output / "sources-index.json"
    index_path.write_text(json.dumps(index, indent=2) + "\n")
    (output / "sources-SHA256SUMS").write_text(
        digest(part)
        + "  "
        + part.name
        + "\n"
        + digest(index_path)
        + "  sources-index.json\n"
    )
    print(f"Closed gateway image sources at {output}; public upload remains separate")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--base-index", type=Path, required=True)
    parser.add_argument("--underlying-index", type=Path, required=True)
    parser.add_argument("--base-receipt", type=Path, required=True)
    parser.add_argument("--gateway-inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base_bytes = args.base_index.read_bytes()
    underlying_bytes = args.underlying_index.read_bytes()
    base = json.loads(base_bytes)
    underlying = json.loads(underlying_bytes)
    if hashlib.sha256(underlying_bytes).hexdigest() != base["baseSourceIndexSha256"]:
        raise ValueError("The inherited source index checksum differs")
    base["sourceIndexSha256"] = hashlib.sha256(base_bytes).hexdigest()
    prepare(
        args.version,
        base,
        underlying,
        json.loads(args.base_receipt.read_text()),
        args.gateway_inventory,
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
