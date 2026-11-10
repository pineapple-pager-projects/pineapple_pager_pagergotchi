#!/bin/bash
# Title: PagerGotchi
# Description: Pwnagotchi for WiFi Pineapple Pager - Automated WiFi handshake capture with personality
# Author: brAinphreAk
# Version: 2.0
# Category: Reconnaissance
# Library: pagerctl.py (pure-Python, bundled in lib/)

# Payload directory (standard Pager installation path)
PAYLOAD_DIR="/root/payloads/user/reconnaissance/pagergotchi"
DATA_DIR="$PAYLOAD_DIR/data"

cd "$PAYLOAD_DIR" || {
    LOG "red" "ERROR: $PAYLOAD_DIR not found"
    exit 1
}

#
# pagerctl.py (pure-Python graphics/input library) is bundled in lib/.
# No shared library (libpagerctl.so) or python3-ctypes is required anymore.
#
if [ ! -f "$PAYLOAD_DIR/lib/pagerctl.py" ]; then
    LOG ""
    LOG "red" "=== MISSING DEPENDENCY ==="
    LOG ""
    LOG "red" "lib/pagerctl.py not found!"
    LOG ""
    LOG "Reinstall PagerGotchi so that:"
    LOG "  $PAYLOAD_DIR/lib/pagerctl.py"
    LOG "is present."
    LOG ""
    LOG "Press any button to exit..."
    WAIT_FOR_INPUT >/dev/null 2>&1
    exit 1
fi

#
# Setup local paths for bundled scripts and libraries
# Display/input handled by pure-Python lib/pagerctl.py (framebuffer takeover)
# MMC paths needed when python3 installed with opkg -d mmc
#
export PATH="/mmc/usr/bin:$PAYLOAD_DIR/bin:$PATH"
export PYTHONPATH="$PAYLOAD_DIR/lib:$PAYLOAD_DIR:$PYTHONPATH"
export LD_LIBRARY_PATH="/mmc/usr/lib:$PAYLOAD_DIR/lib:$LD_LIBRARY_PATH"

#
# Check for Python3 - the only required system dependency
#
if ! command -v python3 >/dev/null 2>&1; then
    LOG ""
    LOG "red" "=== MISSING REQUIREMENT ==="
    LOG ""
    LOG "Python3 is required to run PagerGotchi."
    LOG "All other dependencies are bundled."
    LOG ""
    LOG "green" "GREEN = Install dependencies (requires internet)"
    LOG "red" "RED   = Exit"
    LOG ""

    while true; do
        BUTTON=$(WAIT_FOR_INPUT 2>/dev/null)
        case "$BUTTON" in
            "GREEN"|"A")
                LOG ""
                LOG "Updating package lists..."
                opkg update 2>&1 | while IFS= read -r line; do LOG "  $line"; done
                LOG ""
                LOG "Installing Python3 to MMC..."
                opkg -d mmc install python3 2>&1 | while IFS= read -r line; do LOG "  $line"; done
                LOG ""
                # Verify installation succeeded
                if command -v python3 >/dev/null 2>&1; then
                    LOG "green" "Python3 installed successfully!"
                    sleep 1
                else
                    LOG "red" "Failed to install Python3"
                    LOG "red" "Check internet connection and try again."
                    LOG ""
                    LOG "Press any button to exit..."
                    WAIT_FOR_INPUT >/dev/null 2>&1
                    exit 1
                fi
                break
                ;;
            "RED"|"B")
                LOG "Exiting."
                exit 0
                ;;
        esac
    done
fi

# Verify pwnagotchi_port Python module exists
[ ! -d "$PAYLOAD_DIR/pwnagotchi_port" ] && {
    LOG "red" "ERROR: pwnagotchi_port module not found"
    exit 1
}

#
# Setup
#

# Create data directory
mkdir -p "$DATA_DIR" 2>/dev/null

# Setup monitor mode interface
setup_monitor_mode() {
    local INTERFACE="wlan0mon"

    if ! iw dev 2>/dev/null | grep -q "$INTERFACE"; then
        LOG "Setting up monitor mode..."

        ifconfig wlan0 down 2>/dev/null
        iw dev wlan0 set type monitor 2>/dev/null
        ifconfig wlan0 up 2>/dev/null
        ip link set wlan0 name "$INTERFACE" 2>/dev/null

        if ! iw dev 2>/dev/null | grep -q "$INTERFACE"; then
            if command -v airmon-ng >/dev/null 2>&1; then
                airmon-ng start wlan0 2>/dev/null
            fi
        fi

        if iw dev 2>/dev/null | grep -q "$INTERFACE"; then
            LOG "green" "Monitor mode enabled: $INTERFACE"
            return 0
        else
            if iw dev wlan0 info 2>/dev/null | grep -q "type monitor"; then
                LOG "green" "wlan0 already in monitor mode"
                return 0
            fi
            LOG "red" "Failed to enable monitor mode"
            return 1
        fi
    else
        LOG "green" "Monitor mode already active: $INTERFACE"
    fi
    return 0
}

#
# Main
#

# Show info/splash screen first
LOG ""
LOG "green" "Pwnagotchi for WiFi Pineapple Pager"
LOG "cyan" "ported by *brAinphreAk* (www.brAinphreAk.net)"
LOG ""
LOG "yellow" "Features:"
LOG "cyan" "  - Automated WiFi handshake capture"
LOG "cyan" "  - PMKID and 4-way handshake attacks"
LOG "cyan" "  - Deauth Scope: Whitelist/Blacklist"
LOG "cyan" "  - Privacy Mode: Obfuscate display"
LOG "cyan" "  - Optional GPS & WiGLE logging"
LOG ""
LOG "green" "GREEN = Start"
LOG "red" "RED = Exit"
LOG ""

