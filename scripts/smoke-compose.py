#!/usr/bin/env python3
"""Maintainer host verification of Docker-only startup and preserved named volumes."""

import json
import os
import secrets
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from lib.image_snapshot import freeze
from lib.standalone_compose import standalone

ROOT = Path(__file__).resolve().parents[1]


def main():
    core = Path(
        subprocess.check_output(
            ["python3", "scripts/dependencies.py", "check", "gateway-core"],
            cwd=ROOT,
            text=True,
        ).strip()
    )
    source = json.loads(
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
    compose = standalone(
        source,
        os.environ.get(
            "ZOMBIE_BOOTSTRAP_IMAGE", "zombie-box-tv/bootstrap:0.1.0-dev.45"
        ),
    )
    compose, _ = freeze(compose)
    # Keep host-network discovery outside this isolated host-only fixture. The
    # production Compose still uses the real constrained LAN sidecar.
    compose["services"]["discovery"]["profiles"] = ["physical-lan"]
    for name, target in (("gateway", 8090), ("mediamtx", 8554)):
        compose["services"][name]["ports"] = [
            {
                "host_ip": "127.0.0.1",
                "published": "0",
                "target": target,
                "protocol": "tcp",
            }
        ]
    profiles = []
    if os.environ.get("ZOMBIE_SMOKE_ALL") == "1":
        profiles = ["spotify", "airplay", "youtube-receiver", "threadfin", "rebrowser"]
        for name in ("airplay", "youtube-receiver"):
            compose["services"][name].pop("network_mode", None)
            compose["services"][name]["networks"] = {"default": {}}
        compose["services"]["threadfin"]["ports"] = []
    project = "zombie-compose-check-" + secrets.token_hex(4)
    with tempfile.TemporaryDirectory(prefix=project) as directory:
        file = Path(directory) / "compose.json"
        file.write_text(json.dumps(compose))
        (Path(directory) / "seccomp.json").write_bytes(
            (core / "wrappers/rebrowser/seccomp_profile.json").read_bytes()
        )
        command = ["docker", "compose", "-p", project, "-f", str(file)]
        for profile in profiles:
            command += ["--profile", profile]
        try:
            subprocess.run(
                command + ["up", "-d", "--wait", "--wait-timeout", "120"], check=True
            )

            def gateway(*args):
                return subprocess.check_output(
                    command + ["exec", "-T", "gateway", *args], text=True
                )

            before = gateway(
                "sha256sum",
                "/config/operator.code",
                "/config/relay.key",
                "/config/providers.json",
            )
            before_yt = subprocess.check_output(
                command
                + ["exec", "-T", "youtube", "sha256sum", "/config/youtube.json"],
                text=True,
            )
            bound = subprocess.check_output(
                command + ["port", "gateway", "8090"], text=True
            ).strip()
            with urllib.request.urlopen(
                "http://" + bound + "/health", timeout=5
            ) as response:
                assert response.status == 200
            # Authenticate with the generated operator code, without printing it.
            code = gateway("cat", "/config/operator.code").strip()
            request = urllib.request.Request(
                "http://" + bound + "/v1/devices/register",
                data=json.dumps(
                    {
                        "clientVersion": "compose-fixture",
                        "protocolVersion": 1,
                        "installationId": project,
                        "pairingCode": code,
                        "platform": {"androidApi": 13},
                    }
                ).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                assert response.status in (200, 201)
            # Re-running initialization must preserve secrets and generated relay config.
            subprocess.run(
                command
                + ["up", "-d", "--force-recreate", "--wait", "--wait-timeout", "120"],
                check=True,
            )
            assert before == gateway(
                "sha256sum",
                "/config/operator.code",
                "/config/relay.key",
                "/config/providers.json",
            )
            assert before_yt == subprocess.check_output(
                command
                + ["exec", "-T", "youtube", "sha256sum", "/config/youtube.json"],
                text=True,
            )
            print(
                "PASS: Docker-only startup, generated-code pairing, relay/YouTube startup and secret/config persistence across recreation"
            )
        finally:
            # Only this test's fresh project/volumes are removed; no user runtime.
            subprocess.run(command + ["down", "--volumes"], check=True)


if __name__ == "__main__":
    main()
