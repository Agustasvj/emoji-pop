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


if __name__ == "__main__":
    unittest.main()
