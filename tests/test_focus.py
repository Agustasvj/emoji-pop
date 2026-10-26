import unittest
from emoji_pop.focus import CosmicFocusManager


class TestCosmicFocus(unittest.TestCase):
    def setUp(self):
        self.mgr = CosmicFocusManager.get_instance()

    def test_focus_manager_initialization(self):
        self.assertIsNotNone(self.mgr)
        # Should be available on Pop!_OS COSMIC
        self.assertTrue(self.mgr.is_available)

    def test_capture_and_get_target_app_id(self):
        if self.mgr.is_available:
            app_id = self.mgr.capture_target()
            # If windows are open, app_id should be a string (or None if no window)
            self.assertTrue(app_id is None or isinstance(app_id, str))


if __name__ == "__main__":
    unittest.main()
