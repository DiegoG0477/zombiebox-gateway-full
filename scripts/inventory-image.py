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


def go_build_info(text):
    """Parse embedded build metadata; the inspected executable is never run."""
    lines = text.splitlines()
    if not lines or not re.search(r": go[0-9]+\.[0-9]+", lines[0]):
        raise ValueError("Missing Go build metadata")
    result = {
        "goVersion": lines[0].rsplit(": ", 1)[-1],
        "dependencies": [],
        "build": {},
    }
    allowed = {
        "GOOS",
        "GOARCH",
        "GOARM",
        "CGO_ENABLED",
        "vcs.revision",
        "vcs.modified",
        "-buildmode",
        "-compiler",
    }
    for line in lines[1:]:
        fields = line.strip().split("\t")
        if fields[0] == "path" and len(fields) == 2:
            result["package"] = fields[1]
        elif fields[0] in {"mod", "dep"} and len(fields) in {3, 4}:
            module = {
                "path": fields[1],
                "version": fields[2],
                "goSum": fields[3] if len(fields) == 4 else "",
                "sourceCollected": False,
            }
            if fields[0] == "mod":
                result["mainModule"] = module
            else:
                result["dependencies"].append(module)
        elif fields[0] == "=>":
            # A replacement changes corresponding-source identity. Do not silently
            # attest the original module or follow an arbitrary local build path.
            raise ValueError("Go module replacement requires an explicit source review")
        elif fields[0] == "build" and len(fields) == 2:
            key, separator, value = fields[1].partition("=")
            if separator and key in allowed:
                result["build"][key] = value
    if (
        "package" not in result
        or "mainModule" not in result
        or len(result["dependencies"]) > 4096
    ):
        raise ValueError("Incomplete Go build inventory")
    return result


def inventory_go_binary(container, binary, root):
    if not re.fullmatch(r"/(?:usr/local/bin/)?[a-zA-Z0-9_-]+", binary):
        raise ValueError("Select a root or /usr/local/bin executable path")
    target = root / "go-binary"
    subprocess.run(
        ["docker", "cp", container + ":" + binary, str(target)],
        check=True,
        capture_output=True,
    )
    if (
        target.is_symlink()
        or not target.is_file()
        or target.stat().st_size > 512 * 1024 * 1024
    ):
        raise ValueError("Expected a bounded regular Go executable")
    metadata = subprocess.check_output(
        ["go", "version", "-m", str(target)], text=True, timeout=10
    )
    result = go_build_info(metadata)
    with target.open("rb") as source:
        result["sha256"] = hashlib.file_digest(source, "sha256").hexdigest()
    result["imagePath"] = binary
    result["bytes"] = target.stat().st_size
    target.unlink()
    return result


def inspect_image(image, output, go_binaries=()):
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
            binaries = [
                inventory_go_binary(container, binary, root)
                for binary in dict.fromkeys(go_binaries)
            ]
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
            goBinaries=binaries,
            requiredSources=[
                dict(origin=name, aportsCommit=commit, sourceCollected=False)
                for name, commit in origins
            ],
            coverage={
                "alpineInstalledDatabase": True,
                "npmRuntimeLockPresent": copied.returncode == 0,
                "goAndManuallyCopiedBinaries": False,
                "selectedGoBinariesInspected": len(binaries),
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
    parser.add_argument(
        "--go-binary",
        action="append",
        default=[],
        help="explicit root or /usr/local/bin Go executable to inventory without running it",
    )
    args = parser.parse_args()
    inspect_image(args.image, args.output, args.go_binary)


if __name__ == "__main__":
    main()
