"""Private source/offline installs must keep one operator identity across restarts."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RuntimeSetupTests(unittest.TestCase):
    def test_operator_code_survives_reinstall_and_conflict_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "runtime"
            environment = {**os.environ, "ZOMBIE_RUNTIME_ROOT": str(runtime)}

            def prepare():
                return subprocess.run(
                    ["bash", str(ROOT / "scripts/setup-runtime.sh")],
                    env=environment,
                    text=True,
                    capture_output=True,
                )

            first = prepare()
            self.assertEqual(first.returncode, 0, first.stderr)
            config = runtime / ".local/gateway/config/operator.code"
            compose = runtime / ".local/gateway/compose.env"
            code = config.read_text().strip()
            self.assertRegex(code, r"^[0-9]{6}$")
            self.assertIn("ZOMBIE_PAIRING_CODE=" + code, compose.read_text())
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)

            second = prepare()
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(config.read_text().strip(), code)
            self.assertEqual(compose.read_text().count("ZOMBIE_PAIRING_CODE="), 1)

            compose.write_text(
                compose.read_text().replace(
                    "ZOMBIE_PAIRING_CODE=" + code, "ZOMBIE_PAIRING_CODE=000000"
                )
            )
            rejected = prepare()
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("differs", rejected.stderr)
            self.assertEqual(config.read_text().strip(), code)


if __name__ == "__main__":
    unittest.main()
