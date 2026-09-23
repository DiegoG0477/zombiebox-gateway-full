"""The public installer uses a frozen, verified bundle and Docker only."""

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "v0.1.0-dev.52"
ASSETS = (
    "compose.yaml",
    "seccomp.json",
    "release.lock.json",
    "README.md",
    "LICENSE",
    "NOTICE",
)


class DockerInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.assets = self.path / "assets"
        self.assets.mkdir()
        for name in ASSETS:
            (self.assets / name).write_text(name + "\n")
        (self.assets / "release.lock.json").write_text(
            '{"zombieboxVersion": "v0.1.0-dev.52", "publicationReady": true}\n'
        )
        self.checksums()
        self.bin = self.path / "bin"
        self.bin.mkdir()
        docker = self.bin / "docker"
        docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_CALLS"\n')
        docker.chmod(0o755)
        self.calls = self.path / "docker-calls"
        self.channel = self.path / "channel.txt"
        self.channel.write_text(VERSION + "\n")

    def checksums(self):
        (self.assets / "SHA256SUMS").write_text(
            "".join(
                hashlib.sha256((self.assets / name).read_bytes()).hexdigest()
                + "  "
                + name
                + "\n"
                for name in ASSETS
            )
        )

    def install(self):
        return subprocess.run(
            [
                "sh",
                str(ROOT / "install-docker.sh"),
                "--directory",
                str(self.path / "installed"),
            ],
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                "ZOMBIE_RELEASE_BASE_URL": self.assets.as_uri(),
                "ZOMBIE_INSTALL_CHANNEL_URL": self.channel.as_uri(),
                "DOCKER_CALLS": str(self.calls),
            },
        )

    def test_installs_once_and_reuses_verified_release(self):
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue((self.path / "installed" / VERSION / "compose.yaml").exists())
        second = self.install()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(
            self.calls.read_text().splitlines(),
            ["compose version", "compose pull", "compose up -d"] * 2,
        )

    def test_rejects_tampering_without_starting_containers(self):
        (self.assets / "compose.yaml").write_text("altered\n")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls.read_text().splitlines(), ["compose version"])
        self.assertFalse((self.path / "installed" / VERSION).exists())

    def test_rejects_unpublished_manifest(self):
        (self.assets / "release.lock.json").write_text(
            '{"zombieboxVersion": "v0.1.0-dev.52", "publicationReady": false}\n'
        )
        self.checksums()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("publication gate", result.stderr)
        self.assertEqual(self.calls.read_text().splitlines(), ["compose version"])

    def test_rejects_bad_channel_without_download_or_start(self):
        self.channel.write_text("v0.1.0-dev.54;invalid\n")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_explicit_version_does_not_need_channel(self):
        self.channel.unlink()
        result = subprocess.run(
            [
                "sh",
                str(ROOT / "install-docker.sh"),
                "--version",
                VERSION,
                "--directory",
                str(self.path / "installed"),
            ],
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                "ZOMBIE_RELEASE_BASE_URL": self.assets.as_uri(),
                "ZOMBIE_INSTALL_CHANNEL_URL": self.channel.as_uri(),
                "DOCKER_CALLS": str(self.calls),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
