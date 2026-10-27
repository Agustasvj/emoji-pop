"""
Unit tests for insertion backend, clipboard operations, and fallback behavior.
"""

import unittest
from emoji_pop.insertion import InsertionBackend, InsertionMode


class TestInsertionBackend(unittest.TestCase):
    def setUp(self):
        self.backend = InsertionBackend(mode="auto")

    def test_tool_detection(self):
        # We know on this system wtype and wl-copy are installed
        self.assertTrue(self.backend.has_direct_typing())
        self.assertTrue(self.backend.has_clipboard_tools())

    def test_copy_to_clipboard_basic(self):
        test_char = "✨"
        ok = self.backend.copy_to_clipboard(test_char)
        self.assertTrue(ok)
        curr = self.backend.get_current_clipboard()
        if curr is not None:
            self.assertEqual(curr.strip(), test_char)

    def test_copy_to_clipboard_multicodepoint(self):
        # ZWJ multi-codepoint sequence
        complex_emoji = "🧑🏽‍💻"
        ok = self.backend.copy_to_clipboard(complex_emoji)
        self.assertTrue(ok)
        curr = self.backend.get_current_clipboard()
        if curr is not None:
            self.assertEqual(curr.strip(), complex_emoji)

    def test_insert_copy_only_flag(self):
        ok, msg = self.backend.insert("🎉", copy_only=True)
        self.assertTrue(ok)
        self.assertIn("clipboard", msg.lower())

    def test_copy_only_mode(self):
        copy_backend = InsertionBackend(mode=InsertionMode.COPY_ONLY)
        ok, msg = copy_backend.insert("🍕")
        self.assertTrue(ok)
        self.assertIn("clipboard", msg.lower())

    def test_simulate_paste_methods(self):
        # Test universal Shift+Insert
        ok_universal = self.backend.simulate_paste("universal")
        self.assertTrue(ok_universal)

        # Test Ctrl+V fallback
        ok_ctrl_v = self.backend.simulate_paste("ctrl_v")
        self.assertTrue(ok_ctrl_v)

    def test_primary_and_regular_clipboard(self):
        import subprocess
        test_char = "🚀"
        ok = self.backend.copy_to_clipboard(test_char)
        self.assertTrue(ok)

        # Verify regular clipboard
        proc1 = subprocess.run(["wl-paste"], capture_output=True, text=True, timeout=1.0)
        self.assertEqual(proc1.stdout.strip(), test_char)

        # Verify primary selection
        proc2 = subprocess.run(["wl-paste", "--primary"], capture_output=True, text=True, timeout=1.0)
        self.assertEqual(proc2.stdout.strip(), test_char)


    def test_type_or_paste(self):
        # type_or_paste should succeed with standard emojis and complex sequences
        ok_wave = self.backend.type_or_paste("👋")
        self.assertTrue(ok_wave)

        ok_fire = self.backend.type_or_paste("🔥")
        self.assertTrue(ok_fire)

        # Emoji with FE0F variation selector should also succeed without error
        ok_fe0f = self.backend.type_or_paste("❤️")
        self.assertTrue(ok_fe0f)

    def test_type_direct_strips_fe0f(self):
        ok = self.backend._type_direct("✊\uFE0F")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
