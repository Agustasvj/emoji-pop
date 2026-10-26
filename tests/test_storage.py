"""
Unit tests for XDG storage, preferences, recent history, and favorites.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from emoji_pop.storage import StorageManager


class TestStorageManager(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="emoji_pop_test_")
        self.orig_xdg_config = os.environ.get("XDG_CONFIG_HOME")
        self.orig_xdg_data = os.environ.get("XDG_DATA_HOME")

        os.environ["XDG_CONFIG_HOME"] = os.path.join(self.tmp_dir, "config")
        os.environ["XDG_DATA_HOME"] = os.path.join(self.tmp_dir, "data")
        self.storage = StorageManager()

    def tearDown(self):
        if self.orig_xdg_config is not None:
            os.environ["XDG_CONFIG_HOME"] = self.orig_xdg_config
        else:
            os.environ.pop("XDG_CONFIG_HOME", None)

        if self.orig_xdg_data is not None:
            os.environ["XDG_DATA_HOME"] = self.orig_xdg_data
        else:
            os.environ.pop("XDG_DATA_HOME", None)

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_default_config(self):
        self.assertEqual(self.storage.config.get("shortcut"), "Super+period")
        self.assertEqual(self.storage.config.get("insertion_mode"), "auto")
        self.assertTrue(self.storage.config.get("close_on_select"))

    def test_recent_addition_and_ordering(self):
        self.storage.clear_recent()
        self.assertEqual(self.storage.get_recent(), [])

        self.storage.add_recent("🚀")
        self.storage.add_recent("🔥")
        self.storage.add_recent("🚀")  # Adding 🚀 again should bump it to front

        recent = self.storage.get_recent()
        self.assertEqual(recent[0], "🚀")
        self.assertEqual(recent[1], "🔥")
        self.assertEqual(len(recent), 2)

    def test_favorites_toggle(self):
        self.storage.state["favorites"] = []
        self.storage.save_state()

        self.assertFalse(self.storage.is_favorite("🎉"))
        is_fav = self.storage.toggle_favorite("🎉")
        self.assertTrue(is_fav)
        self.assertTrue(self.storage.is_favorite("🎉"))

        is_fav_again = self.storage.toggle_favorite("🎉")
        self.assertFalse(is_fav_again)
        self.assertFalse(self.storage.is_favorite("🎉"))

    def test_skin_tone_preference(self):
        self.storage.set_skin_tone("\U0001F3FD")
        self.assertEqual(self.storage.get_skin_tone(), "\U0001F3FD")

        # Reload manager from disk
        new_mgr = StorageManager()
        self.assertEqual(new_mgr.get_skin_tone(), "\U0001F3FD")


if __name__ == "__main__":
    unittest.main()
