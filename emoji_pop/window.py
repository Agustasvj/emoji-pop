"""
Main application window for Emoji Pop.
Windows 11 inspired floating popup with multi-pick support, auto-dismiss on click outside,
instant search, and zero-flicker rendering.
"""

import os
from typing import Optional, List
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from emoji_pop.data import EmojiItem, get_emoji_db
from emoji_pop.storage import get_storage
from emoji_pop.grid import EmojiGrid
from emoji_pop.categories import CategoryBar, SkinToneBar
from emoji_pop.insertion import InsertionBackend


class EmojiPopWindow(Gtk.ApplicationWindow):
    """Floating emoji popup window."""

    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="Emoji Pop")
        self.set_default_size(380, 470)
        self.set_resizable(False)
        self.add_css_class("emoji-pop-window")

        self.storage = get_storage()
        self.db = get_emoji_db()
        self.insertion = InsertionBackend(
            mode=self.storage.config.get("insertion_mode", "auto"),
            typing_delay_ms=self.storage.config.get("typing_delay_ms", 60),
            restore_clipboard=self.storage.config.get("restore_clipboard", False),
        )

        self._active_category = self.storage.get_last_category()
        self._search_timer_id = 0
        self._base_status_text = ""
        self._selected_buffer: List[str] = []
        self._is_dismissing = False

        # Outer card container
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("emoji-pop-card")

        # 1. Header (Search entry + Skin tone selector + Close button)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.add_css_class("emoji-pop-header")

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Search emojis...")
        self.search_entry.add_css_class("emoji-pop-search")
        self.search_entry.connect("search-changed", self._on_search_changed)

        self.skin_tone_bar = SkinToneBar(on_tone_changed=self._on_skin_tone_changed)

        # Close button '✕'
        close_btn = Gtk.Button(label="✕")
        close_btn.set_tooltip_text("Close (Esc)")
        close_btn.add_css_class("close-window-btn")
        close_btn.set_focus_on_click(False)
        close_btn.connect("clicked", lambda b: self.close_window(paste_pending=False))

        header_box.append(self.search_entry)
        header_box.append(self.skin_tone_bar)
        header_box.append(close_btn)
        card.append(header_box)

        # 2. Category navigation strip
        self.category_bar = CategoryBar(on_category_changed=self._on_category_selected)
        card.append(self.category_bar)

        # 3. Main Grid (Zero-flicker stack-based)
        self.grid = EmojiGrid(on_select=self._on_emoji_selected, on_hover=self._on_emoji_hovered)
        card.append(self.grid)

        # 4. Footer (Fixed height to prevent any layout jerking/flickering)
        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        footer_box.set_size_request(-1, 30)
        footer_box.add_css_class("emoji-pop-footer")

        self.status_label = Gtk.Label(label="Emoji Pop")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_hexpand(True)
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.status_label.add_css_class("footer-status-label")

        hints_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hints_box.set_halign(Gtk.Align.END)

        k_enter = Gtk.Label(label="↵ Insert")
        k_enter.add_css_class("footer-key-hint")
        k_esc = Gtk.Label(label="Esc Close")
        k_esc.add_css_class("footer-key-hint")

        hints_box.append(k_enter)
        hints_box.append(k_esc)

        footer_box.append(self.status_label)
        footer_box.append(hints_box)
        card.append(footer_box)

        self.set_child(card)

        # Setup keyboard controllers
        self._setup_key_handling()

        # Auto-dismiss when clicking outside window
        self.connect("notify::is-active", self._on_window_active_changed)

        # Load initial category
        self.show_category(self._active_category)

    def _setup_key_handling(self):
        win_key_ctrl = Gtk.EventControllerKey.new()
        win_key_ctrl.connect("key-pressed", self._on_window_key_pressed)
        self.add_controller(win_key_ctrl)

        search_key_ctrl = Gtk.EventControllerKey.new()
        search_key_ctrl.connect("key-pressed", self._on_search_key_pressed)
        self.search_entry.add_controller(search_key_ctrl)

    def _on_window_key_pressed(self, controller, keyval, keycode, state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close_window(paste_pending=False)
            return True
        return False

    def _on_search_key_pressed(self, controller, keyval, keycode, state) -> bool:
        shift_held = bool(state & Gdk.ModifierType.SHIFT_MASK)

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            # Select top result and close
            selected = self.grid.select_first(copy_only=shift_held)
            if selected:
                self.close_window(paste_pending=not shift_held)
            return True
        elif keyval == Gdk.KEY_Down:
            return self.grid.focus_first()
        return False

    def _on_window_active_changed(self, window, param):
        """Auto-dismiss when clicking outside the window."""
        if not self.is_active() and self.get_visible() and not self._is_dismissing:
            # User clicked outside window -> close and paste accumulated emojis
            GLib.timeout_add(50, self._handle_outside_click)

    def _handle_outside_click(self) -> bool:
        if not self.is_active() and self.get_visible() and not self._is_dismissing:
            self.close_window(paste_pending=True)
        return False

    def _on_search_changed(self, entry: Gtk.SearchEntry):
        """Debounced search to ensure snappy typing with zero flicker."""
        if self._search_timer_id:
            GLib.source_remove(self._search_timer_id)
            self._search_timer_id = 0

        self._search_timer_id = GLib.timeout_add(60, self._execute_search)

    def _execute_search(self) -> bool:
        self._search_timer_id = 0
        query = self.search_entry.get_text().strip()

        if not query:
            self.show_category(self._active_category)
            return False

        skin_tone = self.storage.get_skin_tone()
        results = self.db.search(query, skin_tone=skin_tone, limit=120)

        self.grid.show_search_results(query, results)

        count = len(results)
        self._set_status(f"Found {count} emoji" if count == 1 else f"Found {count} emojis")
        return False

    def _on_skin_tone_changed(self, tone_code: str):
        self.grid.invalidate_cache()
        query = self.search_entry.get_text().strip()
        if query:
            self._execute_search()
        else:
            self.show_category(self._active_category, force_refresh=True)

    def _on_category_selected(self, cat_id: str):
        self.search_entry.set_text("")
        self._active_category = cat_id
        self.storage.set_last_category(cat_id)
        self.show_category(cat_id)

    def show_category(self, cat_id: str, force_refresh: bool = False):
        self.category_bar.set_active_category(cat_id)
        skin_tone = self.storage.get_skin_tone()

        if cat_id == "recent":
            recent_chars = self.storage.get_recent()
            items = []
            for ch in recent_chars:
                emoji_obj = self.db.get_emoji(ch)
                name = emoji_obj.name if emoji_obj else "Emoji"
                if emoji_obj and emoji_obj.char in self.db.skin_tone_emojis and skin_tone:
                    modified = self.db.apply_skin_tone(emoji_obj.char, skin_tone)
                    items.append(EmojiItem(char=modified, name=name, keywords=[], category="recent"))
                else:
                    items.append(EmojiItem(char=ch, name=name, keywords=[], category="recent"))

            self.grid.show_category_items("recent", items, is_kaomoji=False, force_refresh=True)
            self._set_status(f"Recently Used ({len(items)})")

        elif cat_id == "favorites":
            fav_chars = self.storage.get_favorites()
            items = []
            for ch in fav_chars:
                emoji_obj = self.db.get_emoji(ch)
                name = emoji_obj.name if emoji_obj else "Favorite Emoji"
                items.append(EmojiItem(char=ch, name=name, keywords=[], category="favorites"))

            self.grid.show_category_items("favorites", items, is_kaomoji=False, force_refresh=True)
            self._set_status(f"Favorites ({len(items)})")

        elif cat_id == "kaomoji":
            items = self.db.get_category_items("kaomoji")
            self.grid.show_category_items("kaomoji", items, is_kaomoji=True, force_refresh=force_refresh)
            self._set_status(f"Kaomoji ({len(items)})")

        else:
            items = self.db.get_category_items(cat_id, skin_tone=skin_tone)
            cat_title = cat_id.replace("_", " ").title()
            self.grid.show_category_items(cat_id, items, is_kaomoji=False, force_refresh=force_refresh)
            self._set_status(f"{cat_title} ({len(items)})")

    def _set_status(self, text: str):
        self._base_status_text = text
        self.status_label.set_label(text)

    def _on_emoji_hovered(self, item: Optional[EmojiItem]):
        if item:
            self.status_label.set_label(f"{item.char}  {item.name}")
        else:
            self.status_label.set_label(self._base_status_text)

    def _on_emoji_selected(self, emoji_char: str, copy_only: bool = False):
        """
        Handle emoji click.
        Keeps popup open so user can pick multiple emojis!
        Copies current pick/accumulation to clipboard immediately.
        """
        # 1. Update recent history
        self.storage.add_recent(emoji_char)

        # 2. Append to selected buffer
        self._selected_buffer.append(emoji_char)
        accumulated = "".join(self._selected_buffer)

        # 3. Always copy to clipboard immediately so it's ready in Wayland clipboard
        self.insertion.copy_to_clipboard(accumulated)

        # 4. Check user preference: close_on_select (default is False now per user request)
        close_on_select = self.storage.config.get("close_on_select", False)
        if close_on_select:
            self.close_window(paste_pending=True)
            return

        # 5. Keep popup open and update status
        self._set_status(f"Added {accumulated}  (click more or click outside to paste)")

    def close_window(self, paste_pending: bool = True):
        """Close window and optionally paste accumulated emojis into target application."""
        if not self.get_visible() or self._is_dismissing:
            return

        self._is_dismissing = True
        accumulated = "".join(self._selected_buffer)
        self._selected_buffer = []

        # Hide window immediately
        self.set_visible(False)

        # If there are emojis to paste and paste was requested
        if paste_pending and accumulated:
            delay_ms = self.storage.config.get("typing_delay_ms", 60)

            def do_paste():
                # Target window now has focus -> simulate Ctrl+V to paste clean UTF-8 text
                self.insertion.simulate_paste()
                self._is_dismissing = False
                return False

            GLib.timeout_add(delay_ms, do_paste)
        else:
            self._is_dismissing = False

    def present_window(self):
        """Show and focus window when shortcut or command is triggered."""
        self._selected_buffer = []
        self._is_dismissing = False
        self.set_visible(True)
        self.present()
        self.search_entry.set_text("")
        self.search_entry.grab_focus()

        if self._active_category == "recent":
            self.show_category("recent", force_refresh=True)
