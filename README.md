# Pagergotchi

A port of [Pwnagotchi](https://github.com/jayofelern/pwnagotchi) for the Hak5 WiFi Pineapple Pager.

![Pagergotchi](https://img.shields.io/badge/Hak5-WiFi%20Pineapple%20Pager-green)

## Features

- **Automated WiFi Handshake Capture** - PMKID and 4-way handshake attacks
- **Cute ASCII Pet** - Personality-driven face that reacts to activity
- **Native Display** - Fast C library rendering (not PIL - runs smoothly on Pager)
- **GPS Support** - Optional GPS logging in WiGLE-compatible format
- **Whitelist Protection** - Protect your own networks from attacks
- **Self-Contained** - All dependencies bundled, only requires Python3

## Installation

1. Copy the `pagergotchi` folder to your Pager's payloads directory:
   ```
   scp -r user root@172.16.52.1:/root/payloads/user/
   ```

2. The payload will appear in the Pager's payload menu under Reconnaissance.

3. On first run, if Python3 is not installed, you'll be prompted to install it.

## Configuration

Edit `config.conf` to customize:

- **Whitelist** - Networks to never attack (your home WiFi, phone hotspot, etc.)
- **Channels** - Which WiFi channels to scan
- **Personality** - How aggressive the attacks should be
- **Debug** - Enable logging for troubleshooting

## Controls

- **GREEN button** - Select/Confirm
- **RED button** - Back/Exit/Pause
- **UP/DOWN** - Navigate menus
- **LEFT/RIGHT** - Toggle options

## Loot Locations

- `/root/loot/handshakes/` - Captured handshake files (.pcap, .22000)
- `/root/loot/wigle/` - WiGLE CSV files (if GPS enabled)
- `/root/loot/ap_logs/` - AP discovery logs

## File Structure

```
pagergotchi/
├── payload.sh           # Main entry point
├── run_pagergotchi.py   # Python launcher
├── config.conf          # User configuration
├── data/                # Runtime data (created automatically)
├── lib/                 # Native libraries & Python packages
├── bin/                 # hcxdumptool binaries
└── pwnagotchi_port/     # Main Python module
```

## Credits

- **Author**: brAinphreAk
- **Website**: [www.brAinphreAk.net](http://www.brainphreak.net)
- **Based on**: [Pwnagotchi](https://github.com/evilsocket/pwnagotchi) by evilsocket
- **Hardware**: [Hak5 WiFi Pineapple Pager](https://hak5.org)

## License

This project is based on Pwnagotchi which is licensed under GPL-3.0.

## Disclaimer

This tool is intended for authorized security testing and educational purposes only. Only use on networks you own or have explicit permission to test. Unauthorized access to computer networks is illegal.
