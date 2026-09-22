#!/usr/bin/env python3
"""Publish a source-closed Full image set under one new immutable release tag."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
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


def archive_config_ids(archive_path, image_ids):
    """Link inventoried OCI image digests to the config IDs exposed by docker load."""

    def blob(archive, digest):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
            raise ValueError(f"Invalid OCI digest: {digest}")
        path = "blobs/sha256/" + digest.removeprefix("sha256:")
        member = archive.extractfile(path)
        if member is None:
            raise ValueError(f"Missing OCI blob: {digest}")
        content = member.read()
        if hashlib.sha256(content).hexdigest() != digest.removeprefix("sha256:"):
            raise ValueError(f"Corrupt OCI blob: {digest}")
        return json.loads(content)

    expected = set(image_ids.values())
    if len(expected) != len(image_ids):
        raise ValueError("Each runtime image needs a distinct inventory identity")
    with tarfile.open(archive_path) as archive:
        root = json.load(archive.extractfile("index.json"))
        descriptors = {item["digest"]: item for item in root["manifests"]}
        if not expected <= descriptors.keys():
            raise ValueError("OCI archive does not contain all inventoried images")
        for digest in descriptors.keys() - expected:
            extra = blob(archive, digest)
            if not extra.get("artifactType") or not extra.get("subject"):
                raise ValueError(f"Unexpected runnable OCI image: {digest}")
        configs = {}
        for source, image_id in image_ids.items():
            item = blob(archive, image_id)
            if "manifests" in item:
                candidates = [
                    child
                    for child in item["manifests"]
                    if child.get("platform") == {"os": "linux", "architecture": "amd64"}
                ]
                if len(candidates) != 1:
                    raise ValueError(f"Expected one Linux/amd64 image: {source}")
                item = blob(archive, candidates[0]["digest"])
            config_id = item["config"]["digest"]
            config = blob(archive, config_id)
            if config.get("os") != "linux" or config.get("architecture") != "amd64":
                raise ValueError(f"Wrong image platform: {source}")
            configs[source] = config_id
        loaded_configs = {
            "sha256:" + Path(entry["Config"]).name
            for entry in json.load(archive.extractfile("manifest.json"))
        }
        if loaded_configs != set(configs.values()):
            raise ValueError("Docker load manifest differs from OCI image set")
        return configs


def publish(index, version, namespace, archive_path=None, receipt_path=None):
    if index.get("version") != version or not index.get("completeCorrespondingSources"):
        raise ValueError("Matching complete corresponding sources are required")
    ids = index["imageIds"]
    if set(ids) != set(SERVICES.values()):
        raise ValueError("Source closure does not cover every Full runtime image")
    if archive_path is None:
        raise ValueError("The exact released OCI archive is required")
    config_ids = archive_config_ids(archive_path, ids)
    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    if not token:
        raise ValueError("GitHub authentication is required")
    username = os.environ.get("GITHUB_ACTOR", "DiegoG0477")
    login = subprocess.run(
        ["docker", "login", "ghcr.io", "-u", username, "--password-stdin"],
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
        config_id = config_ids[source]
        inspected = json.loads(
            subprocess.check_output(
                ["docker", "image", "inspect", config_id], text=True
            )
        )[0]
        if inspected["Id"] != config_id or inspected["Architecture"] != "amd64":
            raise ValueError(f"Image identity/platform mismatch: {service}")
        tag = f"{namespace}/{service}:{version}"
        previous = receipt.get(service)
        if previous:
            if (
                previous["imageId"] != image_id
                or previous["archiveConfigId"] != config_id
                or previous["tag"] != tag
            ):
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
        subprocess.run(["docker", "tag", config_id, tag], check=True)
        pushed = subprocess.run(
            ["docker", "push", tag], capture_output=True, text=True, check=True
        )
        matches = re.findall(r"digest: (sha256:[a-f0-9]{64})", pushed.stdout)
        if len(matches) != 1:
            raise ValueError(f"Cannot prove pushed manifest digest: {service}")
        digest_ref = f"{namespace}/{service}@{matches[0]}"
        receipt[service] = dict(
            imageId=image_id,
            archiveConfigId=config_id,
            tag=tag,
            digestRef=digest_ref,
        )
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
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--namespace", default="ghcr.io/zombiebox-tv")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    release_version(args.version)
    if not re.fullmatch(r"ghcr\.io/[a-z0-9][a-z0-9-]+", args.namespace):
        raise ValueError("Use an explicit lower-case GHCR namespace")
    index = json.loads(args.sources_index.read_text())
    result = publish(index, args.version, args.namespace, args.archive, args.output)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
