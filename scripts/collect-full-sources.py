#!/usr/bin/env python3
"""Stage exact Full runtime sources; fail closed on unresolved dependencies."""

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    "bootstrap",
    "gateway-dev43",
    "mediamtx",
    "youtube",
    "youtube-receiver",
    "spotify",
    "airplay",
    "threadfin",
    "rebrowser",
)
INTEGRATED_UPSTREAMS = (
    "go-librespot",
    "uxplay",
    "threadfin",
    "yt-cast-receiver",
    "mediamtx",
)
MAX_DOWNLOAD = 128 * 1024 * 1024
GO_SOURCE_SHA256 = {
    "go1.26.8": "4e39b98e42f946fa05ac8bc5b71877df97dbdb7cbb1a777b541667ad7117fd2e",
}


def sha256(path):
    with path.open("rb") as content:
        return hashlib.file_digest(content, "sha256").hexdigest()


def download(url, destination, *, token=None, limit=MAX_DOWNLOAD):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "api.github.com",
        "raw.githubusercontent.com",
        "registry.npmjs.org",
        "go.dev",
    }:
        raise ValueError(f"Unexpected source host: {parsed.hostname}")
    request = urllib.request.Request(
        url, headers={"User-Agent": "ZombieBox-source-collector/1"}
    )
    if token and parsed.hostname == "api.github.com":
        request.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(request, timeout=30) as response:
        size = response.headers.get("Content-Length")
        if size and int(size) > limit:
            raise ValueError(f"Source exceeds {limit} bytes: {url}")
        with destination.open("wb") as output:
            copied = 0
            while chunk := response.read(1024 * 1024):
                copied += len(chunk)
                if copied > limit:
                    raise ValueError(f"Source exceeds {limit} bytes: {url}")
                output.write(chunk)
    return destination


def inventories(directory):
    records = {}
    for service in SERVICES:
        record = json.loads((directory / (service + ".json")).read_text())
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", record["imageId"]):
            raise ValueError(f"Invalid inventory identity: {service}")
        records[service] = record
    return records


def archive_repo(checkout, output, name, expected=None):
    actual = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    if expected and actual != expected:
        raise ValueError(f"{name} checkout is not at locked commit")
    if subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain"]):
        raise ValueError(f"{name} source checkout is dirty")
    target = output / (name + "-" + actual[:12] + ".tar")
    if not target.exists():
        with target.open("wb") as stream:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "archive",
                    "--prefix=" + name + "/",
                    actual,
                ],
                stdout=stream,
                check=True,
            )
    return dict(name=target.name, commit=actual, sha256=sha256(target))


def collect_repositories(core, output):
    lock = json.loads((core / "third_party/upstreams.lock.json").read_text())
    indexed = {entry["name"]: entry for entry in lock["repositories"]}
    selected = [
        archive_repo(ROOT, output, "gateway-full"),
        archive_repo(core, output, "gateway-core"),
    ]
    for name in INTEGRATED_UPSTREAMS:
        entry = indexed[name]
        selected.append(
            archive_repo(
                core / "third_party/sources" / name,
                output,
                name,
                entry["commit"],
            )
        )
    return selected


def collect_go(records, core, output):
    modules = {}
    versions = set()
    for record in records.values():
        for binary in record["goBinaries"]:
            versions.add(binary["goVersion"])
            for module in binary["dependencies"]:
                key = (module["path"], module["version"])
                if not module["goSum"].startswith("h1:"):
                    raise ValueError(f"Missing Go checksum: {key}")
                if key in modules and modules[key] != module["goSum"]:
                    raise ValueError(f"Conflicting Go checksum: {key}")
                modules[key] = module["goSum"]
    result = []
    for (name, version), expected in sorted(modules.items()):
        metadata = json.loads(
            subprocess.check_output(
                ["go", "mod", "download", "-json", name + "@" + version],
                cwd=core / "gateway",
                text=True,
            )
        )
        if metadata.get("Error") or metadata.get("Sum") != expected:
            raise ValueError(f"Go source mismatch: {name}@{version}")
        stem = re.sub(r"[^a-zA-Z0-9._-]", "_", name + "@" + version)
        for extension, key in (("zip", "Zip"), ("mod", "GoMod")):
            target = output / (stem + "." + extension)
            shutil.copy2(metadata[key], target)
        result.append(
            dict(
                module=name,
                version=version,
                goSum=expected,
                zipSha256=sha256(output / (stem + ".zip")),
            )
        )
    goroot = Path(subprocess.check_output(["go", "env", "GOROOT"], text=True).strip())
    version = (goroot / "VERSION").read_text().splitlines()[0]
    target = output / ("go-stdlib-" + version + ".tar.gz")
    if not target.exists():
        import tarfile

        with tarfile.open(target, "w:gz") as archive:
            for name in ("src", "LICENSE", "PATENTS", "VERSION"):
                archive.add(goroot / name, arcname="go/" + name)
    standard_libraries = [
        dict(version=version, file=target.name, sha256=sha256(target))
    ]
    for other in sorted(versions - {version}):
        expected = GO_SOURCE_SHA256.get(other)
        if not expected:
            raise ValueError(f"Review and pin Go source checksum for {other}")
        name = other + ".src.tar.gz"
        destination = output / name
        if not destination.exists():
            download("https://go.dev/dl/" + name, destination, limit=64 * 1024 * 1024)
        if sha256(destination) != expected:
            raise ValueError(f"Go source checksum mismatch: {other}")
        standard_libraries.append(dict(version=other, file=name, sha256=expected))
    return dict(modules=result, stdlib=standard_libraries)


