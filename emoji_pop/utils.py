"""
Utility functions for COSMIC shortcut registration, RON parsing, and environment verification.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

COSMIC_SHORTCUTS_PATH = Path.home() / ".config" / "cosmic" / "com.system76.CosmicSettings.Shortcuts" / "v1" / "custom"


def inspect_cosmic_shortcut() -> str:
    """Inspect current COSMIC shortcut mapping for Super + period."""
    if not COSMIC_SHORTCUTS_PATH.exists():
        return f"COSMIC shortcuts file not found at {COSMIC_SHORTCUTS_PATH}. You can configure it via COSMIC Settings -> Keyboard -> Customize Shortcuts."

    try:
        content = COSMIC_SHORTCUTS_PATH.read_text(encoding="utf-8")
        if "emoji-pop" in content:
            return "Emoji Pop shortcut is currently REGISTERED in COSMIC custom shortcuts!"
        
        # Check if Super + period is mapped to something else
        match = re.search(r'modifiers:\s*\[\s*Super,\s*\],\s*key:\s*"period",\s*description:\s*Some\("([^"]*)"\),\s*\):\s*Spawn\("([^"]*)"\)', content)
        if match:
            desc, cmd = match.groups()
            return f"Super + . is currently assigned to: {cmd} (Description: {desc}).\nRun 'emoji-pop --register-shortcut' to update it to Emoji Pop."
        return "Super + . is not currently assigned in COSMIC custom shortcuts."
    except Exception as e:
        return f"Error reading COSMIC shortcuts: {e}"


def register_cosmic_shortcut(command: str = "emoji-pop toggle") -> str:
    """Register or update Super + . shortcut in COSMIC custom shortcuts."""
    if not COSMIC_SHORTCUTS_PATH.parent.exists():
        COSMIC_SHORTCUTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    content = ""
    if COSMIC_SHORTCUTS_PATH.exists():
        content = COSMIC_SHORTCUTS_PATH.read_text(encoding="utf-8")
        # Backup
        bak_path = COSMIC_SHORTCUTS_PATH.with_suffix(".bak")
        bak_path.write_text(content, encoding="utf-8")

    # If it already has Super + period mapped
    pattern = re.compile(
        r'\(\s*modifiers:\s*\[\s*Super,\s*\],\s*key:\s*"period",\s*description:\s*Some\([^)]*\),\s*\):\s*Spawn\([^)]*\),?',
        re.MULTILINE
    )

    new_entry = (
        '    (\n'
        '        modifiers: [\n'
        '            Super,\n'
        '        ],\n'
        '        key: "period",\n'
        '        description: Some("Emoji Pop"),\n'
        f'    ): Spawn("{command}"),\n'
    )

    if pattern.search(content):
        # Replace existing mapping
        updated = pattern.sub(new_entry.strip(), content)
    else:
        # Insert inside outer braces
        stripped = content.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            inner = stripped[1:-1].rstrip()
            updated = "{\n" + inner + ("\n" if inner else "") + new_entry + "}\n"
        else:
            updated = "{\n" + new_entry + "}\n"

    try:
        COSMIC_SHORTCUTS_PATH.write_text(updated, encoding="utf-8")
        return f"Successfully registered Super + . -> '{command}' in COSMIC shortcuts! (Backup saved to {COSMIC_SHORTCUTS_PATH.with_suffix('.bak')})"
    except Exception as e:
        return f"Failed to write COSMIC shortcuts: {e}"


def check_environment() -> Dict[str, Any]:
    """Check system compatibility and dependencies."""
    return {
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "Unknown"),
        "session_type": os.environ.get("XDG_SESSION_TYPE", "Unknown"),
        "has_wayland": bool(os.environ.get("WAYLAND_DISPLAY")),
        "wtype": shutil.which("wtype"),
        "wl_copy": shutil.which("wl-copy"),
        "wl_paste": shutil.which("wl-paste"),
    }
