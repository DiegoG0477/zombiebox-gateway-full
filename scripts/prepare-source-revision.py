#!/usr/bin/env python3
"""Close a release that reuses frozen images and replaces one service image.

The base source parts remain at their immutable public release URL. This release
ships the complete source delta and pins both source sets by SHA256.
"""

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

from lib.release_set import release_version

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT.parent / "gateway-core"
SERVICES = {
    "gateway": "gateway-dev43",
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


def clean_commit(path):
    if subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"]):
        raise ValueError(f"Source checkout is dirty: {path}")
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def archive_checkout(path, destination, prefix):
    with destination.open("wb") as output:
        subprocess.run(
            ["git", "-C", str(path), "archive", "--prefix=" + prefix + "/", "HEAD"],
            stdout=output,
            check=True,
        )


def prepare(version, base_index, base_receipt, spotify_inventory, output):
    release_version(version)
    if base_index["version"] != "v0.1.0-dev.46":
        raise ValueError("Only the audited dev.46 source base is supported")
    if not base_index["completeCorrespondingSources"]:
        raise ValueError("Base image sources are incomplete")
    if set(base_receipt) != {*SERVICES, "discovery"}:
        raise ValueError("Base push receipt is incomplete")
    for service, inventory in SERVICES.items():
        if base_receipt[service]["imageId"] != base_index["imageIds"][inventory]:
            raise ValueError(f"Base image/source identity differs: {service}")
    if (
        clean_commit(CORE)
        != json.loads((ROOT / "dependencies.lock.json").read_text())["dependencies"][
            "gateway-core"
        ]["commit"]
    ):
        raise ValueError("Core checkout differs from Full dependency lock")
    full_commit = clean_commit(ROOT)
    core_commit = clean_commit(CORE)
    new = json.loads(spotify_inventory.read_text())
    if new["imageId"] == base_index["imageIds"]["spotify"]:
        raise ValueError("Spotify image did not change")
    if new["architecture"] != "amd64" or len(new["goBinaries"]) != 2:
        raise ValueError("Unexpected Spotify image inventory")
    if any(
        dependency["path"] == "github.com/xlab/vorbis-go"
        for binary in new["goBinaries"]
        for dependency in binary["dependencies"]
    ):
        raise ValueError("Unlicensed Vorbis binding is still linked")
    binary = next(
        item for item in new["goBinaries"] if item["imagePath"].endswith("go-librespot")
    )
    modules = {
        (item["path"], item["version"]): item["goSum"]
        for item in binary["dependencies"]
    }
    if not {"github.com/jfreymuth/oggvorbis", "github.com/jfreymuth/vorbis"} <= {
        key[0] for key in modules
    }:
        raise ValueError("Licensed decoder modules are missing")
    base_paths = {item["path"] for item in base_index["files"]}
    for item in new["requiredSources"]:
        path = f"staging/{item['origin']}-{item['aportsCommit'][:12]}/APKBUILD"
        if path not in base_paths:
            raise ValueError(
                f"New Alpine source recipe needs separate collection: {path}"
            )
    for binary in new["goBinaries"]:
        if f"staging/go-stdlib-{binary['goVersion']}.tar.gz" not in base_paths:
            raise ValueError("Go standard library source is missing from base")
    staged = ROOT / ".local/build-sources/go-librespot"
    if (staged / "ZOMBIE_PATCH").read_text().strip() != "licensed-vorbis.patch":
        raise ValueError("Spotify staged source has the wrong patch")
    if "github.com/xlab/vorbis-go" in (staged / "go.mod").read_text():
        raise ValueError("Spotify staged source contains the old binding")
    output.mkdir(parents=True, exist_ok=False)
    files = []
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        for name, checkout in (("gateway-full", ROOT), ("gateway-core", CORE)):
            path = temporary / (name + ".tar")
            archive_checkout(checkout, path, name)
            files.append(("source/" + path.name, path))
        files.append(("inventory/spotify.json", spotify_inventory))
        for path in sorted(staged.rglob("*")):
            if path.is_file():
                files.append(
                    ("source/go-librespot/" + str(path.relative_to(staged)), path)
                )
        for (module, module_version), checksum in sorted(modules.items()):
            metadata = json.loads(
                subprocess.check_output(
                    ["go", "mod", "download", "-json", module + "@" + module_version],
                    text=True,
                )
            )
            if metadata.get("Error") or metadata.get("Sum") != checksum:
                raise ValueError(
                    f"Go module checksum differs: {module}@{module_version}"
                )
            stem = re.sub(r"[^a-zA-Z0-9._-]", "_", module + "@" + module_version)
            files.extend(
                (
                    ("go/" + stem + ".zip", Path(metadata["Zip"])),
                    ("go/" + stem + ".mod", Path(metadata["GoMod"])),
                )
            )
        part = output / f"full-sources-{version}-spotify-revision.tar"
        entries = []
        with tarfile.open(part, "w") as archive:
            for name, path in files:
                if path.is_symlink() or not path.is_file():
                    raise ValueError(f"Missing regular source file: {name}")
                archive.add(path, arcname=name, recursive=False)
                entries.append(
                    dict(path=name, sha256=digest(path), bytes=path.stat().st_size)
                )
    base_version = base_index["version"]
    base_url = (
        "https://github.com/ZombieBox-tv/zombiebox-gateway-full/releases/download/"
        + base_version
        + "/"
    )
    parts = [dict(**item, url=base_url + item["name"]) for item in base_index["parts"]]
    parts.append(dict(name=part.name, sha256=digest(part), url=part.name))
    image_ids = dict(base_index["imageIds"])
    image_ids["spotify"] = new["imageId"]
    index = dict(
        schemaVersion=2,
        version=version,
        completeCorrespondingSources=True,
        physicalValidation=False,
        baseSourceIndexSha256=hashlib.sha256(
            (json.dumps(base_index, indent=2) + "\n").encode()
        ).hexdigest(),
        baseSourceIndexUrl=base_url + "sources-index.json",
        baseImageReceipt={
            name: item["digestRef"] for name, item in base_receipt.items()
        },
        fullCommit=full_commit,
        coreCommit=core_commit,
        imageIds=image_ids,
        files=entries,
        parts=parts,
    )
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
    print(
        f"Closed Spotify revision sources at {output}; inherited {len(parts) - 1} immutable source parts"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--base-index", type=Path, required=True)
    parser.add_argument("--base-receipt", type=Path, required=True)
    parser.add_argument("--spotify-inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(
        args.version,
        json.loads(args.base_index.read_text()),
        json.loads(args.base_receipt.read_text()),
        args.spotify_inventory,
        args.output,
    )


if __name__ == "__main__":
    main()
