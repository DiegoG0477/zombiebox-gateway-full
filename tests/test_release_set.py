import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib.release_set import registry_set, release_version


class ReleaseSetTests(unittest.TestCase):
    def setUp(self):
        self.compose = {
            "services": {
                name: {"image": "development"}
                for name in ("gateway", "discovery", "initialize", "mediamtx")
            }
        }
        self.images = {
            name: "ghcr.io/zombiebox-tv/service@sha256:" + "a" * 64
            for name in self.compose["services"]
        }

    def test_every_release_has_an_explicit_version(self):
        for value in ("v0.1.0", "v0.2.0", "v0.1.0-dev.45"):
            self.assertEqual(release_version(value), value)
        for value in ("latest", "main", "v0.1", "../v0.1.0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                release_version(value)

    def test_mutable_or_missing_relay_and_initializer_are_rejected(self):
        for missing in ("initialize", "mediamtx"):
            images = self.images.copy()
            images.pop(missing)
            with self.assertRaises(ValueError):
                registry_set(self.compose, images)
        for value in (
            "ghcr.io/zombiebox-tv/service:latest",
            "ghcr.io/zombiebox-tv/service:v0.1.0",
        ):
            images = {**self.images, "initialize": value}
            with self.assertRaises(ValueError):
                registry_set(self.compose, images)

    def test_new_release_mapping_does_not_mutate_the_older_set(self):
        first = registry_set(self.compose, self.images)
        changed = {
            **self.images,
            "mediamtx": "ghcr.io/zombiebox-tv/relay@sha256:" + "b" * 64,
        }
        second = registry_set(self.compose, changed)
        self.assertNotEqual(
            first["services"]["mediamtx"]["image"],
            second["services"]["mediamtx"]["image"],
        )
        self.assertEqual(self.compose["services"]["mediamtx"]["image"], "development")
        self.assertEqual(
            self.images["mediamtx"], first["services"]["mediamtx"]["image"]
        )
