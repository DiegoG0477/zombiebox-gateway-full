"""An incomplete or mismatched source receipt must never reach GHCR."""

import hashlib
import importlib.util
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_script(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicationGateTests(unittest.TestCase):
    def test_oci_archive_maps_source_identity_to_loaded_config(self):
        publisher = load_script("push-ghcr.py")
        blobs = {}

        def add(value):
            content = json.dumps(value, separators=(",", ":")).encode()
            digest = "sha256:" + hashlib.sha256(content).hexdigest()
            blobs["blobs/sha256/" + digest.removeprefix("sha256:")] = content
            return digest

        config = add({"os": "linux", "architecture": "amd64"})
        manifest = add({"config": {"digest": config}})
        image_id = add(
            {
                "manifests": [
                    {
                        "digest": manifest,
                        "platform": {"os": "linux", "architecture": "amd64"},
                    }
                ]
            }
        )
        blobs["index.json"] = json.dumps({"manifests": [{"digest": image_id}]}).encode()
        blobs["manifest.json"] = json.dumps(
            [{"Config": "blobs/sha256/" + config.removeprefix("sha256:")}]
        ).encode()
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "images.tar"
            with tarfile.open(archive_path, "w") as archive:
                for name, content in blobs.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(content)
                    archive.addfile(info, io.BytesIO(content))
            self.assertEqual(
                publisher.archive_config_ids(archive_path, {"gateway": image_id}),
                {"gateway": config},
            )
            with self.assertRaisesRegex(ValueError, "does not contain"):
                publisher.archive_config_ids(
                    archive_path, {"gateway": "sha256:" + "0" * 64}
                )

    def test_ghcr_push_requires_complete_matching_sources(self):
        publisher = load_script("push-ghcr.py")
        with self.assertRaisesRegex(ValueError, "complete corresponding sources"):
            publisher.publish(
                {"version": "v0.1.0-dev.46", "completeCorrespondingSources": False},
                "v0.1.0-dev.46",
                "ghcr.io/zombiebox-tv",
            )
        with self.assertRaisesRegex(ValueError, "complete corresponding sources"):
            publisher.publish(
                {"version": "v0.1.0-dev.45", "completeCorrespondingSources": True},
                "v0.1.0-dev.46",
                "ghcr.io/zombiebox-tv",
            )

    def test_bundle_requires_complete_sources_before_public_probe(self):
        finalizer = load_script("finalize-public-bundle.py")
        with self.assertRaisesRegex(ValueError, "Complete sources"):
            finalizer.finalize(
                "v0.1.0-dev.46",
                {"version": "v0.1.0-dev.46", "completeCorrespondingSources": False},
                {},
                Path("/unused"),
            )


if __name__ == "__main__":
    unittest.main()
