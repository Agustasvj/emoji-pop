"""
Persistent storage for Emoji Pop configuration, recent history, and favorites.
Adheres strictly to XDG Base Directory specifications.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("emoji_pop.storage")

DEFAULT_CONFIG: Dict[str, Any] = {
    "shortcut": "Super+period",
    "insertion_mode": "auto",       # "auto", "clipboard_paste" (wl-copy + Ctrl+V), "direct", "copy_only"
    "close_on_select": True,        # Directly insert into active text box on select
    "skin_tone": "",                # "", "\U0001F3FB", etc.
    "max_recent": 40,
    "restore_clipboard": False,
    "typing_delay_ms": 60,
    "theme": "system",              # "system", "dark", "light"
}

DEFAULT_STATE: Dict[str, Any] = {
    "recent": [
        "😂", "❤️", "👍", "🔥", "✨", "😊", "🎉", "🚀",
        "😍", "🙏", "🥺", "🥰", "💀", "🤔", "👏", "💯"
    ],
    "favorites": [
        "❤️", "🔥", "✨", "👍", "🚀"
    ],
    "last_category": "recent",
}


def get_config_dir() -> Path:
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        base = Path(xdg_config)
    else:
        base = Path.home() / ".config"
    config_dir = base / "emoji-pop"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_dir() -> Path:
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        base = Path(xdg_data)
    else:
        base = Path.home() / ".local" / "share"
    data_dir = base / "emoji-pop"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


class StorageManager:
    """Manages reading and writing user preferences and emoji state."""

    def __init__(self):
        self.config_file = get_config_dir() / "config.json"
        self.state_file = get_data_dir() / "state.json"
        self.config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.state: Dict[str, Any] = dict(DEFAULT_STATE)
        self.load()

    def load(self):
        # Load user configuration
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as fp:
                    loaded_cfg = json.load(fp)
                    if isinstance(loaded_cfg, dict):
                        self.config.update(loaded_cfg)
            except Exception as e:
                logger.warning("Could not read config file %s: %s", self.config_file, e)

        # Load state (recent, favorites)
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as fp:
                    loaded_state = json.load(fp)
                    if isinstance(loaded_state, dict):
                        self.state.update(loaded_state)
            except Exception as e:
                logger.warning("Could not read state file %s: %s", self.state_file, e)

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as fp:
                json.dump(self.config, fp, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save config to %s: %s", self.config_file, e)

    def save_state(self):
        try:
            with open(self.state_file, "w", encoding="utf-8") as fp:
                json.dump(self.state, fp, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save state to %s: %s", self.state_file, e)

    # --- Recent Emojis ---
    def get_recent(self) -> List[str]:
        return list(self.state.get("recent", []))

    def add_recent(self, emoji_char: str):
        recent = self.state.get("recent", [])
        if emoji_char in recent:
            recent.remove(emoji_char)
        recent.insert(0, emoji_char)
        max_recent = self.config.get("max_recent", 40)
        self.state["recent"] = recent[:max_recent]
        self.save_state()

    def clear_recent(self):
        self.state["recent"] = []
        self.save_state()

    # --- Favorites ---
    def get_favorites(self) -> List[str]:
        return list(self.state.get("favorites", []))

    def is_favorite(self, emoji_char: str) -> bool:
        return emoji_char in self.state.get("favorites", [])

    def toggle_favorite(self, emoji_char: str) -> bool:
        favorites = self.state.get("favorites", [])
        if emoji_char in favorites:
            favorites.remove(emoji_char)
            is_fav = False
        else:
            favorites.insert(0, emoji_char)
            is_fav = True
        self.state["favorites"] = favorites
        self.save_state()
        return is_fav

    # --- Skin Tone Preference ---
    def get_skin_tone(self) -> str:
        return self.config.get("skin_tone", "")

    def set_skin_tone(self, tone: str):
        self.config["skin_tone"] = tone
        self.save_config()

    # --- Category Preference ---
    def get_last_category(self) -> str:
        return self.state.get("last_category", "recent")

    def set_last_category(self, cat_id: str):
        self.state["last_category"] = cat_id
        self.save_state()


_storage_instance: Optional[StorageManager] = None


def get_storage() -> StorageManager:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageManager()
    return _storage_instance
