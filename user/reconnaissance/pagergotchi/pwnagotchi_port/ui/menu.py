"""
Startup and pause menus for Pagergotchi
Uses native C library (libpager.so) for fast rendering
"""

import json
import os
import subprocess
import time

# Payload directory paths
PAYLOAD_DIR = '/root/payloads/user/reconnaissance/pagergotchi'
DATA_DIR = os.path.join(PAYLOAD_DIR, 'data')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
RECOVERY_FILE = os.path.join(DATA_DIR, 'recovery.json')

from pwnagotchi_port.ui.hw.pager import (
    PagerDisplay,
    FONT_SMALL, FONT_MEDIUM, FONT_LARGE,
    PBTN_UP, PBTN_DOWN, PBTN_LEFT, PBTN_RIGHT, PBTN_A, PBTN_B,
    COLOR_BLACK, COLOR_WHITE, COLOR_GREEN, COLOR_RED,
    COLOR_YELLOW, COLOR_GRAY
)

COLOR_DARK_GRAY = 0x4208


class StartupMenu:
    """
    Startup menu with whitelist management
    Uses native pager_gfx for fast rendering
    """

    def __init__(self, config, display=None):
        self.config = config
        self.config_path = config.get('config_path', '/root/payloads/user/reconnaissance/pagergotchi/config.conf')

        # Use provided display or create new one
        if display:
            self.gfx = display
            self._owns_display = False
        else:
            self.gfx = PagerDisplay(config)
            self.gfx.initialize()
            self._owns_display = True

        # Toggle settings (load from persistent file first, then config)
        self.wigle_enabled = config.get('wigle', {}).get('enabled', False)
        self.log_aps_enabled = config.get('log_aps', {}).get('enabled', False)

        # Load from persistent settings file
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    self.wigle_enabled = settings.get('wigle_enabled', self.wigle_enabled)
                    self.log_aps_enabled = settings.get('log_aps_enabled', self.log_aps_enabled)
        except Exception:
            pass

    def scan_networks(self):
        """Scan for nearby WiFi networks using PineAP, returns list of {ssid, bssid} dicts"""
        networks = []
        seen_ssids = set()

        # Try PineAP first (best option on Pineapple)
        try:
            result = subprocess.run(
                ['_pineap', 'RECON', 'APS', 'limit=50', 'format=json'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                try:
                    data = json.loads(result.stdout)
                    aps_list = data if isinstance(data, list) else data.get('aps', data.get('data', []))
                    for ap in aps_list:
                        ssid = ap.get('ssid', ap.get('essid', ap.get('name', '')))
                        bssid = ap.get('mac', ap.get('bssid', ''))
                        if ssid and ssid not in seen_ssids:
                            seen_ssids.add(ssid)
                            networks.append({'ssid': ssid, 'bssid': bssid})
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            pass

        # Fallback to iwinfo
        if not networks:
            try:
                result = subprocess.run(
                    ['iwinfo', 'wlan0', 'scan'],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    current_bssid = None
                    for line in result.stdout.split('\n'):
                        if 'Address:' in line:
                            parts = line.split('Address:')
                            if len(parts) > 1:
                                current_bssid = parts[1].strip()
                        elif 'ESSID:' in line:
                            ssid = line.split('ESSID:')[1].strip().strip('"')
                            if ssid and ssid not in seen_ssids:
                                seen_ssids.add(ssid)
                                networks.append({'ssid': ssid, 'bssid': current_bssid or ''})
            except:
                pass

        return networks[:12]

    def get_whitelist(self):
        """Get current whitelist SSIDs from config and PineAP"""
        whitelist = set()

        # Read from pagergotchi config
        try:
            with open(self.config_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('ssids'):
                        parts = line.split('=', 1)
                        if len(parts) > 1:
                            ssids = parts[1].strip()
                            whitelist.update(s.strip() for s in ssids.split(',') if s.strip())
                        break
        except:
            pass

        # Also read from PineAP ssid_filter (UCI format)
        try:
            import subprocess
            result = subprocess.run(
                ['uci', 'get', 'pineapd.@ssid_filter[0].ssid'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                # UCI returns space-separated list
                for ssid in result.stdout.strip().split():
                    whitelist.add(ssid.strip("'\""))
        except:
            pass

        # Also try reading list entries
        try:
            import subprocess
            result = subprocess.run(
                ['uci', 'show', 'pineapd.@ssid_filter[0]'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if '.ssid=' in line or ".ssid'" in line:
                        # Extract SSID from UCI output like: pineapd.xxx.ssid='NetworkName'
                        parts = line.split('=', 1)
                        if len(parts) > 1:
                            ssid = parts[1].strip().strip("'\"")
                            if ssid:
                                whitelist.add(ssid)
        except:
            pass

        return list(whitelist)

    def save_whitelist(self, ssids, bssids=None):
        """Save whitelist SSIDs to config file"""
        try:
            with open(self.config_path, 'r') as f:
                lines = f.readlines()

            with open(self.config_path, 'w') as f:
                for line in lines:
                    if line.strip().startswith('ssids'):
                        f.write(f"ssids = {', '.join(ssids)}\n")
                    else:
                        f.write(line)
        except Exception as e:
            print(f"Error saving whitelist: {e}")

    def _wait_button(self, timeout=None):
        """Wait for a button press"""
        start = time.time()
        while True:
            if timeout and (time.time() - start) > timeout:
                return None
            current, pressed, released = self.gfx.poll_input()
            if pressed:
                if pressed & PBTN_UP:
                    return 'UP'
                if pressed & PBTN_DOWN:
                    return 'DOWN'
                if pressed & PBTN_LEFT:
                    return 'LEFT'
                if pressed & PBTN_RIGHT:
                    return 'RIGHT'
                if pressed & PBTN_B:  # GREEN button (right) = Select
                    return 'SELECT'
                if pressed & PBTN_A:  # RED button (left) = Exit/Back
                    return 'BACK'
            time.sleep(0.016)

    def _save_toggle_settings(self):
        """Save toggle settings to config"""
        # Update in-memory config
        if 'wigle' not in self.config:
            self.config['wigle'] = {}
        if 'log_aps' not in self.config:
            self.config['log_aps'] = {}

        self.config['wigle']['enabled'] = self.wigle_enabled
        self.config['log_aps']['enabled'] = self.log_aps_enabled

        # Save to persistent settings file
        try:
            import json
            # Ensure data directory exists
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)
            settings = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
            settings['wigle_enabled'] = self.wigle_enabled
            settings['log_aps_enabled'] = self.log_aps_enabled
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f)
        except Exception:
            pass

    def _draw_main_menu(self, selected, options):
        """Draw the main menu"""
        self.gfx.clear(COLOR_BLACK)

        # Title (moved up)
        self.gfx.draw_text_centered(8, "PAGERGOTCHI", COLOR_GREEN, FONT_LARGE)

        # Subtitle (moved up)
        self.gfx.draw_text_centered(32, "pwnagotchi for pineapple pager", COLOR_GRAY, FONT_SMALL)

        # Menu options (moved up, tighter spacing)
        y = 52
        for i, opt in enumerate(options):
            is_toggle = opt.startswith('WiGLE:') or opt.startswith('Log APs:')

            if is_toggle:
                # Handle toggle options specially
                if opt.startswith('WiGLE:'):
                    label = "WiGLE: "
                    value = "Yes" if self.wigle_enabled else "No"
                    value_color = COLOR_GREEN if self.wigle_enabled else COLOR_RED
                else:
                    label = "Log APs: "
                    value = "Yes" if self.log_aps_enabled else "No"
                    value_color = COLOR_GREEN if self.log_aps_enabled else COLOR_RED

                label_color = COLOR_GREEN if i == selected else COLOR_WHITE
                # Center the full "Label: Value" text
                full_text = label + value
                full_width = self.gfx.text_width(full_text, FONT_MEDIUM)
                label_width = self.gfx.text_width(label, FONT_MEDIUM)
                start_x = (480 - full_width) // 2
                self.gfx.draw_text(start_x, y + 6, label, label_color, FONT_MEDIUM)
                self.gfx.draw_text(start_x + label_width, y + 6, value, value_color, FONT_MEDIUM)
            else:
                color = COLOR_GREEN if i == selected else COLOR_WHITE
                self.gfx.draw_text_centered(y + 6, opt, color, FONT_MEDIUM)
            y += 22

        # Credits on bottom right (right-aligned using actual text width)
        margin = 10
        credit1 = "by *brAinphreAk*"
        credit2 = "www.brAinphreAk.net"
        credit1_width = self.gfx.text_width(credit1, FONT_SMALL)
        credit2_width = self.gfx.text_width(credit2, FONT_SMALL)
        self.gfx.draw_text(480 - credit1_width - margin, self.gfx.height - 28, credit1, COLOR_GRAY, FONT_SMALL)
        self.gfx.draw_text(480 - credit2_width - margin, self.gfx.height - 16, credit2, COLOR_GRAY, FONT_SMALL)

        # Bottom instructions (left side, colored text with proper spacing)
        x = 10
        self.gfx.draw_text(x, self.gfx.height - 18, "RED:", COLOR_RED, FONT_SMALL)
        x += self.gfx.text_width("RED:", FONT_SMALL)
        self.gfx.draw_text(x, self.gfx.height - 18, "Exit", COLOR_GRAY, FONT_SMALL)
        x += self.gfx.text_width("Exit", FONT_SMALL) + 10  # small gap between Exit and GREEN
        self.gfx.draw_text(x, self.gfx.height - 18, "GREEN:", COLOR_GREEN, FONT_SMALL)
        x += self.gfx.text_width("GREEN:", FONT_SMALL)
        self.gfx.draw_text(x, self.gfx.height - 18, "Select", COLOR_GRAY, FONT_SMALL)

        self.gfx.flip()

    def show_main_menu(self):
        """
        Show main startup menu
        Returns True to continue to pagergotchi, False to exit
        """
        selected = 0
        options = [
            'Start Pagergotchi',
            'Edit Whitelist',
            'View Whitelist',
            'WiGLE:',
            'Log APs:',
            'Clear History'
        ]

        self._draw_main_menu(selected, options)

        while True:
            btn = self._wait_button()

            if btn == 'UP':
                selected = (selected - 1) % len(options)
                self._draw_main_menu(selected, options)
            elif btn == 'DOWN':
                selected = (selected + 1) % len(options)
                self._draw_main_menu(selected, options)
            elif btn in ['LEFT', 'RIGHT']:
                # Handle toggles
                if selected == 3:  # WiGLE toggle
                    self.wigle_enabled = not self.wigle_enabled
                    # Auto-enable Log APs when WiGLE is enabled
                    if self.wigle_enabled:
                        self.log_aps_enabled = True
                    self._save_toggle_settings()
                    self._draw_main_menu(selected, options)
                elif selected == 4:  # Log APs toggle
                    self.log_aps_enabled = not self.log_aps_enabled
                    # Auto-disable WiGLE when Log APs is disabled
                    if not self.log_aps_enabled:
                        self.wigle_enabled = False
                    self._save_toggle_settings()
                    self._draw_main_menu(selected, options)
            elif btn == 'SELECT':
                if selected == 0:  # Start
                    return True
                elif selected == 1:  # Edit Whitelist
                    self.show_network_scanner()
                    self._draw_main_menu(selected, options)
                elif selected == 2:  # View Whitelist
                    self.show_whitelist_view()
                    self._draw_main_menu(selected, options)
                elif selected == 3:  # WiGLE toggle - also toggle on select
                    self.wigle_enabled = not self.wigle_enabled
                    if self.wigle_enabled:
                        self.log_aps_enabled = True
                    self._save_toggle_settings()
                    self._draw_main_menu(selected, options)
                elif selected == 4:  # Log APs toggle
                    self.log_aps_enabled = not self.log_aps_enabled
                    # Auto-disable WiGLE when Log APs is disabled
                    if not self.log_aps_enabled:
                        self.wigle_enabled = False
                    self._save_toggle_settings()
                    self._draw_main_menu(selected, options)
                elif selected == 5:  # Clear History
                    self.clear_history_confirm()
                    self._draw_main_menu(selected, options)
            elif btn == 'BACK':
                return False

    def show_network_scanner(self):
        """Scan for networks and let user add to whitelist"""
        self.gfx.clear(COLOR_BLACK)
        self.gfx.draw_text_centered(100, "Scanning...", COLOR_YELLOW, FONT_LARGE)
        self.gfx.flip()

        networks = self.scan_networks()
        whitelist = self.get_whitelist()

        if not networks:
            self.gfx.clear(COLOR_BLACK)
            self.gfx.draw_text_centered(80, "No networks found!", COLOR_RED, FONT_MEDIUM)
            self.gfx.draw_text_centered(110, "Try again later", COLOR_GRAY, FONT_SMALL)
            self.gfx.draw_text_centered(180, "Press any button...", COLOR_GRAY, FONT_SMALL)
            self.gfx.flip()
            self._wait_button()
            return

        selected = 0
        scroll_offset = 0
        max_visible = 4

        while True:
            self.gfx.clear(COLOR_BLACK)
            self.gfx.draw_text_centered(12, "SELECT NETWORK", COLOR_GREEN, FONT_MEDIUM)

            y = 45
            for i in range(scroll_offset, min(scroll_offset + max_visible, len(networks))):
                net = networks[i]
                ssid = net['ssid']
                is_whitelisted = ssid in whitelist

                if i == selected:
                    self.gfx.fill_rect(15, y - 4, self.gfx.width - 30, 28, COLOR_DARK_GRAY)
                    color = COLOR_GREEN
                else:
                    color = COLOR_WHITE

                prefix = "[+] " if is_whitelisted else "    "
                display_color = COLOR_YELLOW if is_whitelisted else color
                self.gfx.draw_text(20, y, f"{prefix}{ssid[:18]}", display_color, FONT_MEDIUM)
                y += 32

            self.gfx.draw_text(10, self.gfx.height - 35, "GREEN: Add", COLOR_GREEN, FONT_SMALL)
            self.gfx.draw_text(10, self.gfx.height - 18, "RED: Back", COLOR_RED, FONT_SMALL)
            self.gfx.flip()

            btn = self._wait_button()
            if btn == 'UP':
                selected = max(0, selected - 1)
                if selected < scroll_offset:
                    scroll_offset = selected
            elif btn == 'DOWN':
                selected = min(len(networks) - 1, selected + 1)
                if selected >= scroll_offset + max_visible:
                    scroll_offset = selected - max_visible + 1
            elif btn == 'SELECT':
                net = networks[selected]
                ssid = net['ssid']
                if ssid not in whitelist:
                    whitelist.append(ssid)
                    self.save_whitelist(whitelist)
                    self.gfx.clear(COLOR_BLACK)
                    self.gfx.draw_text_centered(100, "Added!", COLOR_GREEN, FONT_LARGE)
                    self.gfx.flip()
                    time.sleep(0.5)
            elif btn == 'BACK':
                return

    def show_whitelist_view(self):
        """View current whitelist"""
        whitelist = self.get_whitelist()
        selected = 0
        scroll_offset = 0
        max_visible = 4

        while True:
            self.gfx.clear(COLOR_BLACK)
            self.gfx.draw_text_centered(12, "WHITELIST", COLOR_YELLOW, FONT_MEDIUM)

            if not whitelist:
                self.gfx.draw_text_centered(100, "Whitelist is empty", COLOR_GRAY, FONT_MEDIUM)
            else:
                y = 45
                for i in range(scroll_offset, min(scroll_offset + max_visible, len(whitelist))):
                    ssid = whitelist[i]
                    if i == selected:
                        self.gfx.fill_rect(15, y - 4, self.gfx.width - 30, 28, COLOR_DARK_GRAY)
                        self.gfx.draw_text(20, y, ssid[:20], COLOR_GREEN, FONT_MEDIUM)
                    else:
                        self.gfx.draw_text(20, y, ssid[:20], COLOR_WHITE, FONT_MEDIUM)
                    y += 32

            self.gfx.draw_text(10, self.gfx.height - 35, "GREEN: Remove", COLOR_GREEN, FONT_SMALL)
            self.gfx.draw_text(10, self.gfx.height - 18, "RED: Back", COLOR_RED, FONT_SMALL)
            self.gfx.flip()

            btn = self._wait_button()
            if btn == 'UP' and whitelist:
                selected = max(0, selected - 1)
                if selected < scroll_offset:
                    scroll_offset = selected
            elif btn == 'DOWN' and whitelist:
                selected = min(len(whitelist) - 1, selected + 1)
                if selected >= scroll_offset + max_visible:
                    scroll_offset = selected - max_visible + 1
            elif btn == 'SELECT' and whitelist:
                whitelist.pop(selected)
                self.save_whitelist(whitelist)
                if selected >= len(whitelist) and whitelist:
                    selected = len(whitelist) - 1
            elif btn == 'BACK':
                return

    def clear_whitelist_confirm(self):
        """Confirm clearing whitelist"""
        selected = 1  # Default to No

        while True:
            self.gfx.clear(COLOR_BLACK)
            self.gfx.draw_text_centered(50, "Clear Whitelist?", COLOR_YELLOW, FONT_LARGE)
            self.gfx.draw_text_centered(85, "This cannot be undone!", COLOR_RED, FONT_SMALL)

            center = self.gfx.width // 2
            if selected == 0:
                self.gfx.fill_rect(center - 100, 115, 70, 30, COLOR_DARK_GRAY)
                self.gfx.draw_text(center - 85, 125, "YES", COLOR_RED, FONT_MEDIUM)
                self.gfx.draw_text(center + 45, 125, "NO", COLOR_WHITE, FONT_MEDIUM)
            else:
                self.gfx.fill_rect(center + 30, 115, 60, 30, COLOR_DARK_GRAY)
                self.gfx.draw_text(center - 85, 125, "YES", COLOR_WHITE, FONT_MEDIUM)
                self.gfx.draw_text(center + 45, 125, "NO", COLOR_GREEN, FONT_MEDIUM)

            self.gfx.draw_text_centered(self.gfx.height - 25, "LEFT/RIGHT to select, GREEN to confirm", COLOR_GRAY, FONT_SMALL)
            self.gfx.flip()

            btn = self._wait_button()
            if btn in ['LEFT', 'RIGHT', 'UP', 'DOWN']:
                selected = 1 - selected
            elif btn == 'SELECT':
                if selected == 0:
                    self.save_whitelist([])
                    self.gfx.clear(COLOR_BLACK)
                    self.gfx.draw_text_centered(100, "Cleared!", COLOR_GREEN, FONT_LARGE)
                    self.gfx.flip()
                    time.sleep(0.5)
                return
            elif btn == 'BACK':
                return

    def clear_history_confirm(self):
        """Confirm clearing attack history (recovery file)"""
        selected = 1  # Default to No

        while True:
            self.gfx.clear(COLOR_BLACK)
            self.gfx.draw_text_centered(40, "Clear History?", COLOR_YELLOW, FONT_LARGE)
            self.gfx.draw_text_centered(75, "Resets attack tracking", COLOR_GRAY, FONT_SMALL)
            self.gfx.draw_text_centered(95, "for all networks", COLOR_GRAY, FONT_SMALL)

            center = self.gfx.width // 2
            if selected == 0:
                self.gfx.fill_rect(center - 100, 125, 70, 30, COLOR_DARK_GRAY)
                self.gfx.draw_text(center - 85, 135, "YES", COLOR_RED, FONT_MEDIUM)
                self.gfx.draw_text(center + 45, 135, "NO", COLOR_WHITE, FONT_MEDIUM)
            else:
                self.gfx.fill_rect(center + 30, 125, 60, 30, COLOR_DARK_GRAY)
                self.gfx.draw_text(center - 85, 135, "YES", COLOR_WHITE, FONT_MEDIUM)
                self.gfx.draw_text(center + 45, 135, "NO", COLOR_GREEN, FONT_MEDIUM)

            self.gfx.draw_text_centered(self.gfx.height - 25, "LEFT/RIGHT to select, GREEN to confirm", COLOR_GRAY, FONT_SMALL)
            self.gfx.flip()

            btn = self._wait_button()
            if btn in ['LEFT', 'RIGHT', 'UP', 'DOWN']:
                selected = 1 - selected
            elif btn == 'SELECT':
                if selected == 0:
                    try:
                        if os.path.exists(RECOVERY_FILE):
                            os.remove(RECOVERY_FILE)
                    except Exception:
                        pass
                    self.gfx.clear(COLOR_BLACK)
                    self.gfx.draw_text_centered(100, "History Cleared!", COLOR_GREEN, FONT_LARGE)
                    self.gfx.flip()
                    time.sleep(0.5)
                return
            elif btn == 'BACK':
                return

    def cleanup(self):
        """Clean up resources"""
        if self._owns_display and hasattr(self, 'gfx'):
            self.gfx.cleanup()


class PauseMenu:
    """Pause menu shown when red button is pressed during operation"""

    def __init__(self, display, agent=None):
        self.gfx = display
        self.agent = agent
        self.deauth_enabled = True
        if agent and hasattr(agent, '_config'):
            self.deauth_enabled = agent._config.get('personality', {}).get('deauth', True)

    def _wait_button(self):
        """Wait for a button press"""
        while True:
            current, pressed, released = self.gfx.poll_input()
            if pressed:
                if pressed & PBTN_UP:
                    return 'UP'
                if pressed & PBTN_DOWN:
                    return 'DOWN'
                if pressed & PBTN_LEFT:
                    return 'LEFT'
                if pressed & PBTN_RIGHT:
                    return 'RIGHT'
                if pressed & PBTN_B:  # GREEN = Select
                    return 'SELECT'
                if pressed & PBTN_A:  # RED = Back
                    return 'BACK'
            time.sleep(0.016)

    def show(self):
        """
        Show pause menu
        Returns: 'continue', 'exit', or 'shutdown'
        """
        # Wait for all buttons to be released before accepting input
        for _ in range(50):  # Up to 1 second
            current, pressed, released = self.gfx.poll_input()
            if current == 0:
                break
            time.sleep(0.02)
        # Extra settle time
        time.sleep(0.2)
        # Drain any queued presses
        for _ in range(10):
            self.gfx.poll_input()
            time.sleep(0.01)

        selected = 0
        # Options: Continue, Deauth toggle, Exit
        options = ['Continue', 'Deauth: ', 'Exit Pagergotchi']

        while True:
            self.gfx.clear(COLOR_BLACK)
            self.gfx.draw_text_centered(25, "PAUSED", COLOR_YELLOW, FONT_LARGE)

            y = 80
            for i, opt in enumerate(options):
                if i == selected:
                    self.gfx.fill_rect(40, y - 2, self.gfx.width - 80, 28, COLOR_DARK_GRAY)

                # Special handling for deauth toggle
                if i == 1:
                    label = "Deauth: "
                    value = "ON" if self.deauth_enabled else "OFF"
                    value_color = COLOR_GREEN if self.deauth_enabled else COLOR_RED

                    if i == selected:
                        self.gfx.draw_text(60, y + 4, label, COLOR_GREEN, FONT_MEDIUM)
                        # Draw toggle with arrows
                        self.gfx.draw_text(180, y + 4, "<", COLOR_WHITE, FONT_MEDIUM)
                        self.gfx.draw_text(210, y + 4, value, value_color, FONT_MEDIUM)
                        self.gfx.draw_text(280, y + 4, ">", COLOR_WHITE, FONT_MEDIUM)
                    else:
                        self.gfx.draw_text(60, y + 4, label, COLOR_WHITE, FONT_MEDIUM)
                        self.gfx.draw_text(210, y + 4, value, value_color, FONT_MEDIUM)
                else:
                    color = COLOR_GREEN if i == selected else COLOR_WHITE
                    self.gfx.draw_text_centered(y + 4, opt, color, FONT_MEDIUM)

                y += 35

            self.gfx.draw_text(10, self.gfx.height - 18, "GREEN:Select  RED:Resume  L/R:Toggle", COLOR_GRAY, FONT_SMALL)
            self.gfx.flip()

            btn = self._wait_button()
            if btn == 'UP':
                selected = (selected - 1) % len(options)
            elif btn == 'DOWN':
                selected = (selected + 1) % len(options)
            elif btn in ['LEFT', 'RIGHT']:
                # Toggle deauth if on that option
                if selected == 1:
                    self.deauth_enabled = not self.deauth_enabled
                    # Update agent config if available
                    if self.agent and hasattr(self.agent, '_config'):
                        self.agent._config['personality']['deauth'] = self.deauth_enabled
            elif btn == 'SELECT':
                if selected == 0:
                    return 'continue'
                elif selected == 1:
                    # Toggle deauth
                    self.deauth_enabled = not self.deauth_enabled
                    if self.agent and hasattr(self.agent, '_config'):
                        self.agent._config['personality']['deauth'] = self.deauth_enabled
                elif selected == 2:
                    return 'exit'
            elif btn == 'BACK':
                return 'continue'
