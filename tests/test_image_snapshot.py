import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib.image_snapshot import freeze, validate


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "Id": "sha256:" + "a" * 64,
            "Os": "linux",
            "Architecture": "amd64",
        }
        self.compose = {
            "services": {
                name: {
                    "image": "local:test",
                    "build": {"context": "../source"},
                    "mem_limit": "256m",
                    "profiles": ["optional"],
                    "volumes": [
                        {
                            "type": "volume",
                            "source": "${ZOMBIE_CORE_DIR}/config",
                            "target": "/config",
                            "volume": {},
                        }
                    ],
                }
                for name in ("gateway", "discovery", "airplay")
            }
        }

    def test_snapshot_preserves_constraints_and_replaces_tags_without_mutating_input(
        self,
    ):
        original = copy.deepcopy(self.compose)
        frozen, images = freeze(self.compose, lambda _: self.metadata)
        self.assertEqual(self.compose, original)
        for service in frozen["services"].values():
            self.assertEqual(service["image"], self.metadata["Id"])
            self.assertEqual(service["pull_policy"], "never")
            self.assertNotIn("build", service)
            self.assertEqual(service["profiles"], ["optional"])
            self.assertEqual(service["mem_limit"], "256m")
            self.assertEqual(service["platform"], "linux/amd64")
            self.assertEqual(service["volumes"][0]["type"], "bind")
            self.assertFalse(service["volumes"][0]["bind"]["create_host_path"])
        self.assertEqual(validate({"images": images}, lambda _: self.metadata), [])

    def test_generated_network_names_do_not_attach_to_the_previous_installation(self):
        self.compose["name"] = "zombie-box-tv"
        self.compose["networks"] = {
            "default": {"name": "zombie-box-tv_default"},
            "explicit": {"name": "operator-network", "external": True},
        }
        frozen, _ = freeze(self.compose, lambda _: self.metadata)
        self.assertNotIn("name", frozen["networks"]["default"])
        self.assertEqual(frozen["networks"]["explicit"]["name"], "operator-network")

    def test_missing_images_require_restore_and_changed_platform_is_rejected(self):
        _, images = freeze(self.compose, lambda _: self.metadata)

        def absent(_):
            raise subprocess.CalledProcessError(1, "docker")

        self.assertEqual(validate({"images": images}, absent), [self.metadata["Id"]])
        with self.assertRaises(ValueError):
            validate(
                {"images": images}, lambda _: {**self.metadata, "Architecture": "arm64"}
            )

    def test_mixed_gateway_identity_or_platform_cannot_form_a_candidate(self):
        self.compose["services"]["discovery"]["image"] = "different"
        for changed in ({"Id": "sha256:" + "b" * 64}, {"Architecture": "arm64"}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                freeze(
                    self.compose,
                    lambda ref: {
                        **self.metadata,
                        **(changed if ref == "different" else {}),
                    },
                )

    def test_local_ids_are_accepted_by_compose_without_interpolation(self):
        frozen, _ = freeze(self.compose, lambda _: self.metadata)
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-p",
                "zombie-snapshot-test",
                "-f",
                "-",
                "config",
                "--no-interpolate",
                "--no-path-resolution",
                "--format",
                "json",
            ],
            input=json.dumps(frozen),
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for service in json.loads(result.stdout)["services"].values():
            self.assertEqual(service["pull_policy"], "never")
