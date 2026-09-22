#!/usr/bin/env python3
"""Maintainer: freeze a Docker-only Full installation, with initialization in Compose."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from lib.bundle_assets import checksums
from lib.image_snapshot import freeze
from lib.release_set import registry_set, release_version
from lib.standalone_compose import standalone

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--bootstrap-image", required=True)
    parser.add_argument(
        "--images",
        type=Path,
        help="Reviewed public service -> registry digest map; otherwise export local images",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    release_version(args.version)
    if subprocess.check_output(
        ["git", "-C", str(ROOT), "status", "--porcelain"], text=True
    ).strip():
        raise ValueError("Commit Full packaging before freezing a release")
    core = Path(
        subprocess.check_output(
            ["python3", "scripts/dependencies.py", "check", "gateway-core"],
            cwd=ROOT,
            text=True,
        ).strip()
    )
    compose = json.loads(
        subprocess.check_output(
            [
                "docker",
                "compose",
                "-f",
                "compose.yaml",
                "--profile",
                "*",
                "config",
                "--no-interpolate",
                "--no-path-resolution",
                "--format",
                "json",
            ],
            cwd=ROOT,
            text=True,
        )
    )
    compose = standalone(compose, args.bootstrap_image)
    if args.images:
        images = json.loads(args.images.read_text())
        compose = registry_set(compose, images)
        mode = "registry"
    else:
        compose, images = freeze(compose)
        mode = "local-offline"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    if mode == "local-offline":
        subprocess.run(
            [
                "docker",
                "image",
                "save",
                "-o",
                str(output / "images.tar"),
                *sorted({v["imageId"] for v in images.values()}),
            ],
            check=True,
        )
    full_commit = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    manifest = {
        "schemaVersion": 1,
        "zombieboxVersion": args.version,
        "distributionMode": mode,
        "images": images,
        "fullCommit": full_commit,
        "fullDirty": bool(
            subprocess.check_output(
                ["git", "-C", str(ROOT), "status", "--porcelain"], text=True
            ).strip()
        ),
        "configurationCoreCommit": subprocess.check_output(
            ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
        ).strip(),
        "publicationReady": False,
        "physicalValidation": False,
    }
    (output / "release.lock.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "compose.yaml").write_text(json.dumps(compose, indent=2) + "\n")
    shutil.copy2(
        core / "wrappers/rebrowser/seccomp_profile.json", output / "seccomp.json"
    )
    for filename in ("LICENSE", "NOTICE"):
        shutil.copy2(ROOT / filename, output / filename)
    instructions = (
        "# ZombieBox Full "
        + args.version
        + "\n\nRequires only Docker Engine and Compose on Linux. Keep the included static seccomp.json beside compose.yaml for the optional browser.\n\n"
    )
    if mode == "local-offline":
        instructions += "```sh\nsha256sum -c SHA256SUMS\ndocker image load -i images.tar\ndocker compose up -d\n```\n"
    else:
        instructions += "```sh\ndocker compose pull\ndocker compose up -d\n```\n"
    instructions += "\nInitialization creates persistent named volumes and private configuration automatically. No host Go/Python/Node/FFmpeg is used. Default services: gateway, discovery, MediaMTX, YouTube. Optional: `docker compose --profile spotify --profile airplay --profile youtube-receiver --profile rebrowser up -d`. Add Threadfin only when deliberately configuring its IPTV export.\n\nRead the operator code locally with `docker compose logs gateway`. Configure IPTV/Plex/Jellyfin/Stremio through Client Settings. Worker account authorization remains required.\n\nDo not run this on the same LAN ports as another ZombieBox installation. `docker compose down` preserves named volumes; `down -v` deletes state and credentials. Keep the full bundle and old version's manifest/images for rollback. A database downgrade requires a compatible saved backup.\n\nLocal evaluation only until corresponding-source and publication gates are met. No physical compatibility claim.\n"
    (output / "README.md").write_text(instructions)
    checksums(output)
    print(
        f"Prepared {args.version} Docker-only Full ({mode}) at {output}; no deployment/publication"
    )


if __name__ == "__main__":
    main()
