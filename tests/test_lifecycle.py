"""
Unit tests for CLI flags and utility functions.
"""

import sys
import unittest
import subprocess
from pathlib import Path
from emoji_pop.utils import check_environment, inspect_cosmic_shortcut

BIN_PATH = Path(__file__).resolve().parent.parent / "bin" / "emoji-pop"


class TestLifecycleAndUtils(unittest.TestCase):
    def test_environment_check(self):
        env = check_environment()
        self.assertIn("desktop", env)
        self.assertIn("has_wayland", env)
        self.assertTrue(env["has_wayland"])

    def test_inspect_shortcut(self):
        status = inspect_cosmic_shortcut()
        self.assertIsInstance(status, str)
        self.assertTrue(len(status) > 0)

    def test_cli_version_flag(self):
        res = subprocess.run([str(BIN_PATH), "--version"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Emoji Pop v", res.stdout)

    def test_cli_help_flag(self):
        res = subprocess.run([str(BIN_PATH), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Usage:", res.stdout)
        self.assertIn("toggle", res.stdout)


if __name__ == "__main__":
    unittest.main()
