"""
Emoji data model, local index, search engine, and modifier logic.
"""

import os
import gzip
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
BUNDLE_GZ = ASSETS_DIR / "emoji_data.json.gz"
BUNDLE_RAW = ASSETS_DIR / "emoji_data.json"

ZWJ = "\u200D"

# Category metadata with human-readable titles and symbolic icon names
CATEGORY_INFO = [
    {"id": "recent", "title": "Recently Used", "icon": "document-open-recent-symbolic", "symbol": "🕒️"},
    {"id": "favorites", "title": "Favorites", "icon": "starred-symbolic", "symbol": "⭐️"},
    {"id": "smileys_emotion", "title": "Smileys & Emotion", "icon": "face-smile-symbolic", "symbol": "😀"},
    {"id": "people_body", "title": "People & Body", "icon": "avatar-default-symbolic", "symbol": "🧑"},
    {"id": "animals_nature", "title": "Animals & Nature", "icon": "emblem-photos-symbolic", "symbol": "🐱"},
    {"id": "food_drink", "title": "Food & Drink", "icon": "restaurant-symbolic", "symbol": "🍕"},
    {"id": "travel_places", "title": "Travel & Places", "icon": "mark-location-symbolic", "symbol": "🚀"},
    {"id": "activities", "title": "Activities", "icon": "media-playback-start-symbolic", "symbol": "⚽️"},
    {"id": "objects", "title": "Objects", "icon": "preferences-other-symbolic", "symbol": "💡️"},
    {"id": "symbols", "title": "Symbols", "icon": "dialog-information-symbolic", "symbol": "🔣️"},
    {"id": "flags", "title": "Flags", "icon": "flag-symbolic", "symbol": "🚩"},
    {"id": "kaomoji", "title": "Kaomoji", "icon": "text-html-symbolic", "symbol": "ʕ•ᴥ•ʔ"},
]


class EmojiItem:
    __slots__ = ("char", "name", "keywords", "category", "base_char")

    def __init__(self, char: str, name: str, keywords: List[str], category: str, base_char: Optional[str] = None):
        self.char = char
        self.name = name
        self.keywords = keywords
        self.category = category
        self.base_char = base_char or char

    def to_dict(self) -> Dict[str, Any]:
        return {
            "char": self.char,
            "name": self.name,
            "keywords": self.keywords,
            "category": self.category,
        }


