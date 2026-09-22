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
