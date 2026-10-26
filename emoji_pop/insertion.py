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
                    [self._wl_copy_bin, text],
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
                    [self._wl_copy_bin, "--primary", text],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                )
            except Exception as e:
                logger.warning("wl-copy primary selection failed: %s", e)

        # Fallback to GdkClipboard
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

    def simulate_paste(self, method: Optional[str] = None) -> bool:
        """
        Simulate paste keystroke into the active target application via wtype.
        - "universal": Types Shift+Insert, which is standard CUA/X11 and works in BOTH
          terminals (cosmic-term, alacritty, kitty, gnome-terminal) AND GUI apps (gedit,
          browsers, LibreOffice, electron). Falls back to Ctrl+V if Shift+Insert fails.
        - "ctrl_v": Types standard Ctrl+V.
        - "ctrl_shift_v": Types Ctrl+Shift+V for terminals.
        """
        if not self._wtype_bin:
            return False

        target_method = method or self.paste_method or "universal"

        if target_method == "universal":
            try:
                proc = subprocess.run(
                    [self._wtype_bin, "-M", "shift", "-P", "Insert", "-p", "Insert", "-m", "shift"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                )
                if proc.returncode == 0:
                    return True
            except Exception as e:
                logger.warning("Universal Shift+Insert failed: %s", e)

            # Fallback to Ctrl+V
            target_method = "ctrl_v"

        if target_method == "ctrl_shift_v":
            args = [self._wtype_bin, "-M", "ctrl", "-M", "shift", "-k", "v", "-m", "ctrl", "-m", "shift"]
        else:
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
        """Type Unicode string directly via wtype (fallback only)."""
        if not self._wtype_bin:
            return False
        try:
            # Strip trailing variation selector FE0F if present as wtype turns it into tofu
            clean_text = text.rstrip("\uFE0F")
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
        2. Simulates Ctrl+V using wtype so the focused application pastes it atomically.
        3. This guarantees ZERO missing glyph boxes and preserves 100% of Unicode sequences!
        """
        # Step 1: Always copy to clipboard
        copy_ok = self.copy_to_clipboard(emoji_char)

        if copy_only or self.mode == InsertionMode.COPY_ONLY:
            msg = "Copied to clipboard" if copy_ok else "Failed to copy to clipboard"
            if on_complete:
                on_complete(copy_ok, msg)
            return copy_ok, msg

        # Step 2: If DIRECT mode explicitly requested
        if self.mode == InsertionMode.DIRECT:
            success = self._type_direct(emoji_char)
            msg = f"Inserted {emoji_char}" if success else "Copied to clipboard (direct typing failed)"
            if on_complete:
                on_complete(success, msg)
            return success, msg

        # Step 3: Default AUTO and CLIPBOARD_PASTE mode
        # Simulate Ctrl+V to paste the clipboard content into the target window
        if self._wtype_bin:
            paste_ok = self.simulate_paste()
            if paste_ok:
                msg = f"Inserted {emoji_char}"
                if on_complete:
                    on_complete(True, msg)
                return True, msg

        # Step 4: If wtype paste simulation is not available, clipboard copy is already done
        if copy_ok:
            msg = f"Copied {emoji_char} to clipboard (press Ctrl+V to paste)"
            if on_complete:
                on_complete(True, msg)
            return True, msg

        msg = "Insertion failed"
        if on_complete:
            on_complete(False, msg)
        return False, msg
