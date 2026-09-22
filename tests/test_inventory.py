import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "image_inventory",
    Path(__file__).resolve().parents[1] / "scripts/inventory-image.py",
)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class ImageInventoryTests(unittest.TestCase):
    def test_file_metadata_cannot_overwrite_package_origin(self):
        text = (
            "P:libexample\nV:1.0-r0\no:example\nL:MIT\nc:"
            + "a" * 40
            + "\nF:usr/lib\nP:wrong\no:wrong\n"
        )
        package = inventory.alpine_packages(text)[0]
        self.assertEqual(package["name"], "libexample")
        self.assertEqual(package["origin"], "example")

    def test_unknown_recipe_and_duplicate_package_fail_closed(self):
        valid = "P:a\nV:1\no:a\nL:MIT\nc:" + "a" * 40
        for text in ("", "P:a\nV:1\no:a\nL:MIT", valid + "\n\n" + valid):
            with self.subTest(text=text), self.assertRaises(ValueError):
                inventory.alpine_packages(text)


class GoBinaryInventoryTests(unittest.TestCase):
    def test_linked_dependencies_and_revision_are_read_without_private_build_flags(
        self,
    ):
        result = inventory.go_build_info("""/temporary/binary: go1.25.6
\tpath\tzombiebox.local/gateway/cmd/zombied
\tmod\tzombiebox.local/gateway\t(devel)
\tdep\texample.org/library\tv1.2.3\th1:known
\tbuild\tGOOS=linux
\tbuild\tvcs.revision=abc123
\tbuild\t-ldflags=private-build-string
""")
        self.assertEqual(result["package"], "zombiebox.local/gateway/cmd/zombied")
        self.assertEqual(result["dependencies"][0]["goSum"], "h1:known")
        self.assertFalse(result["dependencies"][0]["sourceCollected"])
        self.assertEqual(result["build"], {"GOOS": "linux", "vcs.revision": "abc123"})
        self.assertNotIn("private", str(result))

    def test_replaced_or_absent_build_metadata_cannot_attest_the_wrong_sources(self):
        for value in (
            "",
            "not a Go executable",
            "binary: go1.25.6\n",
            "binary: go1.25.6\n\t=>\t/private/replacement\t(devel)\n",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                inventory.go_build_info(value)
