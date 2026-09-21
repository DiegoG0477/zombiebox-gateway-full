import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "release", ROOT / "scripts/release-bundle.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_source_free_digest_pinned_services_keep_runtime_constraints(self):
        compose = {
            "services": {
                name: {
                    "image": "local:test",
                    "build": {"context": "source"},
                    "mem_limit": "512m",
                    "profiles": ["optional"],
                }
                for name in release.SERVICES
            }
        }
        images = {
            name: "ghcr.io/owner/image@sha256:" + "a" * 64 for name in release.SERVICES
        }
        result = release.release_compose(compose, images)
        for service in result["services"].values():
            self.assertNotIn("build", service)
            self.assertEqual(service["mem_limit"], "512m")
            self.assertEqual(service["profiles"], ["optional"])

    def test_missing_workers_or_mutable_image_are_rejected(self):
        with self.assertRaises(ValueError):
            release.release_compose({}, {})
        images = {name: "ghcr.io/owner/image:latest" for name in release.SERVICES}
        with self.assertRaises(ValueError):
            release.release_compose({}, images)

    def test_unexpanded_runtime_paths_remain_bind_mounts(self):
        mount = {
            "source": "${ZOMBIE_CORE_DIR:-../gateway-core}/wrappers/mediamtx/mediamtx.yml",
            "target": "/mediamtx.yml",
            "type": "volume",
            "volume": {},
            "bind": {"selinux": "Z"},
        }
        compose = {"services": {"mediamtx": {"volumes": [mount]}}}
        images = {
            name: "ghcr.io/owner/image@sha256:" + "a" * 64 for name in release.SERVICES
        }
        result = release.release_compose(compose, images)
        actual = result["services"]["mediamtx"]["volumes"][0]
        self.assertEqual(actual["type"], "bind")
        self.assertNotIn("volume", actual)
        self.assertFalse(actual["bind"]["create_host_path"])
        self.assertEqual(actual["bind"]["selinux"], "Z")


if __name__ == "__main__":
    unittest.main()
