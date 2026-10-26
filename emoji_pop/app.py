"""
Application lifecycle, single-instance D-Bus management, and CLI handling.
"""

import sys
import argparse
import logging
from pathlib import Path
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, GLib, Adw

from emoji_pop import __version__
from emoji_pop.window import EmojiPopWindow
from emoji_pop.storage import get_storage
from emoji_pop.utils import register_cosmic_shortcut, inspect_cosmic_shortcut

logger = logging.getLogger("emoji_pop.app")

STYLE_PATH = Path(__file__).resolve().parent / "assets" / "style.css"


class EmojiPopApplication(Adw.Application):
    """Single-instance GTK4 / Libadwaita application for Emoji Pop."""

    def __init__(self):
        super().__init__(
            application_id="com.pop_os.EmojiPop",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.window: EmojiPopWindow = None
        self._held = False

    def do_startup(self):
        Adw.Application.do_startup(self)

        # Load CSS provider
        if STYLE_PATH.exists():
            provider = Gtk.CssProvider()
            provider.load_from_path(str(STYLE_PATH))
            from gi.repository import Gdk
            gdk_display = Gdk.Display.get_default()
            if gdk_display:
                Gtk.StyleContext.add_provider_for_display(
                    gdk_display,
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )

        # Setup style manager (Dark / Light mode tracking)
        style_mgr = Adw.StyleManager.get_default()
        storage = get_storage()
        theme_pref = storage.config.get("theme", "system")
        if theme_pref == "dark":
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif theme_pref == "light":
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)

        # Build window
        self.window = EmojiPopWindow(self)

    def do_activate(self):
        self._ensure_hold()
        self._toggle_window()

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        args = command_line.get_arguments()
        subcmd = args[1] if len(args) > 1 else "toggle"

        if subcmd == "quit":
            if self._held:
                self.release()
                self._held = False
            self.quit()
            return 0

        self._ensure_hold()

        if subcmd == "hide":
            if self.window and self.window.get_visible():
                self.window.set_visible(False)
            return 0

        if subcmd == "show":
            if self.window:
                self.window.present_window()
            return 0

        # Default: toggle
        self._toggle_window()
        return 0

    def _ensure_hold(self):
        if not self._held:
            self.hold()
            self._held = True

    def _toggle_window(self):
        if not self.window:
            return
        if self.window.get_visible():
            self.window.set_visible(False)
        else:
            self.window.present_window()


def print_help():
    print(
        "Usage: emoji-pop [command|options]\n\n"
        "Commands:\n"
        "  toggle              Toggle picker visibility (default)\n"
        "  show                Show and focus picker\n"
        "  hide                Hide picker\n"
        "  quit                Terminate background daemon\n\n"
        "Options:\n"
        "  --register-shortcut Register Super+. shortcut in COSMIC\n"
        "  --check-shortcut    Inspect current COSMIC shortcut status\n"
        "  --version, -v       Show application version\n"
        "  --help, -h          Show this help message"
    )


def main():
    # Handle pure CLI arguments without starting GTK GUI
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("--help", "-h"):
            print_help()
            sys.exit(0)
        elif arg in ("--version", "-v"):
            print(f"Emoji Pop v{__version__}")
            sys.exit(0)
        elif arg == "--register-shortcut":
            msg = register_cosmic_shortcut()
            print(msg)
            sys.exit(0)
        elif arg == "--check-shortcut":
            msg = inspect_cosmic_shortcut()
            print(msg)
            sys.exit(0)

    app = EmojiPopApplication()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == "__main__":
    main()
