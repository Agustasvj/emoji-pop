"""
Category navigation strip and skin tone selector components.
"""

from typing import Callable, Optional
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from emoji_pop.data import CATEGORY_INFO, get_emoji_db
from emoji_pop.storage import get_storage


class CategoryBar(Gtk.Box):
    """Horizontal category navigation strip with modern icon buttons."""

    def __init__(self, on_category_changed: Callable[[str], None]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.on_category_changed = on_category_changed
        self._buttons = {}
        self._active_id = "recent"

        self.add_css_class("category-bar")

        # Scrollable container in case of small window
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroll.set_hexpand(True)

        inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)

        for cat in CATEGORY_INFO:
            cat_id = cat["id"]
            btn = Gtk.Button(label=cat["symbol"])
            btn.set_tooltip_text(cat["title"])
            btn.add_css_class("category-tab-btn")
            btn.connect("clicked", self._on_button_clicked, cat_id)

            self._buttons[cat_id] = btn
            inner_box.append(btn)

        scroll.set_child(inner_box)
        self.append(scroll)

    def set_active_category(self, cat_id: str):
        if cat_id in self._buttons:
            if self._active_id in self._buttons:
                self._buttons[self._active_id].remove_css_class("active")
            self._active_id = cat_id
            self._buttons[cat_id].add_css_class("active")

    def _on_button_clicked(self, btn, cat_id: str):
        self.set_active_category(cat_id)
        self.on_category_changed(cat_id)


class SkinToneBar(Gtk.Box):
    """Compact Fitzpatrick skin tone selector row."""

    def __init__(self, on_tone_changed: Callable[[str], None]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.on_tone_changed = on_tone_changed
        self._buttons = {}
        self._active_code = ""

        self.add_css_class("skin-tone-bar")

        db = get_emoji_db()
        for tone_info in db.skin_tones:
            code = tone_info["code"]
            sample = tone_info["sample"]
            name = tone_info["name"]

            btn = Gtk.Button(label=sample)
            btn.set_tooltip_text(f"Skin Tone: {name}")
            btn.add_css_class("skin-tone-btn")
            btn.connect("clicked", self._on_button_clicked, code)

            self._buttons[code] = btn
            self.append(btn)

        storage = get_storage()
        current_tone = storage.get_skin_tone()
        self.set_active_tone(current_tone)

    def set_active_tone(self, tone_code: str):
        if self._active_code in self._buttons:
            self._buttons[self._active_code].remove_css_class("active")
        self._active_code = tone_code
        if tone_code in self._buttons:
            self._buttons[tone_code].add_css_class("active")

    def _on_button_clicked(self, btn, tone_code: str):
        self.set_active_tone(tone_code)
        storage = get_storage()
        storage.set_skin_tone(tone_code)
        self.on_tone_changed(tone_code)
