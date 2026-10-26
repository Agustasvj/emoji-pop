#!/usr/bin/env bash
# ==============================================================================
# Emoji Pop — Uninstaller
# ==============================================================================

set -e

BIN_FILE="${HOME}/.local/bin/emoji-pop"
APP_FILE="${HOME}/.local/share/applications/com.pop_os.EmojiPop.desktop"
ICON_FILE="${HOME}/.local/share/icons/hicolor/scalable/apps/com.pop_os.EmojiPop.svg"
PKG_DIR="${HOME}/.local/share/emoji-pop"
CONFIG_DIR="${HOME}/.config/emoji-pop"

echo "Uninstalling Emoji Pop..."

# 1. Stop daemon if running
if [ -x "${BIN_FILE}" ]; then
    "${BIN_FILE}" quit >/dev/null 2>&1 || true
fi

# 2. Remove files
rm -f "${BIN_FILE}"
rm -f "${APP_FILE}"
rm -f "${ICON_FILE}"
rm -rf "${PKG_DIR}"

# Update desktop and icon databases
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${HOME}/.local/share/applications" >/dev/null 2>&1 || true
fi

echo "Emoji Pop has been uninstalled."
echo "Note: Configuration in ${CONFIG_DIR} was preserved. Remove manually if desired:"
echo "  rm -rf ${CONFIG_DIR}"
