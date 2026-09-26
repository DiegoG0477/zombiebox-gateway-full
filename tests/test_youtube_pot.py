import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lib.standalone_compose import MOUNTS, standalone


class YouTubePotPackagingTests(unittest.TestCase):
    def setUp(self):
        self.compose_file = ROOT / "compose.yaml"
        # Parse compose.yaml
        output = subprocess.check_output(
            [
                "docker",
                "compose",
                "-f",
                str(self.compose_file),
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
        self.compose_data = json.loads(output)
        self.services = self.compose_data.get("services", {})

    def test_services_present_under_youtube_pot_profile(self):
        self.assertIn("youtube-pot", self.services)
        self.assertIn("bgutil-provider", self.services)

        pot_svc = self.services["youtube-pot"]
        bgutil_svc = self.services["bgutil-provider"]

        # Strictly opt-in: must have profiles: ['youtube-pot']
        self.assertEqual(pot_svc.get("profiles"), ["youtube-pot"])
        self.assertEqual(bgutil_svc.get("profiles"), ["youtube-pot"])

    def test_network_isolation_and_no_published_host_ports(self):
        bgutil_svc = self.services["bgutil-provider"]
        pot_svc = self.services["youtube-pot"]

        # MUST NOT publish host ports (no LAN / 0.0.0.0 exposure!)
        self.assertNotIn("ports", bgutil_svc)
        self.assertNotIn("ports", pot_svc)

        # Internal exposure only
        self.assertEqual([int(p) for p in bgutil_svc.get("expose", [])], [4416])
        self.assertEqual([int(p) for p in pot_svc.get("expose", [])], [8097])

    def test_immutable_digest_and_security_opts(self):
        bgutil_svc = self.services["bgutil-provider"]
        image = bgutil_svc.get("image", "")
        # Pinned version and sha256 digest, no 'latest'
        self.assertIn("brainicism/bgutil-ytdlp-pot-provider:2.0.0@sha256:", image)
        self.assertNotIn(":latest", image)

        pot_svc = self.services["youtube-pot"]
        self.assertTrue(pot_svc.get("read_only"))
        self.assertIn("no-new-privileges:true", pot_svc.get("security_opt", []))
        self.assertEqual(pot_svc.get("cap_drop"), ["ALL"])

    def test_standalone_mounts_mapping(self):
        self.assertIn("youtube-pot", MOUNTS)
        self.assertEqual(MOUNTS["youtube-pot"], {"/config": "youtube-pot"})

        standalone_res = standalone(self.compose_data, "bootstrap:test")
        self.assertIn("youtube-pot", standalone_res["volumes"])
        svc = standalone_res["services"]["youtube-pot"]
        self.assertEqual(svc["volumes"][0]["source"], "youtube-pot")
        self.assertEqual(svc["volumes"][0]["target"], "/config")


class SetupYouTubeScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        # Create minimal gateway config structure
        gateway_config = self.root / ".local/gateway/config"
        gateway_config.mkdir(parents=True)
        (gateway_config / "providers.json").write_text(json.dumps({}))

    def run_setup(self, *extra_args):
        env = {**os.environ, "ZOMBIE_RUNTIME_ROOT": str(self.root)}
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/setup-youtube.py"), *extra_args],
            env=env,
            capture_output=True,
            text=True,
        )

    def test_setup_default_without_pot(self):
        res = self.run_setup("--enable")
        self.assertEqual(res.returncode, 0, res.stderr)

        providers = json.loads(
            (self.root / ".local/gateway/config/providers.json").read_text()
        )
        self.assertEqual(providers["youtube"]["url"], "http://youtube:8091")
        self.assertTrue(providers["youtube"]["enabled"])
        self.assertFalse((self.root / ".local/youtube-pot").exists())

    def test_setup_with_pot_flag(self):
        res = self.run_setup("--enable", "--pot")
        self.assertEqual(res.returncode, 0, res.stderr)

        providers = json.loads(
            (self.root / ".local/gateway/config/providers.json").read_text()
        )
        self.assertEqual(providers["youtube"]["url"], "http://youtube-pot:8097")
        self.assertTrue(providers["youtube"]["enabled"])

        pot_config = self.root / ".local/youtube-pot/pot.json"
        self.assertTrue(pot_config.exists())
        self.assertEqual(pot_config.stat().st_mode & 0o777, 0o600)

        data = json.loads(pot_config.read_text())
        self.assertEqual(data["upstream_url"], "http://youtube:8091")
        self.assertEqual(data["bgutil_url"], "http://bgutil-provider:4416")
        self.assertEqual(data["token"], providers["youtube"]["token"])

    def test_mismatched_existing_pot_identity_preserves_gateway_route(self):
        first = self.run_setup("--enable")
        self.assertEqual(first.returncode, 0, first.stderr)
        providers_path = self.root / ".local/gateway/config/providers.json"
        before = providers_path.read_text()
        pot_directory = self.root / ".local/youtube-pot"
        pot_directory.mkdir()
        (pot_directory / "pot.json").write_text(
            json.dumps(
                {
                    "token": "mismatched-token",
                    "upstream_url": "http://youtube:8091",
                    "bgutil_url": "http://bgutil-provider:4416",
                }
            )
        )

        result = self.run_setup("--enable", "--pot")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(providers_path.read_text(), before)
        self.assertIn("preserved configuration", result.stderr)

    def test_selecting_base_worker_after_pot_restores_base_route(self):
        self.assertEqual(self.run_setup("--enable", "--pot").returncode, 0)
        result = self.run_setup("--enable")
        self.assertEqual(result.returncode, 0, result.stderr)
        providers = json.loads(
            (self.root / ".local/gateway/config/providers.json").read_text()
        )
        self.assertEqual(providers["youtube"]["url"], "http://youtube:8091")

    def test_custom_gateway_route_is_preserved_when_enabling_pot(self):
        self.assertEqual(self.run_setup("--enable").returncode, 0)
        providers_path = self.root / ".local/gateway/config/providers.json"
        providers = json.loads(providers_path.read_text())
        providers["youtube"]["url"] = "http://custom-youtube:8091"
        providers_path.write_text(json.dumps(providers))
        before = providers_path.read_text()

        result = self.run_setup("--enable", "--pot")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(providers_path.read_text(), before)
        self.assertIn("preserved configuration", result.stderr)


if __name__ == "__main__":
    unittest.main()
