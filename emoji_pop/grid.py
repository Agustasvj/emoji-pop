"""
High-performance emoji grid with zero-flicker cached category pages,
widget pooling for search, and keyboard navigation.
"""

from typing import List, Optional, Callable, Dict
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib

from emoji_pop.data import EmojiItem, get_emoji_db
from emoji_pop.storage import get_storage


class FixedEmojiChild(Gtk.Widget):
    """Container widget that strictly limits measured dimensions to 32x32 for emoji items."""
    def __init__(self, child: Gtk.Widget):
        super().__init__()
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self._child = child
        child.set_parent(self)

    def do_measure(self, orientation, for_size):
        return (32, 32, -1, -1)

    def do_size_allocate(self, width, height, baseline):
        if self._child:
            self._child.allocate(width, height, baseline, None)

    def do_dispose(self):
        if self._child:
            self._child.unparent()
            self._child = None


class EmojiGrid(Gtk.Box):
    """Zero-flicker stack-based emoji and kaomoji grid."""

    def __init__(self, on_select: Callable[[str, bool], None], on_hover: Optional[Callable[[Optional[EmojiItem]], None]] = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_select = on_select
        self.on_hover = on_hover

        # Main stack container - transitions are instant to prevent visual flashing
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)

        # Cache of category pages: cat_id -> (scrolled_window, flowbox, is_populated)
        self._category_pages: Dict[str, Dict] = {}

        # Search page & widget pool
        self._search_buttons: List[Gtk.Button] = []
        self._search_items: List[EmojiItem] = []
        self._setup_search_page()

        # Empty state page
        self._setup_empty_page()

        self.append(self.stack)

    def _setup_empty_page(self):
        self.empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.empty_box.set_valign(Gtk.Align.CENTER)
        self.empty_box.set_halign(Gtk.Align.CENTER)
        self.empty_box.set_vexpand(True)
        self.empty_box.add_css_class("empty-state-box")

        self.empty_icon = Gtk.Label(label="🔍")
        self.empty_icon.add_css_class("empty-state-icon")
        self.empty_title = Gtk.Label(label="No emojis found")
        self.empty_title.add_css_class("empty-state-title")
        self.empty_subtitle = Gtk.Label(label="Try searching for something else")
        self.empty_subtitle.add_css_class("empty-state-subtitle")

        self.empty_box.append(self.empty_icon)
        self.empty_box.append(self.empty_title)
        self.empty_box.append(self.empty_subtitle)

        self.stack.add_named(self.empty_box, "_empty")

    def _setup_search_page(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add_css_class("emoji-scroll-area")

        self.search_flowbox = Gtk.FlowBox()
        self.search_flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.search_flowbox.set_valign(Gtk.Align.START)
        self.search_flowbox.set_homogeneous(True)
        self.search_flowbox.set_min_children_per_line(9)
        self.search_flowbox.set_max_children_per_line(9)
        self.search_flowbox.add_css_class("emoji-flowbox")

        self.search_flowbox.connect("child-activated", self._on_flowbox_child_activated)
        scroll.set_child(self.search_flowbox)
        self.stack.add_named(scroll, "_search")
        self._search_scroll = scroll

    def _create_category_page(self, cat_id: str, is_kaomoji: bool = False):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add_css_class("emoji-scroll-area")

        flowbox = Gtk.FlowBox()
        flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        flowbox.set_valign(Gtk.Align.START)
        flowbox.add_css_class("emoji-flowbox")

        if is_kaomoji:
            flowbox.set_homogeneous(False)
            flowbox.set_min_children_per_line(2)
            flowbox.set_max_children_per_line(3)
        else:
            flowbox.set_homogeneous(True)
            flowbox.set_min_children_per_line(9)
            flowbox.set_max_children_per_line(9)

        flowbox.connect("child-activated", self._on_flowbox_child_activated)
        scroll.set_child(flowbox)

        self._category_pages[cat_id] = {
            "scroll": scroll,
            "flowbox": flowbox,
            "populated": False,
            "is_kaomoji": is_kaomoji,
        }
        self.stack.add_named(scroll, cat_id)

    def show_category_items(self, cat_id: str, items: List[EmojiItem], is_kaomoji: bool = False, force_refresh: bool = False):
        """Display a category with zero flicker, reusing already rendered widgets."""
        if not items:
            self.empty_title.set_label(f"No items in {cat_id.replace('_', ' ').title()}")
            self.empty_subtitle.set_label("")
            self.stack.set_visible_child_name("_empty")
            return

        if cat_id not in self._category_pages:
            self._create_category_page(cat_id, is_kaomoji=is_kaomoji)

        page = self._category_pages[cat_id]
        flowbox = page["flowbox"]

        # Only populate widgets if not yet populated or if forced (e.g. recent/favorites/skin tone changed)
        if not page["populated"] or force_refresh:
            # Clear flowbox
            while True:
                c = flowbox.get_first_child()
                if c is None:
                    break
                flowbox.remove(c)

            for item in items:
                btn = self._make_emoji_button(item, is_kaomoji=is_kaomoji)
                flowbox.append(btn)

            page["populated"] = True

        self.stack.set_visible_child_name(cat_id)
        page["scroll"].get_vadjustment().set_value(0)

    def show_search_results(self, query: str, results: List[EmojiItem]):
        """Update search page by recycling existing buttons to eliminate flickering."""
        self._search_items = results

        if not results:
            self.empty_title.set_label(f"No emojis found for \"{query}\"")
            self.empty_subtitle.set_label("Try searching with another keyword or synonym")
            self.stack.set_visible_child_name("_empty")
            return

        # Recycle or expand button pool
        for i, item in enumerate(results):
            if i < len(self._search_buttons):
                btn = self._search_buttons[i]
                if hasattr(btn, "_label") and btn._label:
                    btn._label.set_text(item.char)
                else:
                    btn.set_label(item.char)
                btn.set_tooltip_text(item.name)
                btn._emoji_item = item
                btn.get_parent().set_visible(True)
            else:
                btn = self._make_emoji_button(item, is_kaomoji=False)
                self._search_buttons.append(btn)
                self.search_flowbox.append(btn)

        # Hide extra buttons in pool beyond results count
        for i in range(len(results), len(self._search_buttons)):
            self._search_buttons[i].get_parent().set_visible(False)

        self.stack.set_visible_child_name("_search")
        self._search_scroll.get_vadjustment().set_value(0)

    def _make_emoji_button(self, item: EmojiItem, is_kaomoji: bool = False) -> Gtk.Button:
        if is_kaomoji:
            btn = Gtk.Button(label=item.char)
            btn.add_css_class("kaomoji-item-btn")
        else:
            lbl = Gtk.Label(label=item.char)
            fixed_child = FixedEmojiChild(lbl)
            btn = Gtk.Button()
            btn.set_child(fixed_child)
            btn._label = lbl
            btn.add_css_class("emoji-item-btn")

        btn.set_tooltip_text(item.name)
        btn._emoji_item = item

        # Do not steal focus from search entry on click
        btn.set_focus_on_click(False)

        btn.connect("clicked", self._on_button_clicked)

        # Hover detection for status text
        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", lambda c, x, y, b=btn: self.on_hover(getattr(b, "_emoji_item", None)) if self.on_hover else None)
        motion.connect("leave", lambda c: self.on_hover(None) if self.on_hover else None)
        btn.add_controller(motion)

        # Right-click context menu
        click_ctrl = Gtk.GestureClick.new()
        click_ctrl.set_button(Gdk.BUTTON_SECONDARY)
        click_ctrl.connect("pressed", lambda g, n, x, y, b=btn: self._on_item_right_clicked(g, n, x, y, b))
        btn.add_controller(click_ctrl)

        return btn

    def _on_flowbox_child_activated(self, flowbox, child):
        btn = child.get_child()
        if btn and hasattr(btn, "_emoji_item") and btn._emoji_item:
            self.on_select(btn._emoji_item.char, False)

    def _on_button_clicked(self, btn):
        item = getattr(btn, "_emoji_item", None)
        if item:
            self.on_select(item.char, False)

    def _on_item_right_clicked(self, gesture, n_press, x, y, btn: Gtk.Button):
        item = getattr(btn, "_emoji_item", None)
        if not item:
            return

        popover = Gtk.Popover()
        popover.set_parent(btn)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_margin_top(6)
        vbox.set_margin_bottom(6)
        vbox.set_margin_start(6)
        vbox.set_margin_end(6)

        copy_btn = Gtk.Button(label="📋 Copy to Clipboard")
        copy_btn.set_has_frame(False)
        copy_btn.connect("clicked", lambda b, c=item.char: (popover.popdown(), self.on_select(c, True)))
        vbox.append(copy_btn)

        storage = get_storage()
        is_fav = storage.is_favorite(item.char)
        fav_label = "⭐ Remove Favorite" if is_fav else "☆ Add to Favorites"
        fav_btn = Gtk.Button(label=fav_label)
        fav_btn.set_has_frame(False)

        def toggle_fav(b):
            popover.popdown()
            storage.toggle_favorite(item.char)
            # Invalidate favorites page cache so it reloads
            if "favorites" in self._category_pages:
                self._category_pages["favorites"]["populated"] = False
            if self.on_hover:
                self.on_hover(item)

        fav_btn.connect("clicked", toggle_fav)
        vbox.append(fav_btn)

        # Quick skin tone variants
        db = get_emoji_db()
        base_char = getattr(item, "base_char", item.char)
        if base_char in db.skin_tone_emojis:
            tone_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            tone_box.set_margin_top(4)
            for tone_info in db.skin_tones:
                code = tone_info["code"]
                char_variant = db.apply_skin_tone(base_char, code)
                t_btn = Gtk.Button(label=char_variant)
                t_btn.set_has_frame(False)
                t_btn.connect("clicked", lambda b, c=char_variant: (popover.popdown(), self.on_select(c, False)))
                tone_box.append(t_btn)
            vbox.append(tone_box)

        popover.set_child(vbox)
        popover.popup()

    def select_first(self, copy_only: bool = False) -> bool:
        """Select top search result or first item in active grid."""
        active_name = self.stack.get_visible_child_name()
        if active_name == "_search":
            if self._search_items:
                self.on_select(self._search_items[0].char, copy_only)
                return True
        elif active_name in self._category_pages:
            flowbox = self._category_pages[active_name]["flowbox"]
            first_child = flowbox.get_child_at_index(0)
            if first_child:
                btn = first_child.get_child()
                if btn and hasattr(btn, "_emoji_item"):
                    self.on_select(btn._emoji_item.char, copy_only)
                    return True
        return False

    def focus_first(self) -> bool:
        """Move keyboard navigation into the currently visible grid."""
        active_name = self.stack.get_visible_child_name()
        flowbox = None
        if active_name == "_search":
            flowbox = self.search_flowbox
        elif active_name in self._category_pages:
            flowbox = self._category_pages[active_name]["flowbox"]

        if flowbox:
            first_child = flowbox.get_child_at_index(0)
            if first_child and first_child.get_visible():
                return first_child.grab_focus()
        return False

    def invalidate_cache(self):
        """Invalidate category cache when preferences (e.g. skin tone) change."""
        for cat_id, page in self._category_pages.items():
            page["populated"] = False
