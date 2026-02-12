# Pagergotchi

A port of [Pwnagotchi](https://github.com/jayofelern/pwnagotchi) for the Hak5 WiFi Pineapple Pager.

![Pagergotchi](https://img.shields.io/badge/Hak5-WiFi%20Pineapple%20Pager-green)

![Pagergotchi in action](screenshots/handshake-captured.png)

## Features

- **Automated WiFi Handshake Capture** - PMKID and 4-way handshake attacks via pineapd
- **Cute ASCII Pet** - Personality-driven face that reacts to activity
- **Native Display** - Fast C library rendering via libpagerctl.so (480x222 RGB565)
- **Non-Blocking Pause Menu** - Two-column settings layout with 2D navigation; attacks continue in background
- **Theme System** - 4 visual themes (Default, Cyberpunk, Matrix, Synthwave)
- **Brightness Control** - Adjustable screen brightness (20-100% in 10% steps)
- **Auto-Dim** - Configurable idle timeout (Off/30s/60s) with adjustable dim level (20-60%)
- **Privacy Mode** - Obfuscates MACs, SSIDs, and GPS on display
- **GPS Support** - Optional GPS logging in WiGLE-compatible format
- **Whitelist & Blacklist** - Fine-grained target control with BSSID support
- **WiGLE Integration** - Export captures for WiGLE database uploads
- **App Handoff** - Seamlessly switch to other payloads (e.g., Bjorn) from the pause menu ([details](APP_HANDOFF.md))
- **Self-Contained** - All dependencies bundled, only requires Python3

## Installation

1. Clone or download this repository

2. Copy the `pagergotchi` folder to your Pager's payloads directory:
   ```bash
   scp -r payloads/user/reconnaissance/pagergotchi root@172.16.52.1:/root/payloads/user/reconnaissance/
   ```

3. The payload will appear in the Pager's payload menu under **Reconnaissance > Pagergotchi**

4. On first run, Python3 will be auto-installed if needed (requires internet)

## Payload Launch

When you select Pagergotchi from the payload menu, you'll see the launch screen:

![Payload Launch](screenshots/payload-launch.png)

Press **GREEN** to start or **RED** to exit.

## Startup Menu

The startup menu provides these options:

![Startup Menu](screenshots/mainmenu.png)

- **Start Pagergotchi** - Begin automated operation
- **Deauth Scope** - Configure whitelist/blacklist
- **Privacy** - Toggle display obfuscation (ON/OFF)
- **WiGLE** - Toggle WiGLE CSV logging (ON/OFF)
- **Log APs** - Toggle AP discovery logging (ON/OFF)
- **Clear History** - Reset attack tracking for all networks

![Clear History](screenshots/clear-history.png)

## Main Display

Once started, Pagergotchi shows the main hunting display:

![Startup](screenshots/startup.png)

The display shows:
- Channel and AP count
- Uptime
- Status messages and personality
- ASCII face that reacts to activity
- GPS coordinates (if available)
- PWND count and battery status

| Discovering APs | Client Found |
|-----------------|--------------|
| ![Discover AP](screenshots/discover-ap.png) | ![Client Discovered](screenshots/client-discovered.png) |

| Deauthing | Handshake Captured |
|-----------|-------------------|
| ![Deauthed](screenshots/deauthed.png) | ![Handshake Captured](screenshots/handshake-captured.png) |

## Pause Menu

Press **RED** at any time during operation to open the pause menu. The agent continues capturing handshakes in the background while the menu is displayed.

![Pause Menu](screenshots/pause-menu.png)

The pause menu uses a two-column settings layout with action items below. Use UP/DOWN to navigate rows, LEFT/RIGHT to move between columns, and GREEN to cycle values or select actions.

### Themes

| Theme | Description |
|-------|-------------|
| **Default** | Classic black & white |
| **Cyberpunk** | Cyan and pink neon |
| **Matrix** | Green phosphor terminal |
| **Synthwave** | Purple and pink retro |

| Default | Cyberpunk |
|---------|-----------|
| ![Default Theme](screenshots/themes-default.png) | ![Cyberpunk Theme](screenshots/themes-cyberpunk.png) |

| Matrix | Synthwave |
|--------|-----------|
| ![Matrix Theme](screenshots/themes-matrix.png) | ![Synthwave Theme](screenshots/themes-synthwave.png) |

#### Custom Themes

Create `data/custom_themes.json` to add your own themes with hex color values. Custom themes appear after the built-in themes in the theme cycle. Copy the example to get started:

```bash
cp data/custom_themes.example.json data/custom_themes.json
```

A theme only requires 3 colors — `bg`, `text`, and `face`. All other keys are optional and will derive from these:

```json
{
  "Fire": {
    "bg": "#1a0500",
    "text": "#ff6600",
    "face": "#ff0000"
  }
}
```

For full control, you can specify all 15 keys:

```json
{
  "Ocean": {
    "bg": "#0a1628",
    "text": "#4fc3f7",
    "face": "#00e5ff",
    "label": "#78909c",
    "line": "#1a3a5c",
    "status": "#4fc3f7",
    "menu_title": "#00e5ff",
    "menu_selected": "#4fc3f7",
    "menu_unselected": "#78909c",
    "menu_on": "#00e676",
    "menu_off": "#ff1744",
    "menu_dim": "#37474f",
    "menu_accent": "#ffab40",
    "menu_warning": "#ff6e40",
    "menu_submenu": "#40c4ff"
  }
}
```

| Key | Used for | Default |
|-----|----------|---------|
| **`bg`** | Background color (required) | — |
| **`text`** | Main text color (required) | — |
| **`face`** | ASCII face color (required) | — |
| `label` | Label text | `text` dimmed 60% |
| `line` | Separator lines | `text` dimmed 40% |
| `status` | Status bar text | `text` |
| `menu_title` | Menu title text | `face` |
| `menu_selected` | Highlighted menu item | `text` |
| `menu_unselected` | Non-highlighted menu items | `label` |
| `menu_on` | Toggle ON indicator | `face` |
| `menu_off` | Toggle OFF indicator | `text` dimmed 30% |
| `menu_dim` | Subtle/secondary menu text | `line` |
| `menu_accent` | Accent highlights | `face` |
| `menu_warning` | Warning text | `#ff6400` (orange) |
| `menu_submenu` | Submenu title | `face` |

Multiple themes can be defined in the same file. Invalid entries and malformed JSON are silently ignored. Built-in theme names cannot be overridden. See `data/custom_themes.example.json` for a working example.

### Auto-Dim

When enabled, the screen dims to the configured level after a period of inactivity. Any button press wakes the screen back to full brightness. The first press after dimming only wakes the screen and is not processed as a menu action.

- **Auto Dim timeout**: Off, 30s, or 60s
- **Dim Level**: 20%, 30%, 40%, 50%, or 60% brightness

## Deauth Scope

Control which networks are targeted:

![Deauth Scope Menu](screenshots/deauth-scope.png)

### Whitelist (Do Not Target)
Networks added here will never be attacked. Use for:
- Your home WiFi
- Phone hotspots
- Work networks

![Whitelist Menu](screenshots/whitelist.png)

### Blacklist (Target Only These)
When populated, ONLY these networks will be attacked. Use for:
- Authorized penetration testing
- Specific target assessments

### Adding Networks

| Scan & Add | Manual Add |
|------------|------------|
| ![Scanning APs](screenshots/scanning-aps.png) | ![Manual Add](screenshots/manual-add.png) |

- **Scan & Add** - Scan nearby networks and select from list
- **Manual Add** - Enter SSID or BSSID directly
- **View/Edit** - Remove entries from lists

![Whitelist View](screenshots/whitelist-view.png)

Both SSID and BSSID are stored, so networks are matched even if they hide their SSID.

## Privacy Mode

When enabled, sensitive data is obfuscated on the display:

| Data Type | Example | Obfuscated |
|-----------|---------|------------|
| SSID | `MyNetwork` | `MXXXXXXK` |
| MAC/BSSID | `AA:BB:CC:11:22:33` | `AA:BB:CC:XX:XX:XX` |
| GPS | (any coordinates) | `LAT 38.871 LON -77.055` |

Privacy mode always displays fixed fake coordinates (the Pentagon) regardless of actual GPS location.

## GPS Support

If a USB GPS device is connected, Pagergotchi will:
- Display coordinates on the main screen
- Log GPS data with captured handshakes
- Generate WiGLE-compatible CSV files (if WiGLE enabled)

GPS only appears on display when:
- A GPS device is connected and has a fix, OR
- Privacy mode is enabled (shows fake coordinates)

## Data Storage

### Payload Directory (settings & config)
All settings and configuration stay within the payload directory:

| File | Contents |
|------|----------|
| `config.conf` | User configuration |
| `data/settings.json` | Runtime settings (theme, brightness, privacy, deauth, auto-dim, lists) |
| `data/recovery.json` | Attack history for all networks |
| `data/session.json` | Last session statistics |
| `data/custom_themes.json` | User-defined themes in hex color format (optional) |
| `data/.next_payload` | Temporary file for app handoff (auto-deleted) |

### Loot Directory (captured data)
Captured data goes to the standard Pager loot location:

| Path | Contents |
|------|----------|
| `/root/loot/handshakes/` | Captured .pcap and .22000 files |
| `/root/loot/wigle/` | WiGLE CSV exports |
| `/root/loot/ap_logs/` | AP discovery logs |

## Configuration

Edit `config.conf` for persistent settings:

```ini
[general]
debug = false

[capture]
interface = wlan1mon

[channels]
# Leave empty for all 2.4/5/6GHz bands, or specify: 1,6,11
channels =

[whitelist]
# Use on-screen menu for easier management with BSSID support
ssids =

[deauth]
enabled = true

[timing]
throttle_d = 0.9
throttle_a = 0.4
```

Runtime settings (theme, brightness, privacy, auto-dim, etc.) are saved to `data/settings.json`.

## File Structure

### Repository Layout
```
pagergotchi/
├── README.md                # This file
├── screenshots/             # Documentation images
└── payloads/
    └── user/
        └── reconnaissance/
            └── pagergotchi/     # <- Copy this folder to your Pager
```

### Payload Contents
```
pagergotchi/
├── payload.sh              # Main entry point (service management & handoff loop)
├── run_pagergotchi.py      # Python launcher
├── config.conf             # User configuration
├── launch_pagergotchi.sh   # Direct launcher for handoff from other apps
├── launch_bjorn.sh         # Bjorn launcher (handoff target)
├── data/                   # Runtime data (auto-created)
│   ├── settings.json       # Persistent settings
│   ├── recovery.json       # Attack history
│   ├── custom_themes.json  # User-defined themes (optional)
│   ├── custom_themes.example.json  # Example custom themes
│   └── .next_payload       # Handoff target (temporary)
├── fonts/                  # TTF fonts for display
├── lib/                    # Native libraries & Python packages
│   ├── libpagerctl.so      # Native display/input library
│   └── pagerctl.py         # Python bindings
├── bin/                    # Capture tools
└── pwnagotchi_port/        # Main Python module
    ├── main.py             # Entry point, button monitor thread, main loop
    ├── agent.py            # AI brain & attack logic
    └── ui/
        ├── view.py         # Display rendering, pause menu, auto-dim
        ├── menu.py         # Startup menu, themes, settings persistence
        ├── components.py   # UI elements (Text, LabeledValue, Line)
        └── faces.py        # ASCII face definitions
```

## Technical Details

### Display
- Uses libpagerctl.so for native 480x222 RGB565 rendering
- Double-buffered for flicker-free updates
- TTF font rendering via stb_truetype
- 2 FPS refresh for main display (power saving)
- Partial redraws for pause menu navigation (only changed items are redrawn)

### Input
- Thread-safe event queue for reliable button detection
- 16ms poll interval for responsive input
- Stale event flushing after menu draws to prevent buffered keypress issues
- Non-blocking menu allows background operation
- Debounced input with edge detection

### Attacks
- PMKID capture via association frames
- Deauth for 4-way handshake capture
- Per-AP throttling to avoid detection
- Attack history prevents repeated attempts

### Architecture
- **Button monitor thread** - Polls hardware input at 16ms, handles menu navigation
- **Refresh thread** - Redraws main display at 2 FPS, skips when menu is active
- **Uptime thread** - Updates uptime counter every second
- **Main loop** - Runs recon/attack epochs, checks for exit/menu signals

## Requirements

- Hak5 WiFi Pineapple Pager
- Python3 with ctypes (auto-installed if missing)
- Monitor mode capable WiFi adapter (built-in wlan1)

## Credits

- **Author**: brAinphreAk
- **Website**: [www.brAinphreAk.net](http://www.brainphreak.net)
- **Support**: [ko-fi.com/brainphreak](https://ko-fi.com/brainphreak)
- **Based on**: [Pwnagotchi](https://github.com/evilsocket/pwnagotchi) by evilsocket
- **Hardware**: [Hak5 WiFi Pineapple Pager](https://hak5.org)
- **Display Library**: [pagerctl](https://github.com/pineapple-pager-projects/pineapple_pager_pagerctl)

## License

This project is based on Pwnagotchi which is licensed under GPL-3.0.

## Disclaimer

This tool is intended for authorized security testing and educational purposes only. Only use on networks you own or have explicit permission to test. Unauthorized access to computer networks is illegal.
