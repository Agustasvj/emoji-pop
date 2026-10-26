"""
COSMIC Wayland Native Focus Manager.
Interacts directly with cosmic-comp's zcosmic_toplevel_info and zcosmic_toplevel_manager
protocols to query active toplevel windows and transfer keyboard focus dynamically
WITHOUT unmapping or hiding the Emoji Pop window.

This eliminates 100% of window flickering and keeps the picker rock-solid still.
"""

import os
import ctypes
import logging
import subprocess
from typing import Optional

logger = logging.getLogger("emoji_pop.focus")


class CosmicFocusManager:
    """Manages Wayland focus transfer for zero-flicker emoji insertion."""

    _instance = None

    def __init__(self):
        self._lib = None
        self._initialized = False
        self._load_library()

    @classmethod
    def get_instance(cls) -> "CosmicFocusManager":
        if cls._instance is None:
            cls._instance = CosmicFocusManager()
        return cls._instance

    def _load_library(self):
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        so_path = os.path.join(pkg_dir, "libcosmic_focus.so")

        # Compile if missing
        if not os.path.exists(so_path):
            self._compile_library(pkg_dir, so_path)

        if os.path.exists(so_path):
            try:
                self._lib = ctypes.CDLL(so_path)
                self._lib.cosmic_tracker_init.restype = ctypes.c_int
                self._lib.cosmic_tracker_refresh.restype = ctypes.c_int
                self._lib.cosmic_tracker_activate_target.restype = ctypes.c_int
                self._lib.cosmic_tracker_get_target_app_id.restype = ctypes.c_char_p

                if self._lib.cosmic_tracker_init():
                    self._initialized = True
                    logger.info("COSMIC native focus manager initialized successfully.")
                else:
                    logger.warning("COSMIC focus manager init failed (not running under COSMIC?)")
            except Exception as e:
                logger.error("Failed to load libcosmic_focus.so: %s", e)
                self._lib = None

    def _compile_library(self, pkg_dir: str, so_path: str):
        native_dir = os.path.join(pkg_dir, "native")
        c_src = os.path.join(native_dir, "cosmic_focus.c")
        if not os.path.exists(c_src):
            return

        cmd = [
            "gcc", "-shared", "-fPIC", "-O2",
            f"-I{native_dir}",
            c_src,
            os.path.join(native_dir, "cosmic-toplevel-info-code.c"),
            os.path.join(native_dir, "cosmic-toplevel-management-code.c"),
            "-lwayland-client",
            "-o", so_path
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0:
                logger.info("Compiled %s successfully.", so_path)
            else:
                logger.warning("Compilation of libcosmic_focus.so failed: %s", res.stderr)
        except Exception as e:
            logger.warning("Failed to invoke gcc: %s", e)

    @property
    def is_available(self) -> bool:
        return self._initialized and self._lib is not None

    def capture_target(self) -> Optional[str]:
        """Capture the currently active target window before presenting Emoji Pop."""
        if not self.is_available:
            return None
        try:
            self._lib.cosmic_tracker_refresh()
            app_id = self._lib.cosmic_tracker_get_target_app_id()
            if app_id:
                app_str = app_id.decode("utf-8", "ignore")
                logger.debug("Captured target window: %s", app_str)
                return app_str
        except Exception as e:
            logger.debug("capture_target error: %s", e)
        return None

    def activate_target(self) -> bool:
        """Transfer Wayland focus to the target window without hiding Emoji Pop."""
        if not self.is_available:
            return False
        try:
            res = self._lib.cosmic_tracker_activate_target()
            return bool(res)
        except Exception as e:
            logger.error("activate_target error: %s", e)
            return False

    def get_target_app_id(self) -> str:
        if not self.is_available:
            return ""
        try:
            app_id = self._lib.cosmic_tracker_get_target_app_id()
            return app_id.decode("utf-8", "ignore") if app_id else ""
        except Exception:
            return ""
