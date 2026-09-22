#!/usr/bin/env python3
"""Audit staged corresponding sources and split them into bounded release assets."""

import argparse
import hashlib
import json
import re
import tarfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

collector = SourceFileLoader(
    "full_source_collector", str(Path(__file__).with_name("collect-full-sources.py"))
).load_module()
MAX_PART = 1_900_000_000


def require_file(path, expected=None):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing regular source file: {path}")
    digest = collector.sha256(path)
    if expected and digest != expected:
        raise ValueError(f"Source checksum mismatch: {path}")
    return digest


def validate(inventories, staging, distfiles):
    records = collector.inventories(inventories)
    repositories = json.loads((staging / "repositories.json").read_text())
    go = json.loads((staging / "go.json").read_text())
    npm = json.loads((staging / "npm.json").read_text())
    aports = json.loads((staging / "aports.json").read_text())
    expected_repos = {"gateway-full", "gateway-core", *collector.INTEGRATED_UPSTREAMS}
    if {
        name
        for name in expected_repos
        if any(
            item["name"] == name + "-" + item["commit"][:12] + ".tar"
            for item in repositories
        )
    } != expected_repos or len(repositories) != len(expected_repos):
        raise ValueError(
            "Missing first-party or integrated upstream repository archives"
        )
    for entry in repositories:
        require_file(staging / entry["name"], entry["sha256"])
    required_go = {
        (module["path"], module["version"], module["goSum"])
        for record in records.values()
        for binary in record["goBinaries"]
        for module in binary["dependencies"]
    }
    actual_go = {
        (item["module"], item["version"], item["goSum"]) for item in go["modules"]
    }
    if actual_go != required_go:
        raise ValueError("Go source set differs from linked modules")
    for item in go["modules"]:
        stem = re.sub(r"[^a-zA-Z0-9._-]", "_", item["module"] + "@" + item["version"])
        require_file(staging / (stem + ".zip"), item["zipSha256"])
        require_file(staging / (stem + ".mod"))
    versions = {
        binary["goVersion"]
        for record in records.values()
        for binary in record["goBinaries"]
    }
    if {item["version"] for item in go["stdlib"]} != versions:
        raise ValueError("Go standard library source versions differ from binaries")
    for item in go["stdlib"]:
        require_file(staging / item["file"], item["sha256"])
    required_npm = {
        (item["resolved"], item["integrity"])
        for record in records.values()
        for item in record["npmPackages"]
    }
    if {(item["url"], item["integrity"]) for item in npm} != required_npm:
        raise ValueError("npm source set differs from runtime lock inventory")
    for item in npm:
        require_file(staging / item["file"], item["sha256"])
    required_aports = {
        (item["origin"], item["aportsCommit"])
        for record in records.values()
        for item in record["requiredSources"]
    }
    if {(item["origin"], item["aportsCommit"]) for item in aports} != required_aports:
        raise ValueError("Alpine recipe set differs from installed package inventory")
    needed_distfiles = set()
    for item in aports:
        folder = staging / item["directory"]
        require_file(distfiles / "verified" / item["directory"])
        for source in item["files"]:
            require_file(folder / source["name"], source["sha256"])
        apkbuild = (folder / "APKBUILD").read_text()
        checks = re.findall(r"\b([a-f0-9]{128})  ([^\s\"]+)", apkbuild)
        if "sha512sums=" in apkbuild and not checks:
            raise ValueError(f"Unparsed Alpine source hashes: {item['directory']}")
        for expected, filename in checks:
            if filename in {".", ".."} or "/" in filename or "\\" in filename:
                raise ValueError(f"Unexpected Alpine source name: {filename}")
            local = folder / filename
            source = local if local.is_file() else distfiles / filename
            if not local.is_file():
                needed_distfiles.add(filename)
            require_file(source)
            with source.open("rb") as content:
                if hashlib.file_digest(content, "sha512").hexdigest() != expected:
                    raise ValueError(f"Alpine source checksum mismatch: {filename}")
    if list(distfiles.glob("*.part")):
        raise ValueError("Incomplete Alpine distfile download")
    return records, needed_distfiles


def source_files(inventories, staging, distfiles, needed_distfiles):
    for service in collector.SERVICES:
        yield f"inventory/{service}.json", inventories / (service + ".json")
    for path in sorted(staging.rglob("*")):
        if path.is_file():
            yield "staging/" + str(path.relative_to(staging)), path
    for name in sorted(needed_distfiles):
        yield "alpine-distfiles/" + name, distfiles / name


def package(inventories, staging, distfiles, output, version):
    records, needed_distfiles = validate(inventories, staging, distfiles)
    output.mkdir(parents=True, exist_ok=False)
    files = list(source_files(inventories, staging, distfiles, needed_distfiles))
    parts = []
    index = []
    current = None
    used = 0
    for name, path in files:
        size = path.stat().st_size
        if size > MAX_PART:
            raise ValueError(f"Single source exceeds release asset limit: {name}")
        if current is None or (used + size > MAX_PART and used):
            if current:
                current.close()
            filename = f"full-sources-{version}-part-{len(parts) + 1:03d}.tar"
            parts.append(filename)
            current = tarfile.open(output / filename, "w")
            used = 0
        current.add(path, arcname=name, recursive=False)
        index.append(
            dict(path=name, sha256=require_file(path), bytes=size, part=parts[-1])
        )
        used += size
    if current:
        current.close()
    manifest = dict(
        schemaVersion=1,
        version=version,
        imageIds={service: record["imageId"] for service, record in records.items()},
        repositoryArchives=json.loads((staging / "repositories.json").read_text()),
        files=index,
        parts=[dict(name=name, sha256=require_file(output / name)) for name in parts],
        completeCorrespondingSources=True,
        physicalValidation=False,
    )
    (output / "sources-index.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "SHA256SUMS").write_text(
        "".join(
            require_file(output / name) + "  " + name + "\n"
            for name in [*parts, "sources-index.json"]
        )
    )
    print(f"Source closure packaged as {len(parts)} release assets at {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventories", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--distfiles", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prefix = "v0.1.0-dev."
    if not args.version.startswith(prefix) or not args.version[len(prefix) :].isdigit():
        raise ValueError("Use an explicit dev checkpoint for this source inventory")
    package(args.inventories, args.staging, args.distfiles, args.output, args.version)


if __name__ == "__main__":
    main()
