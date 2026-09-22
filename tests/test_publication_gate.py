"""An incomplete or mismatched source receipt must never reach GHCR."""

import importlib.util
import sys
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
