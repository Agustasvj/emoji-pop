"""
Unit tests for Emoji Pop data loader, search engine, and Unicode modifier pipeline.
"""

import unittest
from emoji_pop.data import EmojiDatabase, EmojiItem, get_emoji_db


class TestEmojiData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_emoji_db()

    def test_database_loads_successfully(self):
        self.assertTrue(self.db.loaded)
        self.assertGreater(len(self.db.all_emojis), 1500)
        self.assertGreater(len(self.db.categories), 8)
        self.assertGreater(len(self.db.kaomoji_list), 10)

    def test_exact_search_terms(self):
        # 1. "laugh" should find 😂, 🤣, 😆
        results = self.db.search("laugh", limit=10)
        chars = [item.char for item in results]
        self.assertIn("😂", chars)
        self.assertIn("🤣", chars)

        # 2. "rocket" should find 🚀
        results = self.db.search("rocket", limit=5)
        chars = [item.char for item in results]
        self.assertIn("🚀", chars)

        # 3. "heart" should find ❤️ or hearts
        results = self.db.search("heart", limit=10)
        chars = [item.char for item in results]
        self.assertTrue(any(c in chars for c in ("❤️", "💖", "💕", "🤍", "🤎")))

        # 4. "thumbs up" should find 👍
        results = self.db.search("thumbs up", limit=5)
        chars = [item.char for item in results]
        self.assertIn("👍", chars)

        # 5. "fire" should find 🔥
        results = self.db.search("fire", limit=5)
        chars = [item.char for item in results]
        self.assertIn("🔥", chars)

        # 6. "cat" should find 🐱 or 🐈
        results = self.db.search("cat", limit=10)
        chars = [item.char for item in results]
        self.assertTrue(any(c in chars for c in ("🐱", "🐈", "😸")))

    def test_kaomoji_search(self):
        results = self.db.search("shrug")
        chars = [item.char for item in results]
        self.assertTrue(any("ツ" in c for c in chars))

    def test_skin_tone_modifier_application(self):
        tone_medium = "\U0001F3FD"  # 🏽

        # Single-codepoint modifiable emoji
        res = self.db.apply_skin_tone("👍", tone_medium)
        self.assertEqual(res, "👍🏽")

        # ZWJ sequence modifiable emoji
        res_worker = self.db.apply_skin_tone("🧑‍💻", tone_medium)
        self.assertEqual(res_worker, "🧑🏽‍💻")

        # Non-modifiable emoji should remain unchanged
        res_rocket = self.db.apply_skin_tone("🚀", tone_medium)
        self.assertEqual(res_rocket, "🚀")

    def test_search_with_skin_tone_filter(self):
        tone_dark = "\U0001F3FF"  # 🏿
        results = self.db.search("thumbs up", skin_tone=tone_dark)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].char, "👍🏿")

    def test_empty_and_whitespace_queries(self):
        self.assertEqual(self.db.search(""), [])
        self.assertEqual(self.db.search("   "), [])

    def test_non_matching_query(self):
        results = self.db.search("xyzzy123nonexistent")
        self.assertEqual(results, [])

    def test_categories_retrieval(self):
        smileys = self.db.get_category_items("smileys_emotion")
        self.assertGreater(len(smileys), 100)

        flags = self.db.get_category_items("flags")
        self.assertGreater(len(flags), 200)

        kaomoji = self.db.get_category_items("kaomoji")
        self.assertGreater(len(kaomoji), 10)

    def test_bmp_emojis_have_fe0f(self):
        """Verify that BMP symbols that require FE0F for color emoji rendering have it."""
        coffee = self.db.get_emoji("☕️") or self.db.get_emoji("☕\uFE0F")
        self.assertIsNotNone(coffee)
        self.assertTrue(coffee.char.endswith("\uFE0F"))

        star = self.db.get_emoji("⭐️") or self.db.get_emoji("⭐\uFE0F")
        self.assertIsNotNone(star)
        self.assertTrue(star.char.endswith("\uFE0F"))

        soccer = self.db.get_emoji("⚽️") or self.db.get_emoji("⚽\uFE0F")
        self.assertIsNotNone(soccer)
        self.assertTrue(soccer.char.endswith("\uFE0F"))


if __name__ == "__main__":
    unittest.main()