while true; do
    BUTTON=$(WAIT_FOR_INPUT 2>/dev/null)
    case "$BUTTON" in
        "GREEN"|"A")
            break
            ;;
        "RED"|"B")
            LOG "Exiting."
            exit 0
            ;;
    esac
done

# Now do setup after GREEN button pressed
LOG ""
SPINNER_ID=$(START_SPINNER "Setting up PagerGotchi...")

if ! setup_monitor_mode; then
    STOP_SPINNER "$SPINNER_ID" 2>/dev/null
    LOG ""
    LOG "red" "Monitor mode setup failed!"
    LOG "Press any button to try anyway..."
    WAIT_FOR_INPUT >/dev/null 2>&1
    SPINNER_ID=$(START_SPINNER "Starting anyway...")
fi

# Free some resources while we run (the display itself is handled by
# UI_TAKEOVER below, NOT by stopping pineapplepager — the pager UI daemon
# stays running and simply yields the framebuffer).
/etc/init.d/php8-fpm stop 2>/dev/null
/etc/init.d/nginx stop 2>/dev/null
/etc/init.d/bluetoothd stop 2>/dev/null

# Hand the radio from the default pineapd to our own (handshakes enabled).
# Delete it from procd too, so it is not respawned while ours runs
# (pineapplepager's own stop hook normally does this; we must do it since
# we no longer stop pineapplepager).
STOP_SPINNER "$SPINNER_ID" 2>/dev/null
LOG "Starting pineapd with handshake capture..."
/etc/init.d/pineapd stop 2>/dev/null
ubus call service delete '{"name":"pineapd"}' 2>/dev/null
killall pineapd 2>/dev/null
sleep 1

# Start our pineapd with handshakes enabled
/usr/sbin/pineapd \
    --recon=true \
    --reconpath /root/recon/ \
    --reconname pager \
    --handshakepath /root/loot/handshakes/ \
    --handshakes=true \
    --partialhandshakes=true \
    --interface wlan1mon \
    --band wlan1mon:2,5 \
    --type wlan1mon:max \
    --hop wlan1mon:fast \
    --primary wlan1mon \
    --inject wlan1mon &
PINEAPD_PID=$!
sleep 2

# Verify pineapd started
if kill -0 $PINEAPD_PID 2>/dev/null; then
    LOG "green" "pineapd started with handshake capture (PID: $PINEAPD_PID)"
else
    LOG "red" "Warning: pineapd may not have started correctly"
fi

# Detect and setup GPS if available
LOG "Detecting GPS device..."
GPS_DEVICE=$(uci -q get gpsd.core.device 2>/dev/null)
if [ -n "$GPS_DEVICE" ] && [ -e "$GPS_DEVICE" ]; then
    LOG "green" "GPS detected: $GPS_DEVICE"
    LOG "Restarting gpsd..."
    /etc/init.d/gpsd restart 2>/dev/null
    sleep 2
else
    LOG "No GPS device detected (optional)"
fi

sleep 0.5

# ------------------------------------------------------------------
# Hold the display for the WHOLE session via UI_TAKEOVER (the firmware
# DuckyScript command), not by stopping the pineapplepager service.
# The pager UI daemon keeps running and yields /dev/fb0; on UI_RELEASE it
# simply redraws its home screen — no service cold-start / "restart".
# PAGERCTL_EXTERNAL_TAKEOVER tells lib/pagerctl.py to skip its own
# per-process takeover so there is no flicker between loop iterations.
# ------------------------------------------------------------------
export PAGERCTL_EXTERNAL_TAKEOVER=1
UI_TAKEOVER
trap 'UI_RELEASE 2>/dev/null' EXIT INT TERM

# Payload loop — PagerGotchi can hand off to other apps via exit code 42
# Python writes the target launch script path to data/.next_payload
NEXT_PAYLOAD_FILE="$DATA_DIR/.next_payload"

while true; do
    cd "$PAYLOAD_DIR"
    python3 run_pagergotchi.py
    EXIT_CODE=$?

    # Cleanup pagergotchi processes
    killall hcxdumptool 2>/dev/null
    if [ -n "$PINEAPD_PID" ]; then
        kill $PINEAPD_PID 2>/dev/null
        PINEAPD_PID=""
    fi
    killall pineapd 2>/dev/null

    # Exit code 42 = hand off to another payload
    if [ "$EXIT_CODE" -eq 42 ] && [ -f "$NEXT_PAYLOAD_FILE" ]; then
        NEXT_SCRIPT=$(cat "$NEXT_PAYLOAD_FILE")
        rm -f "$NEXT_PAYLOAD_FILE"

        if [ -f "$NEXT_SCRIPT" ]; then
            bash "$NEXT_SCRIPT"
            # Only loop back to pagergotchi if launched app exits 42
            [ $? -eq 42 ] && continue
        fi
    fi

    break
done

# Release the display back to the still-running pager UI daemon (also covered
# by the trap, but do it explicitly before restarting services).
UI_RELEASE 2>/dev/null

sleep 1

# Restore services on final exit. pineapplepager was never stopped, so it is
# NOT restarted here (that cold-start was the "pager restarted" on exit).
# Re-registering pineapd via its init script restores the default radio daemon.
/etc/init.d/pineapd start 2>/dev/null &
/etc/init.d/php8-fpm start 2>/dev/null &
/etc/init.d/nginx start 2>/dev/null &
/etc/init.d/bluetoothd start 2>/dev/null &
