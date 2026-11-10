#!/bin/sh
# Title: PagerGotchi
# Description: Pwnagotchi for WiFi Pineapple Pager - Automated WiFi handshake capture with personality
# Author: brAinphreAk
# Version: 2.0
# Category: Reconnaissance
# Library: pagerctl.py (pure-Python, bundled in lib/)
#
# Pagerctl-native launcher. pagerctl_home has already torn the pager
# down and stopped pineapplepager — we skip the duckyscript splash
# and just set up monitor mode and relaunch pineapd with handshake
# capture enabled, then hand control to run_pagergotchi.py.

PAYLOAD_DIR="/root/payloads/user/reconnaissance/pagergotchi"
DATA_DIR="$PAYLOAD_DIR/data"

cd "$PAYLOAD_DIR" || exit 1

export PATH="/mmc/usr/bin:$PAYLOAD_DIR/bin:$PATH"
export PYTHONPATH="$PAYLOAD_DIR/lib:$PAYLOAD_DIR:$PYTHONPATH"
export LD_LIBRARY_PATH="/mmc/usr/lib:$PAYLOAD_DIR/lib:$LD_LIBRARY_PATH"

command -v python3 >/dev/null 2>&1 || exit 1
[ ! -f "$PAYLOAD_DIR/lib/pagerctl.py" ] && exit 1
[ ! -d "$PAYLOAD_DIR/pwnagotchi_port" ] && exit 1

mkdir -p "$DATA_DIR" 2>/dev/null

setup_monitor_mode() {
    INTERFACE="wlan0mon"
    if ! iw dev 2>/dev/null | grep -q "$INTERFACE"; then
        ifconfig wlan0 down 2>/dev/null
        iw dev wlan0 set type monitor 2>/dev/null
        ifconfig wlan0 up 2>/dev/null
        ip link set wlan0 name "$INTERFACE" 2>/dev/null
        if ! iw dev 2>/dev/null | grep -q "$INTERFACE"; then
            command -v airmon-ng >/dev/null 2>&1 && airmon-ng start wlan0 2>/dev/null
        fi
    fi
}
setup_monitor_mode

# Stop conflicting services (pineapplepager is already stopped by
# pagerctl_home, so we don't touch it).
/etc/init.d/php8-fpm stop 2>/dev/null
/etc/init.d/nginx stop 2>/dev/null
/etc/init.d/bluetoothd stop 2>/dev/null

# Replace pineapd with a handshake-enabled instance
/etc/init.d/pineapd stop 2>/dev/null
killall pineapd 2>/dev/null
sleep 1

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

# GPS (optional)
GPS_DEVICE=$(uci -q get gpsd.core.device 2>/dev/null)
if [ -n "$GPS_DEVICE" ] && [ -e "$GPS_DEVICE" ]; then
    /etc/init.d/gpsd restart 2>/dev/null
    sleep 2
fi

sleep 0.5

NEXT_PAYLOAD_FILE="$DATA_DIR/.next_payload"

while true; do
    cd "$PAYLOAD_DIR"
    python3 run_pagergotchi.py
    EXIT_CODE=$?

    killall hcxdumptool 2>/dev/null
    if [ -n "$PINEAPD_PID" ]; then
        kill $PINEAPD_PID 2>/dev/null
        PINEAPD_PID=""
    fi
    killall pineapd 2>/dev/null

    if [ "$EXIT_CODE" -eq 42 ] && [ -f "$NEXT_PAYLOAD_FILE" ]; then
        NEXT_SCRIPT=$(cat "$NEXT_PAYLOAD_FILE")
        rm -f "$NEXT_PAYLOAD_FILE"
        if [ -f "$NEXT_SCRIPT" ]; then
            sh "$NEXT_SCRIPT"
            [ $? -eq 42 ] && continue
        fi
    fi

    break
done

sleep 1

# Restore auxiliary services (pineapplepager is restored by pagerctl_home)
/etc/init.d/pineapd start 2>/dev/null &
/etc/init.d/php8-fpm start 2>/dev/null &
/etc/init.d/nginx start 2>/dev/null &
/etc/init.d/bluetoothd start 2>/dev/null &

exit 0
