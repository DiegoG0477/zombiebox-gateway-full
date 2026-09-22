#!/usr/bin/env python3
"""Check published corresponding-source assets before pushing GHCR images."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def verify(repository, version, index_path, images_checksum):
    index = json.loads(index_path.read_text())
    if index.get("version") != version or not index.get("completeCorrespondingSources"):
        raise ValueError("Matching complete source index required")
    release = json.loads(
        subprocess.check_output(
            ["gh", "api", f"repos/{repository}/releases/tags/{version}"], text=True
        )
    )
    if release.get("draft") or release.get("tag_name") != version:
        raise ValueError("Sources must be publicly released before binary publication")
    assets = {asset["name"]: asset for asset in release["assets"]}
    expected = {item["name"]: item["sha256"] for item in index["parts"]}
    expected["sources-index.json"] = hashlib.sha256(index_path.read_bytes()).hexdigest()
    checksum = images_checksum.read_text().strip()
    match = re.fullmatch(r"([a-f0-9]{64})  images\.tar", checksum)
    if not match:
        raise ValueError("Invalid exact images.tar checksum")
    expected["images.tar"] = match.group(1)
    for name, digest in expected.items():
        asset = assets.get(name)
        if not asset or asset.get("state") != "uploaded":
            raise ValueError(f"Missing public release source/image asset: {name}")
        if asset.get("digest") != "sha256:" + digest:
            raise ValueError(f"Uploaded asset checksum mismatch: {name}")
        if asset["size"] > 2 * 1024**3:
            raise ValueError(f"Asset exceeds GitHub's per-file limit: {name}")
    print(f"Verified {len(expected)} public release assets for {version}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sources-index", type=Path, required=True)
    parser.add_argument("--images-checksum", type=Path, required=True)
    args = parser.parse_args()
    verify(args.repository, args.version, args.sources_index, args.images_checksum)


if __name__ == "__main__":
    main()