class EmojiDatabase:
    """In-memory high-performance emoji registry and search index."""

    def __init__(self):
        self.categories: Dict[str, List[EmojiItem]] = {}
        self.all_emojis: Dict[str, EmojiItem] = {}
        self.skin_tone_emojis: Set[str] = set()
        self.gender_emojis: Set[str] = set()
        self.gender_swap_emojis: Set[str] = set()
        self.skin_tones: List[Dict[str, str]] = []
        self.kaomoji_list: List[Dict[str, str]] = []
        self._word_index: Dict[str, List[EmojiItem]] = {}
        self.loaded = False

    def load(self):
        if self.loaded:
            return

        data = None
        if BUNDLE_GZ.exists():
            with gzip.open(BUNDLE_GZ, "rt", encoding="utf-8") as fp:
                data = json.load(fp)
        elif BUNDLE_RAW.exists():
            with open(BUNDLE_RAW, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        else:
            raise FileNotFoundError(f"Emoji bundle not found at {BUNDLE_GZ} or {BUNDLE_RAW}")

        raw_categories = data.get("categories", {})
        for cat_id, items in raw_categories.items():
            category_list: List[EmojiItem] = []
            for item in items:
                emoji_obj = EmojiItem(
                    char=item["char"],
                    name=item["name"],
                    keywords=item.get("keywords", []),
                    category=cat_id,
                )
                category_list.append(emoji_obj)
                self.all_emojis[emoji_obj.char] = emoji_obj
            self.categories[cat_id] = category_list

        meta = data.get("modifier_meta", {})
        self.skin_tone_emojis = set(meta.get("skin_tone_emojis", []))
        self.gender_emojis = set(meta.get("gender_emojis", []))
        self.gender_swap_emojis = set(meta.get("gender_swap_emojis", []))
        self.skin_tones = meta.get("skin_tones", [])
        self.kaomoji_list = data.get("kaomoji", [])

        self._build_search_index()
        self.loaded = True

    def _build_search_index(self):
        """Build fast token index for instant prefix and word matching."""
        self._word_index.clear()
        for item in self.all_emojis.values():
            tokens = set()
            # Tokenize name
            for word in item.name.lower().split():
                clean_word = "".join(c for c in word if c.isalnum())
                if clean_word:
                    tokens.add(clean_word)
            # Tokenize keywords
            for kw in item.keywords:
                for word in kw.lower().split():
                    clean_word = "".join(c for c in word if c.isalnum())
                    if clean_word:
                        tokens.add(clean_word)

            for token in tokens:
                if token not in self._word_index:
                    self._word_index[token] = []
                self._word_index[token].append(item)

    def is_skin_tone_modifiable(self, emoji_str: str) -> bool:
        """Check if an emoji character or compound sequence supports skin tones."""
        if emoji_str in self.skin_tone_emojis:
            return True
        base = emoji_str.split(ZWJ)[0].rstrip("\uFE0F")
        return base in self.skin_tone_emojis

    def apply_skin_tone(self, emoji_str: str, tone: str) -> str:
        """Apply Fitzpatrick skin tone modifier to compatible emoji sequence."""
        if not tone:
            return emoji_str
        if not self.is_skin_tone_modifiable(emoji_str):
            return emoji_str

        parts = emoji_str.split(ZWJ)
        # Apply tone directly to the initial person/hand element
        parts[0] = parts[0].replace("\uFE0F", "") + tone
        return ZWJ.join(parts)

    def get_category_items(self, category_id: str, skin_tone: str = "") -> List[EmojiItem]:
        """Return items for a category with the specified skin tone applied."""
        self.load()
        if category_id == "kaomoji":
            return [
                EmojiItem(char=k["text"], name=k["name"], keywords=[k["name"]], category="kaomoji")
                for k in self.kaomoji_list
            ]

        items = self.categories.get(category_id, [])
        if not skin_tone:
            return items

        results = []
        for item in items:
            if self.is_skin_tone_modifiable(item.char):
                modified_char = self.apply_skin_tone(item.char, skin_tone)
                results.append(EmojiItem(
                    char=modified_char,
                    name=item.name,
                    keywords=item.keywords,
                    category=item.category,
                    base_char=item.char,
                ))
            else:
                results.append(item)
        return results

    def get_emoji(self, char: str) -> Optional[EmojiItem]:
        """Look up emoji metadata by character or base character."""
        self.load()
        if char in self.all_emojis:
            return self.all_emojis[char]
        # Check if it has a tone modifier
        base = char
        for tone_info in self.skin_tones:
            code = tone_info["code"]
            if code and code in base:
                base = base.replace(code, "")
                break
        return self.all_emojis.get(base)

    def search(self, query: str, skin_tone: str = "", limit: int = 100) -> List[EmojiItem]:
        """
        Search emojis by query string with relevance scoring.
        Scoring priorities:
        1. Exact character / exact name match (100)
        2. Exact keyword / alias match (85)
        3. Name starts with query (75)
        4. Word in name starts with query (60)
        5. Keyword starts with query (45)
        6. Substring in name / keywords (30)
        """
        self.load()
        q = query.strip().lower()
        if not q:
            return []

        # If user pasted an emoji directly, look it up immediately
        if q in self.all_emojis:
            return [self.all_emojis[q]]

        scores: Dict[str, Tuple[int, EmojiItem]] = {}
        q_words = q.split()

        for char, item in self.all_emojis.items():
            name_lower = item.name.lower()
            name_words = name_lower.split()

            score = 0
            # 1. Exact name match
            if q == name_lower:
                score = max(score, 100)

            # 2. Exact keyword match
            elif any(q == kw.lower() for kw in item.keywords):
                score = max(score, 85)

            # 3. Name starts with query
            elif name_lower.startswith(q):
                score = max(score, 75)

            # 4. Word in name starts with query
            elif any(w.startswith(q) for w in name_words):
                score = max(score, 60)

            # 5. Multi-word query all match name words
            elif len(q_words) > 1 and all(any(w.startswith(qw) for w in name_words) for qw in q_words):
                score = max(score, 55)

            # 6. Keyword starts with query
            elif any(kw.lower().startswith(q) for kw in item.keywords):
                score = max(score, 45)

            # 7. Substring in name
            elif q in name_lower:
                score = max(score, 30)

            # 8. Substring in keywords
            elif any(q in kw.lower() for kw in item.keywords):
                score = max(score, 20)

            if score > 0:
                scores[char] = (score, item)

        # Also search kaomoji
        for k in self.kaomoji_list:
            k_name = k["name"].lower()
            k_score = 0
            if q == k_name:
                k_score = 90
            elif k_name.startswith(q):
                k_score = 65
            elif q in k_name:
                k_score = 35
            elif q in k["text"]:
                k_score = 50

            if k_score > 0:
                k_item = EmojiItem(char=k["text"], name=k["name"], keywords=[k["name"]], category="kaomoji")
                scores[k["text"]] = (k_score, k_item)

        # Sort by score descending, then by name length ascending (shorter names first)
        ranked = sorted(scores.values(), key=lambda pair: (-pair[0], len(pair[1].name)))

        results = []
        for _, item in ranked[:limit]:
            if skin_tone and self.is_skin_tone_modifiable(item.char):
                modified = self.apply_skin_tone(item.char, skin_tone)
                results.append(EmojiItem(
                    char=modified,
                    name=item.name,
                    keywords=item.keywords,
                    category=item.category,
                    base_char=item.char,
                ))
            else:
                results.append(item)

        return results


# Global singleton instance
_db_instance: Optional[EmojiDatabase] = None


def get_emoji_db() -> EmojiDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = EmojiDatabase()
        _db_instance.load()
    return _db_instance
