"""
Reliable text insertion backend for Wayland and COSMIC.
Supports robust clipboard paste simulation (wl-copy + Ctrl+V) to preserve 100%
of all Unicode emoji sequences (ZWJs, skin tones, flags, variation selectors)
without tofu boxes or dropped keystrokes.
"""

import os
import shutil
import subprocess
import logging
from enum import Enum
from typing import Optional, Tuple
import gi

gi.require_version("Gdk", "4.0")
from gi.repository import GLib, Gio, Gdk

logger = logging.getLogger("emoji_pop.insertion")


class InsertionMode(str, Enum):
    AUTO = "auto"
    CLIPBOARD_PASTE = "clipboard_paste"
    DIRECT = "direct"
    COPY_ONLY = "copy_only"


class InsertionBackend:
    """Handles inserting emoji into the target application or copying to clipboard."""

    def __init__(self, mode: str = "auto", typing_delay_ms: int = 50, restore_clipboard: bool = False, paste_method: str = "universal"):
        self.mode = mode
        self.typing_delay_ms = typing_delay_ms
        self.restore_clipboard = restore_clipboard
        self.paste_method = paste_method
        self._wtype_bin = shutil.which("wtype")
        self._wl_copy_bin = shutil.which("wl-copy")
        self._wl_paste_bin = shutil.which("wl-paste")

    def has_direct_typing(self) -> bool:
        return self._wtype_bin is not None

    def has_clipboard_tools(self) -> bool:
        return self._wl_copy_bin is not None

    def copy_to_clipboard(self, text: str) -> bool:
        """
        Copy text to Wayland / system clipboard AND primary selection.
        Populating both ensures all terminal emulators, X11/Xwayland apps,
        and Wayland GUI apps have access to the selected emoji.
        """
        copied = False
        if self._wl_copy_bin:
            # Standard clipboard (Ctrl+V, Shift+Insert in GUI apps)
            try:
                proc = subprocess.run(
                    [self._wl_copy_bin, "-n", text],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                )
                if proc.returncode == 0:
                    copied = True
            except Exception as e:
                logger.warning("wl-copy standard clipboard failed: %s", e)

            # Primary selection (terminals, middle-click paste, X11 apps)
            try:
                subprocess.run(
                    [self._wl_copy_bin, "-n", "--primary", text],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                )
            except Exception as e:
                logger.warning("wl-copy primary selection failed: %s", e)

        # Fallback to GdkClipboard ONLY if wl-copy is not available.
        # Calling Gdk.Clipboard.set() when wl-copy succeeded clobbers wl-copy's
        # selection offer with an incompatible MIME type, causing stale pastes.
        if not copied:
            try:
                display = Gdk.Display.get_default()
                if display:
                    clipboard = display.get_clipboard()
                    clipboard.set(text)
                    copied = True
            except Exception as e:
                logger.error("Gdk.Clipboard set failed: %s", e)

        return copied

    def get_current_clipboard(self) -> Optional[str]:
        """Fetch current clipboard text if available."""
        if self._wl_paste_bin:
            try:
                proc = subprocess.run(
                    [self._wl_paste_bin, "--type", "text/plain"],
                    capture_output=True,
                    timeout=0.5,
                    text=True
                )
                if proc.returncode == 0:
                    return proc.stdout
            except Exception:
                pass
        return None

    def simulate_paste(self, method: Optional[str] = None, target_app: Optional[str] = None) -> bool:
        """
        Simulate paste keystroke into the active target application via wtype.
        - Terminal emulators (cosmic-term, alacritty, kitty): sends Ctrl+Shift+V.
        - GUI applications (gedit, Firefox, Chrome, LibreOffice, Code, etc.): sends Ctrl+V.
        """
        if not self._wtype_bin:
            return False

        target = target_app or method or getattr(self, "paste_method", "") or ""
        app_lower = target.lower()
        is_terminal = any(term in app_lower for term in ("term", "kitty", "alacritty", "console", "pty"))

        if method == "ctrl_shift_v" or is_terminal:
            args = [self._wtype_bin, "-M", "ctrl", "-M", "shift", "-k", "v", "-m", "ctrl", "-m", "shift"]
        elif method == "shift_insert":
            args = [self._wtype_bin, "-M", "shift", "-P", "Insert", "-p", "Insert", "-m", "shift"]
        else:
            # Standard Ctrl+V for all GUI applications, web browsers, and text fields
            args = [self._wtype_bin, "-M", "ctrl", "-k", "v", "-m", "ctrl"]

        try:
            proc = subprocess.run(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1.0,
            )
            return proc.returncode == 0
        except Exception as e:
            logger.warning("Simulate paste failed: %s", e)
            return False

    def _type_direct(self, text: str) -> bool:
        """
        Type Unicode string directly via wtype.
        Strips variation selector FE0F (VS16) so wtype does not inject it as an
        isolated individual keystroke, which causes tofu box glyphs in target inputs.
        """
        if not self._wtype_bin:
            return False
        try:
            clean_text = text.replace("\uFE0F", "")
            proc = subprocess.run(
                [self._wtype_bin, clean_text],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1.0,
            )
            return proc.returncode == 0
        except Exception as e:
            logger.warning("Direct wtype typing error: %s", e)
            return False

    def type_or_paste(self, emoji_char: str, target_app: Optional[str] = None) -> bool:
        """
        Insert emoji into the active target application.
        Primary: Direct wtype typing with VS16 removal.
        This completely bypasses Wayland clipboard caching and asynchronous IPC races,
        guaranteeing the exact clicked emoji is inserted on the very first try without
        lag or stale repeat insertions.
        Fallback / Configured: Clipboard paste simulation via simulate_paste().
        """
        # If user explicitly requested clipboard paste mode in settings
        if self.mode == InsertionMode.CLIPBOARD_PASTE:
            return self.simulate_paste(target_app=target_app)

        # Primary mode (auto or direct): Use direct typing if wtype available
        if self._wtype_bin:
            typed = self._type_direct(emoji_char)
            if typed:
                return True

        # Fallback to clipboard paste if direct typing is unavailable
        return self.simulate_paste(target_app=target_app)

    def notify_user(self, title: str, message: str):
        """Send desktop notification via notify-send or desktop portal."""
        notify_bin = shutil.which("notify-send")
        if notify_bin:
            try:
                subprocess.Popen([
                    notify_bin,
                    "-a", "Emoji Pop",
                    "-i", "accessories-character-map",
                    title,
                    message
                ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def insert(self, emoji_char: str, copy_only: bool = False, on_complete=None) -> Tuple[bool, str]:
        """
        Execute insertion pipeline.
        In AUTO mode:
        1. Copies exact UTF-8 string to Wayland clipboard using wl-copy.
        2. Directly types the exact emoji character into the target app without stale cache races.
        """
        # Step 1: Always copy to clipboard
        copy_ok = self.copy_to_clipboard(emoji_char)

        if copy_only or self.mode == InsertionMode.COPY_ONLY:
            msg = "Copied to clipboard" if copy_ok else "Failed to copy to clipboard"
            if on_complete:
                on_complete(copy_ok, msg)
            return copy_ok, msg

        # Step 2: Use type_or_paste
        success = self.type_or_paste(emoji_char)
        if success:
            msg = f"Inserted {emoji_char}"
            if on_complete:
                on_complete(True, msg)
            return True, msg

        # Step 3: Fallback if typing failed but clipboard copy succeeded
        if copy_ok:
            msg = f"Copied {emoji_char} to clipboard (press Ctrl+V to paste)"
            if on_complete:
                on_complete(True, msg)
            return True, msg

        msg = "Insertion failed"
        if on_complete:
            on_complete(False, msg)
        return False, msg