def collect_npm(records, output):
    packages = {}
    for record in records.values():
        for package in record["npmPackages"]:
            key = package["resolved"]
            if key in packages and packages[key]["integrity"] != package["integrity"]:
                raise ValueError(f"Conflicting npm integrity: {key}")
            packages[key] = package
    result = []
    for index, (url, package) in enumerate(sorted(packages.items())):
        algorithm, encoded = package["integrity"].split("-", 1)
        if algorithm not in {"sha512", "sha256"}:
            raise ValueError(f"Unsupported npm integrity: {algorithm}")
        target = output / (
            f"npm-{index:03d}-" + hashlib.sha256(url.encode()).hexdigest()[:12] + ".tgz"
        )
        if not target.exists():
            download(url, target)
        digest = hashlib.new(algorithm, target.read_bytes()).digest()
        if digest != base64.b64decode(encoded, validate=True):
            raise ValueError(f"npm package integrity mismatch: {url}")
        result.append(
            dict(
                url=url,
                integrity=package["integrity"],
                file=target.name,
                sha256=sha256(target),
            )
        )
    return result


def api_json(url, token):
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "response.json"
        try:
            download(url, path, token=token, limit=2 * 1024 * 1024)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise
        return json.loads(path.read_text())


def fetch_aports_directory(origin, commit, output, token):
    for section in ("main", "community", "testing"):
        path = f"{section}/{origin}"
        url = (
            "https://api.github.com/repos/alpinelinux/aports/contents/"
            + path
            + "?ref="
            + commit
        )
        entries = api_json(url, token)
        if entries is None:
            continue
        if not isinstance(entries, list) or len(entries) > 256:
            raise ValueError(f"Unexpected aports directory: {path}@{commit}")
        target = output / (origin + "-" + commit[:12])
        target.mkdir(parents=True, exist_ok=True)
        files = []
        for entry in entries:
            if (
                entry["type"] != "file"
                or not re.fullmatch(r"[^\x00-\x1f/\\]+", entry["name"])
                or entry["name"] in {".", ".."}
            ):
                raise ValueError(
                    f"Review non-file aports entry: {path}/{entry['name']}"
                )
            destination = target / entry["name"]
            if not destination.exists():
                download(entry["download_url"], destination, limit=16 * 1024 * 1024)
            files.append(dict(name=entry["name"], sha256=sha256(destination)))
        if "APKBUILD" not in {item["name"] for item in files}:
            raise ValueError(f"Missing APKBUILD: {path}@{commit}")
        return dict(
            origin=origin,
            aportsCommit=commit,
            section=section,
            directory=target.name,
            files=files,
        )
    raise ValueError(f"Missing exact aports recipe: {origin}@{commit}")


def collect_aports(records, output, token):
    needed = {
        (source["origin"], source["aportsCommit"])
        for record in records.values()
        for source in record["requiredSources"]
    }
    manifest = output / "aports.json"
    result = json.loads(manifest.read_text()) if manifest.exists() else []
    complete = {(entry["origin"], entry["aportsCommit"]) for entry in result}
    with ThreadPoolExecutor(max_workers=6) as pool:
        tasks = {
            pool.submit(fetch_aports_directory, origin, commit, output, token): (
                origin,
                commit,
            )
            for origin, commit in sorted(needed)
            if (origin, commit) not in complete
        }
        for future in as_completed(tasks):
            result.append(future.result())
    return sorted(result, key=lambda item: (item["origin"], item["aportsCommit"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventories", type=Path, required=True)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--phase", choices=("repositories", "go", "npm", "aports"), required=True
    )
    args = parser.parse_args()
    records = inventories(args.inventories)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    core = args.core.resolve()
    if args.phase == "repositories":
        result = collect_repositories(core, output)
    elif args.phase == "go":
        result = collect_go(records, core, output)
    elif args.phase == "npm":
        result = collect_npm(records, output)
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
        result = collect_aports(records, output, token)
    (output / (args.phase + ".json")).write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"Staged {args.phase}; runtime source closure still requires distfiles and audit"
    )


if __name__ == "__main__":
    main()
