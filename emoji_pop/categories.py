"""
Category navigation strip and skin tone selector components.
"""

from typing import Callable, Optional
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from emoji_pop.data import CATEGORY_INFO
from emoji_pop.storage import get_storage

# Sleek Fitzpatrick skin tone swatches with hex color circles
SKIN_TONE_CONFIG = [
    {"code": "", "color_class": "skin-tone-dot-default", "color": "#FFD234", "name": "Default"},
    {"code": "\U0001F3FB", "color_class": "skin-tone-dot-light", "color": "#FADCBC", "name": "Light"},
    {"code": "\U0001F3FC", "color_class": "skin-tone-dot-med-light", "color": "#E0BB95", "name": "Medium-Light"},
    {"code": "\U0001F3FD", "color_class": "skin-tone-dot-medium", "color": "#BF8F68", "name": "Medium"},
    {"code": "\U0001F3FE", "color_class": "skin-tone-dot-med-dark", "color": "#9B643D", "name": "Medium-Dark"},
    {"code": "\U0001F3FF", "color_class": "skin-tone-dot-dark", "color": "#5A3825", "name": "Dark"},
]


class CategoryBar(Gtk.Box):
    """Horizontal category navigation strip with modern icon buttons."""

    def __init__(self, on_category_changed: Callable[[str], None]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.on_category_changed = on_category_changed
        self._buttons = {}
        self._active_id = "recent"

        self.add_css_class("category-bar")

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroll.set_hexpand(True)

        inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)

        for cat in CATEGORY_INFO:
            cat_id = cat["id"]
            btn = Gtk.Button(label=cat["symbol"])
            btn.set_tooltip_text(cat["title"])
            btn.add_css_class("category-tab-btn")
            btn.set_focus_on_click(False)
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
    """Sleek circular color swatch skin tone selector."""

    def __init__(self, on_tone_changed: Callable[[str], None]):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.on_tone_changed = on_tone_changed
        self._buttons = {}
        self._active_code = ""

        self.add_css_class("skin-tone-bar")

        for tone in SKIN_TONE_CONFIG:
            code = tone["code"]
            name = tone["name"]

            btn = Gtk.Button()
            btn.set_tooltip_text(f"Skin Tone: {name}")
            btn.add_css_class("skin-tone-btn")
            btn.set_focus_on_click(False)

            # Circular color swatch dot
            dot = Gtk.Box()
            dot.add_css_class("skin-tone-dot")
            dot.add_css_class(tone["color_class"])
            btn.set_child(dot)

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
