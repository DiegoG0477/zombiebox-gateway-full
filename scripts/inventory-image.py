#!/usr/bin/env python3
"""Inventory an immutable Alpine runtime image without starting its entrypoint."""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


def alpine_packages(text):
    packages = []
    for block in text.split("\n\n"):
        fields = {}
        for line in block.splitlines():
            key, separator, value = line.partition(":")
            if key == "F":
                break  # File entries reuse header keys; they are not package metadata.
            if separator:
                fields[key] = value
        if not fields:
            continue
        if not all(fields.get(key) for key in ("P", "V", "o", "L")):
            raise ValueError("Incomplete installed Alpine package record")
        commit = fields.get("c", "")
        if not re.fullmatch(r"[a-f0-9]{40}", commit):
            raise ValueError("Alpine source recipe lacks an exact aports commit")
        packages.append(
            dict(
                name=fields["P"],
                version=fields["V"],
                origin=fields["o"],
                license=fields["L"],
                aportsCommit=commit,
            )
        )
    if not packages or len(packages) > 4096:
        raise ValueError("Invalid Alpine package count")
    if len({package["name"] for package in packages}) != len(packages):
        raise ValueError("Duplicate installed package")
    return sorted(packages, key=lambda package: package["name"])


def inspect_image(image, output):
    if not re.fullmatch(r"(?:[a-z0-9./:_-]+@)?sha256:[a-f0-9]{64}", image):
        raise ValueError("Use an immutable image ID or registry digest")
    inspected = json.loads(
        subprocess.check_output(["docker", "image", "inspect", image], text=True)
    )[0]
    with tempfile.TemporaryDirectory(prefix="zombie-image-inventory-") as temporary:
        root = Path(temporary)
        container = subprocess.check_output(
            [
                "docker",
                "create",
                "--network",
                "none",
                "--entrypoint",
                "/bin/true",
                image,
            ],
            text=True,
        ).strip()
        try:
            subprocess.run(
                [
                    "docker",
                    "cp",
                    container + ":/lib/apk/db/installed",
                    str(root / "installed"),
                ],
                check=True,
                capture_output=True,
            )
            packages = alpine_packages((root / "installed").read_text())
            npm = []
            copied = subprocess.run(
                [
                    "docker",
                    "cp",
                    container + ":/app/node_modules/.package-lock.json",
                    str(root / "npm.json"),
                ],
                capture_output=True,
            )
            if copied.returncode == 0:
                lock = json.loads((root / "npm.json").read_text())
                for name, package in sorted(lock.get("packages", {}).items()):
                    if name:
                        npm.append(
                            dict(
                                path=name,
                                version=package.get("version"),
                                resolved=package.get("resolved"),
                                integrity=package.get("integrity"),
                                license=package.get("license", "REVIEW_REQUIRED"),
                            )
                        )
        finally:
            subprocess.run(
                ["docker", "rm", container], check=True, stdout=subprocess.DEVNULL
            )
        origins = sorted({(p["origin"], p["aportsCommit"]) for p in packages})
        record = dict(
            schemaVersion=1,
            imageId=inspected["Id"],
            architecture=inspected["Architecture"],
            rootfsLayers=inspected["RootFS"]["Layers"],
            installedDatabaseSha256=hashlib.sha256(
                (root / "installed").read_bytes()
            ).hexdigest(),
            osPackages=packages,
            npmPackages=npm,
            requiredSources=[
                dict(origin=name, aportsCommit=commit, sourceCollected=False)
                for name, commit in origins
            ],
            coverage={
                "alpineInstalledDatabase": True,
                "npmRuntimeLockPresent": copied.returncode == 0,
                "goAndManuallyCopiedBinaries": False,
                "completeCorrespondingSources": False,
            },
            publicationReady=False,
        )
    with output.open("x") as destination:
        destination.write(json.dumps(record, indent=2) + "\n")
    print(
        f"Inventoried {len(packages)} OS packages / {len(origins)} source recipes / {len(npm)} npm packages; source collection remains required."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inspect_image(args.image, args.output)


if __name__ == "__main__":
    main()
