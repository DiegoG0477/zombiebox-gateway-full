#!/usr/bin/env python3
"""Publish a source-closed Full image set under one new immutable release tag."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from lib.release_set import release_version

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


def publish(index, version, namespace, receipt_path=None):
    if index.get("version") != version or not index.get("completeCorrespondingSources"):
        raise ValueError("Matching complete corresponding sources are required")
    ids = index["imageIds"]
    if set(ids) != set(SERVICES.values()):
        raise ValueError("Source closure does not cover every Full runtime image")
    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    if not token:
        raise ValueError("GitHub authentication is required")
    login = subprocess.run(
        ["docker", "login", "ghcr.io", "-u", "DiegoG0477", "--password-stdin"],
        input=token,
        text=True,
        capture_output=True,
    )
    if login.returncode:
        raise ValueError("GHCR authentication failed; check write:packages access")
    receipt = (
        json.loads(receipt_path.read_text())
        if receipt_path and receipt_path.exists()
        else {}
    )
    for service in SERVICES:
        if service in receipt:
            continue
        tag = f"{namespace}/{service}:{version}"
        if (
            subprocess.run(
                ["docker", "manifest", "inspect", tag], capture_output=True, text=True
            ).returncode
            == 0
        ):
            raise ValueError(f"Refusing to move existing image tag: {tag}")
    for service, source in SERVICES.items():
        image_id = ids[source]
        inspected = json.loads(
            subprocess.check_output(["docker", "image", "inspect", image_id], text=True)
        )[0]
        if inspected["Id"] != image_id or inspected["Architecture"] != "amd64":
            raise ValueError(f"Image identity/platform mismatch: {service}")
        tag = f"{namespace}/{service}:{version}"
        previous = receipt.get(service)
        if previous:
            if previous["imageId"] != image_id or previous["tag"] != tag:
                raise ValueError(f"Existing push receipt differs: {service}")
            remote = subprocess.check_output(
                [
                    "docker",
                    "buildx",
                    "imagetools",
                    "inspect",
                    "--format",
                    "{{.Digest}}",
                    tag,
                ],
                text=True,
            ).strip()
            if previous["digestRef"] != f"{namespace}/{service}@{remote}":
                raise ValueError(
                    f"Published digest differs from saved receipt: {service}"
                )
            continue
        subprocess.run(["docker", "tag", image_id, tag], check=True)
        pushed = subprocess.run(
            ["docker", "push", tag], capture_output=True, text=True, check=True
        )
        matches = re.findall(r"digest: (sha256:[a-f0-9]{64})", pushed.stdout)
        if len(matches) != 1:
            raise ValueError(f"Cannot prove pushed manifest digest: {service}")
        digest_ref = f"{namespace}/{service}@{matches[0]}"
        receipt[service] = dict(imageId=image_id, tag=tag, digestRef=digest_ref)
        if receipt_path:
            receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"Published {service}: {digest_ref}")
    receipt["discovery"] = receipt["gateway"].copy()
    if receipt_path:
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources-index", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--namespace", default="ghcr.io/zombiebox-tv")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    release_version(args.version)
    if not re.fullmatch(r"ghcr\.io/[a-z0-9][a-z0-9-]+", args.namespace):
        raise ValueError("Use an explicit lower-case GHCR namespace")
    index = json.loads(args.sources_index.read_text())
    result = publish(index, args.version, args.namespace, args.output)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
