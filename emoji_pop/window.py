"""
Main application window for Emoji Pop.
Frameless, translucent floating popup that directly inserts selected emojis
into the active text box with zero intermediate clicks.
"""

import os
from typing import Optional
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from emoji_pop.data import EmojiItem, get_emoji_db
from emoji_pop.storage import get_storage
from emoji_pop.grid import EmojiGrid
from emoji_pop.categories import CategoryBar, SkinToneBar
from emoji_pop.insertion import InsertionBackend
from emoji_pop.focus import CosmicFocusManager


class EmojiPopWindow(Gtk.ApplicationWindow):
    """Frameless translucent floating emoji popup window."""

    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="Emoji Pop")
        self.set_default_size(350, 410)
        self.set_size_request(350, 410)
        self.set_resizable(False)

        # Remove window titlebar & window decorations completely
        self.set_decorated(False)
        self.add_css_class("emoji-pop-window")

        self.storage = get_storage()
        self.db = get_emoji_db()
        self.focus_manager = CosmicFocusManager.get_instance()
        self.insertion = InsertionBackend(
            mode=self.storage.config.get("insertion_mode", "auto"),
            typing_delay_ms=self.storage.config.get("typing_delay_ms", 50),
            restore_clipboard=self.storage.config.get("restore_clipboard", False),
            paste_method=self.storage.config.get("paste_method", "universal"),
        )

        self._active_category = self.storage.get_last_category()
        self._search_timer_id = 0
        self._base_status_text = ""
        self._is_inserting = False
        self._insert_queue = []
        self._user_closed = False
        self._last_insert_time = 0

        # Outer card container
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("emoji-pop-card")
        card.set_size_request(350, 410)

        # 1. Header (Search entry + Circular Skin tone swatches + Close button)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
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
        close_btn.connect("clicked", lambda b: self.dismiss_window())

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

        # Handle window close request (close button '✕' on top titlebar/ribbon)
        self.set_hide_on_close(True)
        self.connect("close-request", self._on_close_request)

        # Enforce fixed floating size: prevent maximizing or docking in COSMIC
        self.connect("notify::maximized", self._on_maximized_changed)

        # Load initial category
        self.show_category(self._active_category)

    def _setup_key_handling(self):
        win_key_ctrl = Gtk.EventControllerKey.new()
        win_key_ctrl.connect("key-pressed", self._on_window_key_pressed)
        self.add_controller(win_key_ctrl)

        search_key_ctrl = Gtk.EventControllerKey.new()
        search_key_ctrl.connect("key-pressed", self._on_search_key_pressed)
        self.search_entry.add_controller(search_key_ctrl)

    def _on_close_request(self, window) -> bool:
        """Handle window close button '✕' on top ribbon."""
        self.dismiss_window()
        return True

    def _on_maximized_changed(self, window, param):
        """Revert maximization immediately to keep compact floating dimensions."""
        if self.is_maximized():
            self.unmaximize()

    def dismiss_window(self):
        """Cleanly dismiss and hide the popup window."""
        self._user_closed = True
        self._is_inserting = False
        self._insert_queue.clear()
        self.set_visible(False)

    def _on_window_key_pressed(self, controller, keyval, keycode, state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.dismiss_window()
            return True
        return False

    def _on_search_key_pressed(self, controller, keyval, keycode, state) -> bool:
        shift_held = bool(state & Gdk.ModifierType.SHIFT_MASK)

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            selected = self.grid.select_first(copy_only=shift_held)
            return selected
        elif keyval == Gdk.KEY_Down:
            return self.grid.focus_first()
        return False

    def _on_window_active_changed(self, window, param):
        """Auto-dismiss when clicking outside the window before any emoji is selected."""
        if self._is_inserting or self._insert_queue or self._user_closed:
            return
        # If user opened the picker but clicked outside without selecting anything, dismiss cleanly
        if not self.is_active() and self.get_visible() and getattr(self, "_last_insert_time", 0) == 0:
            GLib.timeout_add(100, self._handle_outside_click)

    def _handle_outside_click(self) -> bool:
        if self._is_inserting or self._insert_queue or self._user_closed:
            return False
        if not self.is_active() and self.get_visible() and getattr(self, "_last_insert_time", 0) == 0:
            self.dismiss_window()
        return False

    def _on_search_changed(self, entry: Gtk.SearchEntry):
        """Debounced search to ensure snappy typing with zero flicker."""
        if self._search_timer_id:
            GLib.source_remove(self._search_timer_id)
            self._search_timer_id = 0

        self._search_timer_id = GLib.timeout_add(50, self._execute_search)

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
        RAPID DIRECT EMOJI INSERTION WITH QUEUED MULTI-SELECTION:
        1. Save to recent history.
        2. Copy emoji to both standard clipboard and primary selection.
        3. If copy_only, show status and return.
        4. Transfer Wayland focus to target window WITHOUT unmapping or hiding the window.
        5. Insert selected emoji directly without clipboard race conditions or stale caching.
        6. Emoji Pop stays completely still on screen, queueing rapid multi-clicks seamlessly!
        """
        if self._user_closed:
            return

        # 1. Update recent history
        self.storage.add_recent(emoji_char)

        # 2. Always copy to both standard clipboard and primary selection
        self.insertion.copy_to_clipboard(emoji_char)

        # 3. Update footer status label for immediate visual feedback
        emoji_obj = self.db.get_emoji(emoji_char)
        name = emoji_obj.name if emoji_obj else ""
        if copy_only:
            self.status_label.set_label(f"Copied {emoji_char}  {name} to clipboard")
            return

        self.status_label.set_label(f"Inserted {emoji_char}  {name}")

        # If an insertion is currently mid-flight, queue it so rapid clicks are NEVER dropped!
        if self._is_inserting:
            self._insert_queue.append(emoji_char)
            return

        self._process_insertion(emoji_char)

    def _process_insertion(self, emoji_char: str):
        self._is_inserting = True
        self._last_insert_time = GLib.get_monotonic_time()
        close_on_select = self.storage.config.get("close_on_select", False)

        if self.focus_manager.is_available:
            # Native COSMIC: Transfer focus directly to target window without flickering
            self.focus_manager.activate_target()
            target_app = self.focus_manager.get_target_app_id()

            def do_native_insert():
                # Perform UTF-8 clipboard paste (Ctrl+V / Shift+Insert)
                self.insertion.type_or_paste(emoji_char, target_app=target_app)
                if close_on_select:
                    self._is_inserting = False
                    self._insert_queue.clear()
                    self.dismiss_window()
                else:
                    # Insertion finished! Target window remains smoothly focused.
                    # We DO NOT call self.present() — this eliminates 100% of focus
                    # flickering/blinking, prevents browser instability, and leaves
                    # Emoji Pop floating smoothly in front for continuous multi-selection.
                    self._is_inserting = False
                    if self._insert_queue:
                        next_char = self._insert_queue.pop(0)
                        GLib.timeout_add(15, lambda: self._process_insertion(next_char))
                return False

            GLib.timeout_add(25, do_native_insert)

        else:
            # Fallback for non-COSMIC desktop environments where native protocol is unavailable
            delay_ms = self.storage.config.get("typing_delay_ms", 50)
            self.set_visible(False)

            def do_fallback_insert():
                self.insertion.type_or_paste(emoji_char)
                if close_on_select:
                    self._is_inserting = False
                    self._insert_queue.clear()
                else:
                    self._is_inserting = False
                    self.set_visible(True)
                    if self._insert_queue:
                        next_char = self._insert_queue.pop(0)
                        GLib.timeout_add(15, lambda: self._process_insertion(next_char))
                return False

            GLib.timeout_add(delay_ms, do_fallback_insert)

    def present_window(self):
        """Show and focus window when shortcut or command is triggered."""
        self._user_closed = False
        self._is_inserting = False
        self._insert_queue.clear()
        self._last_insert_time = 0

        # Capture target application before Emoji Pop takes focus
        if self.focus_manager.is_available:
            self.focus_manager.capture_target()

        self.set_visible(True)
        self.present()
        self.search_entry.set_text("")
        self.search_entry.grab_focus()

        if self._active_category == "recent":
            self.show_category("recent", force_refresh=True)
