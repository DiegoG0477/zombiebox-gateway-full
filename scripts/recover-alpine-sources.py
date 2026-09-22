#!/usr/bin/env python3
"""Restore vanished upstream distfiles from Alpine's versioned mirror by SHA512."""

import argparse
import hashlib
import json
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

MIRROR = "https://distfiles.alpinelinux.org/distfiles/v3.23/"


def sha512(path):
    with path.open("rb") as content:
        return hashlib.file_digest(content, "sha512").hexdigest()


def recover(staging, distfiles):
    recipes = json.loads((staging / "aports.json").read_text())
    recovered = 0
    failures = []
    for entry in recipes:
        folder = staging / entry["directory"]
        checks = re.findall(
            r"\b([a-f0-9]{128})  ([^\s\"]+)", (folder / "APKBUILD").read_text()
        )
        for expected, filename in checks:
            if filename in {".", ".."} or "/" in filename or "\\" in filename:
                raise ValueError(f"Invalid source name: {filename}")
            if (folder / filename).is_file():
                continue
            target = distfiles / filename
            if target.is_file() and sha512(target) == expected:
                continue
            if shutil.disk_usage(distfiles).free < 3 * 1024**3:
                raise ValueError("Less than 3 GiB free; stop source recovery")
            temporary = distfiles / (filename + ".part")
            url = MIRROR + urllib.parse.quote(filename)
            try:
                with (
                    urllib.request.urlopen(url, timeout=30) as response,
                    temporary.open("wb") as output,
                ):
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                if sha512(temporary) != expected:
                    raise ValueError("mirror checksum differs")
                temporary.replace(target)
                recovered += 1
                print(f"Recovered {filename} from Alpine v3.23 distfiles")
            except Exception as error:
                temporary.unlink(missing_ok=True)
                failures.append(f"{filename}: {error}")
    if failures:
        raise ValueError("Unresolved Alpine sources:\n" + "\n".join(failures))
    print(f"Recovered {recovered} exact Alpine distfiles")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--distfiles", type=Path, required=True)
    args = parser.parse_args()
    recover(args.staging, args.distfiles)


if __name__ == "__main__":
    main()
