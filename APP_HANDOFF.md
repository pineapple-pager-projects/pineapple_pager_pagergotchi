# App Handoff

Pagergotchi can seamlessly hand off to other payloads installed on the device. When a compatible payload is detected, an "Exit to [App]" option appears in the pause menu.

## How It Works

1. Select "Exit to [App]" from the pause menu
2. Pagergotchi cleanly shuts down (stops pineapd, cleans up processes)
3. The target app launches and takes full control of the display
4. When the target app exits normally, services are restored and the Pager returns to its launcher
5. If the target app exits with code 42, control returns to Pagergotchi

Each program runs alone — Pagergotchi, the target app, and the Pager service never run simultaneously.

## Adding Launcher Scripts

To make a payload available for handoff, create a `launch_<name>.sh` file in the `pagergotchi/` directory:

```bash
#!/bin/bash
# Title: My App
# Requires: /root/payloads/user/reconnaissance/my_app
# Description of what this launcher does

MY_APP_DIR="/root/payloads/user/reconnaissance/my_app"
# ... setup and launch ...
```

- **`# Title:`** - Display name shown in the pause menu (e.g., "Exit to My App")
- **`# Requires:`** - Path that must exist for the menu option to appear. If the path doesn't exist, the launcher is hidden.

The launcher script must use `bash` syntax (not `sh`/ash), as it is invoked with `bash`.

## Exit Code Convention

| Exit Code | Behavior |
|-----------|----------|
| 0 (or any non-42) | Services restored, Pager returns to launcher |
| 42 | Control returns to Pagergotchi |

The handoff target path is written to `data/.next_payload` and consumed by `payload.sh` after Pagergotchi exits with code 42.
