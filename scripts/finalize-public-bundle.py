#!/usr/bin/env python3
"""Gate a Docker-only release on source closure and anonymous GHCR access."""

import argparse
import json
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from lib.bundle_assets import checksums
from lib.release_set import release_version

ROOT = Path(__file__).resolve().parents[1]
SERVICES = {
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


def public_digest(reference):
    prefix = "ghcr.io/"
    if not reference.startswith(prefix) or "@sha256:" not in reference:
        raise ValueError(f"Expected pinned GHCR digest: {reference}")
    name, digest = reference[len(prefix) :].split("@", 1)
    if not name.startswith("zombiebox-tv/"):
        raise ValueError(f"Wrong registry owner: {name}")
    scope = urllib.parse.quote("repository:" + name + ":pull")
    token_url = "https://ghcr.io/token?service=ghcr.io&scope=" + scope
    with urllib.request.urlopen(token_url, timeout=15) as response:
        token = json.load(response)["token"]
    request = urllib.request.Request(
        "https://ghcr.io/v2/" + name + "/manifests/" + digest,
        method="HEAD",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": ", ".join(
                (
                    "application/vnd.oci.image.manifest.v1+json",
                    "application/vnd.docker.distribution.manifest.v2+json",
                    "application/vnd.oci.image.index.v1+json",
                    "application/vnd.docker.distribution.manifest.list.v2+json",
                )
            ),
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if (
            response.status != 200
            or response.headers.get("Docker-Content-Digest") != digest
        ):
            raise ValueError(f"Anonymous GHCR digest check failed: {reference}")


def finalize(version, index, receipt, output):
    if index.get("version") != version or not index.get("completeCorrespondingSources"):
        raise ValueError("Complete sources for this release are required")
    if set(receipt) != set(SERVICES):
        raise ValueError("Every Compose service needs a push receipt")
    images = {}
    for service, inventory in SERVICES.items():
        item = receipt[service]
        if item["imageId"] != index["imageIds"][inventory]:
            raise ValueError(
                f"Source inventory differs from published image: {service}"
            )
        images[service] = item["digestRef"]
    for reference in sorted(set(images.values())):
        public_digest(reference)
    with tempfile.TemporaryDirectory() as temporary:
        mapping = Path(temporary) / "images.json"
        mapping.write_text(json.dumps(images))
        subprocess.run(
            [
                "python3",
                str(ROOT / "scripts/compose-bundle.py"),
                "--version",
                version,
                "--bootstrap-image",
                images["initialize"],
                "--images",
                str(mapping),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            check=True,
        )
    manifest_path = output / "release.lock.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["publicationReady"] = True
    manifest["sourceIndexSha256"] = (
        __import__("hashlib")
        .sha256(json.dumps(index, indent=2).encode() + b"\n")
        .hexdigest()
    )
    manifest["sourceAssets"] = index["parts"]
    manifest["registryAnonymousPullVerified"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    readme = output / "README.md"
    readme.write_text(
        readme.read_text().replace(
            "Local evaluation only until corresponding-source and publication gates are met. ",
            "Sources accompany this release; images were anonymously reachable at packaging time. ",
        )
    )
    checksums(output)
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(output / "compose.yaml"),
            "--profile",
            "*",
            "config",
            "--quiet",
        ],
        check=True,
    )
    print(f"Public pull bundle prepared at {output}; upload assets before advertising")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sources-index", type=Path, required=True)
    parser.add_argument("--push-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    release_version(args.version)
    finalize(
        args.version,
        json.loads(args.sources_index.read_text()),
        json.loads(args.push_receipt.read_text()),
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
