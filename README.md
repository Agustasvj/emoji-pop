# Emoji Pop 🚀

**Emoji Pop** is a fast, lightweight, Windows 11-inspired emoji picker designed natively for **Pop!_OS 24.04 LTS** and the **COSMIC desktop environment** on Wayland.

Inspired by the Windows `Win + .` workflow, Emoji Pop provides instant emoji and kaomoji search, seamless multi-selection, and dependable text insertion into any active application without bloated web runtimes or background polling.

---

## Highlights

- ⚡ **Ultra-Lightweight**: Built with native Python 3, GTK4, and Libadwaita. Consumes **~38 MB RSS** (vs 250MB+ for Electron apps) and **0.0% idle CPU**.
- 🪟 **Windows 11 Interaction Model**: Compact floating popup that stays open while you pick multiple emojis, closing automatically when you click outside or press Escape.
- 🎯 **100% Reliable Insertion**: Uses Wayland clipboard paste simulation (`wl-copy` + `Ctrl+V`) to guarantee that all Unicode sequences (multi-codepoints, skin tones, flags, zero-width joiners, and variation selectors) insert cleanly with zero tofu boxes (`[ ]`).
- 🔍 **Instant, Zero-Flicker Search**: Pre-indexed local database with tokenized CLDR keywords, English aliases, and scoring relevance. Category pages are cached in a `Gtk.Stack` with button recycling for seamless, flicker-free rendering.
- 🎨 **Cosmic & System Theme Matching**: Fully integrates with Pop!_OS dark and light mode via `Adw.StyleManager` and COSMIC theme tokens.
- ⌨️ **Keyboard-First Workflow**: Configurable global shortcut (`Super + .`), arrow-key grid navigation, Enter to insert, and Escape to dismiss.
- 🔒 **Private & Secure**: Operates 100% offline. No background keylogging, no network requests, no elevated root privileges.

---

## Requirements

- **OS**: Pop!_OS 24.04 LTS (or Ubuntu 24.04 with COSMIC desktop)
- **Session**: Wayland
- **Packages**:
  - `python3` (>= 3.10)
  - `python3-gi`, `libgtk-4-1`, `libadwaita-1-0`
  - `wtype` (Wayland virtual keyboard keystroke injector)
  - `wl-clipboard` (`wl-copy` and `wl-paste`)
  - `fonts-noto-color-emoji`

To install missing dependencies:
```bash
sudo apt update
sudo apt install python3 python3-gi libgtk-4-1 libadwaita-1-0 wtype wl-clipboard fonts-noto-color-emoji
```

---

## Installation

### Automatic User Installation (Recommended)

Run the included `install.sh` script (does not require root access):

```bash
git clone https://github.com/Agustasvj/emoji-pop.git
cd emoji-pop
./install.sh
```

The installer will:
1. Compile the native COSMIC zero-flicker focus manager (`libcosmic_focus.so`).
2. Copy the application to `~/.local/share/emoji-pop`.
3. Install the `emoji-pop` launcher into `~/.local/bin`.
4. Install desktop entries and icons into `~/.local/share/applications` and `~/.local/share/icons`.
5. Automatically register `Super + .` in `~/.config/cosmic/com.system76.CosmicSettings.Shortcuts/v1/custom`.

### Uninstallation

```bash
./uninstall.sh
```

---

## Usage

### Global Shortcut

Press **`Super + .`** anytime while typing in any application (e.g., COSMIC Term, Cosmic Edit, Firefox, VS Code, Slack, or Discord).

### Multi-Emoji Picking (Windows 11 Workflow)

1. Press **`Super + .`** to open Emoji Pop.
2. Click any emoji (e.g. 👋) or type to search and click. It is **immediately inserted** into your active text box.
3. The popup **stays open** seamlessly in front so you can keep clicking more emojis (e.g. ✊, 🚀, 🔥).
4. When you are done:
   - **Click back into your document** (or anywhere outside the popup) to dismiss it.
   - OR press **Escape** (or click the **✕** button) to close.

### Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Super + .` | Toggle Emoji Pop window |
| `Down Arrow` (in search) | Focus first emoji in grid |
| `Arrow Keys` | Navigate emoji grid |
| `Enter` | Insert highlighted / top emoji and close |
| `Shift + Enter` | Copy to clipboard only |
| `Escape` | Close picker |
| `Right-Click` | Context menu (Favorite, Copy, Quick Skin Tones) |

---

## CLI Options

```bash
emoji-pop toggle              # Toggle picker visibility (default action)
emoji-pop show                # Show and focus picker
emoji-pop hide                # Hide picker
emoji-pop quit                # Terminate background daemon
emoji-pop --check-shortcut    # Verify COSMIC shortcut status
emoji-pop --register-shortcut # Configure Super+. in COSMIC Settings
emoji-pop --version           # Display version
emoji-pop --help              # Display CLI help
```

---

## Configuration

Preferences are stored in `~/.config/emoji-pop/config.json` adhering to XDG standards:

```json
{
  "shortcut": "Super+period",
  "insertion_mode": "auto",
  "close_on_select": false,
  "skin_tone": "",
  "max_recent": 40,
  "typing_delay_ms": 60,
  "theme": "system"
}
```

- `close_on_select`: Set to `false` (default) to keep the popup open for multi-picking, or `true` to close on the first click.
- `insertion_mode`: `"auto"` (clipboard paste simulation), `"direct"` (raw wtype typing), or `"copy_only"` (clipboard copy only).
- `skin_tone`: Preferred Fitzpatrick modifier (`""` for default, `\U0001F3FB` for light, etc.).

---

## Architecture

```
[Target Application] <--- (Ctrl+V paste) --- [wtype]
         |                                      ^
         | Focus yield                          | Keystroke simulation
         v                                      |
[COSMIC Compositor]                        [Insertion Backend]
         ^                                      ^
         | Super + . toggle                     | Exact UTF-8
         v                                      v
  [emoji-pop CLI] ---> [D-Bus Single Instance: Gtk.Application]
                                |
                    +-----------+-----------+
                    |                       |
               [GTK4 Window]         [Local Data Engine]
              (Adw.StyleManager)      (1,923 Emojis / Token Index)
                    |                       |
               [Gtk.Stack]             [XDG Storage]
           (Zero-flicker cache)     (History & Favorites)
```

### Why It Is Lightweight

1. **Native GTK4 & Libadwaita**: Zero web browser overhead. Python + PyGObject provides instant access to native C libraries without compiling heavyweight daemons.
2. **Zero Polling**: Does not run active loops or capture arbitrary global keys. Operates strictly via compositor-triggered commands. When hidden, the process sleeps in `epoll_wait` consuming 0.0% CPU.
3. **Stacked Category Virtualization**: Instead of rebuilding dozens of GTK widgets whenever categories or searches change, category pages are cached in a `Gtk.Stack` and search buttons are recycled in-place.
4. **Compressed Local Metadata**: Unicode dataset is stored locally in a 34 KB gzipped bundle, loading in under 38 ms.

---

## Performance Benchmarks

Measured on Pop!_OS 24.04 LTS (Kernel 7.1, x86-64 Wayland):

| Metric | Result |
| :--- | :--- |
| **Cold Startup Time** | ~180 ms |
| **Warm Invocation Latency** | **18 ms** |
| **Idle Resident Memory (RSS)** | **37.7 MB** |
| **Peak Resident Memory** | **44.2 MB** |
| **Idle CPU Consumption** | **0.00%** |
| **Average Search Latency** | **11.2 ms** (across 1,923 emojis) |
| **Stress Test (30 rapid toggles)** | **0 errors, 100% stability** |

---

## License

MIT License. Designed with ❤️ for Pop!_OS and the COSMIC desktop environment.
