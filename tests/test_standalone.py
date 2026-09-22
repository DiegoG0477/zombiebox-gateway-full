import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lib.standalone_compose import standalone


class StandaloneComposeTests(unittest.TestCase):
    def test_real_compose_requires_no_operator_files_secrets_or_builds(self):
        source = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(ROOT / "compose.yaml"),
                    "--profile",
                    "*",
                    "config",
                    "--no-interpolate",
                    "--no-path-resolution",
                    "--format",
                    "json",
                ],
                text=True,
            )
        )
        result = standalone(source, "bootstrap:test")
        for service in result["services"].values():
            self.assertNotIn("build", service)
            for mount in service.get("volumes", []):
                self.assertEqual(mount["type"], "volume")
                self.assertIn(mount["source"], result["volumes"])
        self.assertNotIn("${ZOMBIE_RELAY_ADMIN_TOKEN", json.dumps(result))
        self.assertNotIn("${ZOMBIE_CORE_DIR", json.dumps(result))
        self.assertNotIn("${ZOMBIE_RUNTIME_ROOT", json.dumps(result))
        self.assertIn("service_completed_successfully", json.dumps(result))
        self.assertEqual(result["services"]["initialize"]["network_mode"], "none")
        self.assertEqual(
            result["services"]["gateway"]["entrypoint"],
            ["/bin/sh", "/config/launch.sh"],
        )
        rendered = subprocess.run(
            [
                "docker",
                "compose",
                "-p",
                "standalone-unit",
                "-f",
                "-",
                "--profile",
                "*",
                "config",
                "--quiet",
            ],
            input=json.dumps(result),
            text=True,
            capture_output=True,
        )
        self.assertEqual(rendered.returncode, 0, rendered.stderr)


class InitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        (self.assets / "probes").mkdir()
        (self.assets / "probes/baseline.mp4").write_bytes(b"probe fixture")
        for name in ("spotify.yml", "launch-gateway.sh"):
            (self.assets / name).write_bytes((ROOT / "bootstrap" / name).read_bytes())
        (self.assets / "mediamtx.yml").write_text("authMethod: http\n")
        self.seed = self.root / "seed"
        self.env = {
            **os.environ,
            "ZOMBIE_UID": str(os.getuid()),
            "ZOMBIE_GID": str(os.getgid()),
            "ZOMBIE_SEED_ROOT": str(self.seed),
            "ZOMBIE_SEED_ASSETS": str(self.assets),
        }

    def initialize(self):
        return subprocess.run(
            ["node", str(ROOT / "bootstrap/initialize.mjs")],
            env=self.env,
            text=True,
            capture_output=True,
        )

    def test_secrets_match_across_services_and_restart_preserves_operator_choices(self):
        first = self.initialize()
        self.assertEqual(first.returncode, 0, first.stderr)
        gateway = self.seed / "gateway"
        relay = (gateway / "relay.key").read_text().strip()
        self.assertNotIn(relay, first.stdout)
        self.assertIn(relay, (self.seed / "mediamtx/mediamtx.yml").read_text())
        providers = json.loads((gateway / "providers.json").read_text())
        yt = json.loads((self.seed / "youtube/youtube.json").read_text())
        self.assertEqual(providers["youtube"]["token"], yt["token"])
        providers["iptv"] = {"enabled": True, "url": "https://example.org/my.m3u"}
        (gateway / "providers.json").write_text(json.dumps(providers))
        before = {
            p.relative_to(self.seed): p.read_bytes()
            for p in self.seed.rglob("*")
            if p.is_file()
        }
        second = self.initialize()
        self.assertEqual(second.returncode, 0, second.stderr)
        after = {
            p.relative_to(self.seed): p.read_bytes()
            for p in self.seed.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual((gateway / "relay.key").stat().st_mode & 0o777, 0o600)

    def test_new_image_assets_change_without_rotating_account_secrets(self):
        self.assertEqual(self.initialize().returncode, 0)
        key = (self.seed / "gateway/relay.key").read_bytes()
        changed = b"#!/bin/sh\n# updated launcher fixture\n"
        (self.assets / "launch-gateway.sh").write_bytes(changed)
        (self.assets / "probes/baseline.mp4").write_bytes(b"new probe fixture")
        self.assertEqual(self.initialize().returncode, 0)
        self.assertEqual((self.seed / "gateway/launch.sh").read_bytes(), changed)
        self.assertEqual(
            (self.seed / "probes/baseline.mp4").read_bytes(), b"new probe fixture"
        )
        self.assertEqual((self.seed / "gateway/relay.key").read_bytes(), key)

    def test_invalid_existing_secret_is_preserved_and_blocks_startup(self):
        self.assertEqual(self.initialize().returncode, 0)
        key = self.seed / "gateway/relay.key"
        key.write_text("broken-value")
        result = self.initialize()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(key.read_text(), "broken-value")
        self.assertNotIn("broken-value", result.stderr)

    def test_configuration_links_are_not_followed(self):
        self.assertEqual(self.initialize().returncode, 0)
        key = self.seed / "gateway/relay.key"
        key.unlink()
        key.symlink_to(self.assets / "spotify.yml")
        before = (self.assets / "spotify.yml").read_bytes()
        self.assertNotEqual(self.initialize().returncode, 0)
        self.assertEqual((self.assets / "spotify.yml").read_bytes(), before)
