#!/usr/bin/env bash
# ==============================================================================
# Emoji Pop — Installer for Pop!_OS 24.04 & COSMIC Desktop
# Can be run without root privileges (installs to ~/.local)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
PKG_DIR="${HOME}/.local/share/emoji-pop"

echo "=========================================================="
echo "  Installing Emoji Pop for Pop!_OS / COSMIC Wayland"
echo "=========================================================="

# 1. Check system requirements
echo "Checking requirements..."
command -v python3 >/dev/null 2>&1 || { echo "Error: python3 is not installed."; exit 1; }
python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')" >/dev/null 2>&1 || {
    echo "Warning: PyGObject with GTK4 / Libadwaita was not detected."
    echo "Please ensure packages 'python3-gi', 'libgtk-4-1', and 'libadwaita-1-0' are installed."
}

if ! command -v wtype >/dev/null 2>&1; then
    echo "Notice: 'wtype' was not found in PATH."
    echo "Automatic typing requires wtype. You can install it via: sudo apt install wtype"
fi

if ! command -v wl-copy >/dev/null 2>&1; then
    echo "Notice: 'wl-copy' was not found in PATH."
    echo "Clipboard integration requires wl-clipboard. You can install it via: sudo apt install wl-clipboard"
fi

# 2. Build emoji dataset if missing
if [ ! -f "${SCRIPT_DIR}/emoji_pop/assets/emoji_data.json.gz" ]; then
    echo "Generating emoji dataset bundle..."
    python3 "${SCRIPT_DIR}/scripts/build_data.py"
fi

# 2b. Build native COSMIC focus helper
if command -v gcc >/dev/null 2>&1; then
    echo "Compiling native COSMIC zero-flicker focus manager..."
    gcc -shared -fPIC -O2 \
        -I"${SCRIPT_DIR}/emoji_pop/native" \
        "${SCRIPT_DIR}/emoji_pop/native/cosmic_focus.c" \
        "${SCRIPT_DIR}/emoji_pop/native/cosmic-toplevel-info-code.c" \
        "${SCRIPT_DIR}/emoji_pop/native/cosmic-toplevel-management-code.c" \
        -lwayland-client \
        -o "${SCRIPT_DIR}/emoji_pop/libcosmic_focus.so" || true
fi

# 3. Create destination directories
mkdir -p "${BIN_DIR}" "${APP_DIR}" "${ICON_DIR}" "${PKG_DIR}"

# 4. Copy package contents
echo "Installing application files to ${PKG_DIR}..."
cp -r "${SCRIPT_DIR}/emoji_pop" "${PKG_DIR}/"

# 5. Install launcher script
echo "Installing launcher to ${BIN_DIR}/emoji-pop..."
cat << 'EOF' > "${BIN_DIR}/emoji-pop"
#!/usr/bin/env python3
import sys
from pathlib import Path

pkg_root = Path.home() / ".local" / "share" / "emoji-pop"
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from emoji_pop.app import main

if __name__ == "__main__":
    main()
EOF
chmod +x "${BIN_DIR}/emoji-pop"

# 6. Install desktop file and icon
echo "Installing desktop entry and icon..."
cp "${SCRIPT_DIR}/data/com.pop_os.EmojiPop.desktop" "${APP_DIR}/"
cp "${SCRIPT_DIR}/data/com.pop_os.EmojiPop.svg" "${ICON_DIR}/"

# Update caches if utilities are available
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

# 7. Configure COSMIC Shortcut
echo ""
echo "Configuring COSMIC keyboard shortcut..."
"${BIN_DIR}/emoji-pop" --register-shortcut || true

echo ""
echo "=========================================================="
echo "  Emoji Pop has been successfully installed!"
echo "=========================================================="
echo "  Binary:   ${BIN_DIR}/emoji-pop"
echo "  Shortcut: Super + . (configured in COSMIC Settings)"
echo ""
echo "  Usage:"
echo "    emoji-pop toggle     (Toggle visibility)"
echo "    emoji-pop --help     (Show CLI options)"
echo ""
echo "  Ensure '${BIN_DIR}' is in your PATH."
echo "=========================================================="
