# Quantum ESPRESSO Controller

Python desktop controls for local Quantum Mobile Docker and a school SSH server.

## What changed in v0.2.0

- **Choose Docker Compose File** identifies the selected Compose file and filters for both `.yml` and `.yaml`. The existing saved-path behavior is preserved; the app does not bundle your Compose file or scientific data.
- School login checks for **GlobalProtect connected to `vpn.connect.cpp.edu`** first. If no connected VPN is detected, it checks Wi-Fi for **eduroam**. A detected VPN takes priority in the displayed result. Until an approved connection is detected, the Bronco ID, masked password field, and school Connect button are disabled. Use **Check school network** after changing networks. The result names the detected connection in the network status and activity log, for example `Connected Wi-Fi: eduroam | School login available` or `Connected VPN: GlobalProtect (vpn.connect.cpp.edu) | School login available`. The worker rechecks before starting SSH.
- Windows checks Wi-Fi with `netsh` and the GlobalProtect adapter with PowerShell. macOS uses `networksetup`, with a System Profiler fallback for Macs that incorrectly report Wi-Fi as disconnected, plus `scutil` and `ifconfig` for VPN detection. The fallback checks only the active network, not nearby networks, and may take up to 40 seconds. Missing commands, unavailable interfaces, privacy restrictions that hide the SSID, and detection errors leave school login disabled with a warning. A running GlobalProtect app alone is not proof of a connected VPN. Approval requires a live VPN interface and the latest GlobalProtect client status reporting Connected with portal `vpn.connect.cpp.edu`; a saved portal or another VPN does not qualify. The app reads only the tail of the local PanGPA status log and does not copy or display its contents. If that log is missing, unreadable, or uses an unsupported format, VPN verification fails and the app checks eduroam instead.
- The Bronco password is held only in memory while connecting. The field clears when connection starts; the worker discards its copy after submitting it to SSH, or on failure, cancellation, or disconnection. **The app never permanently saves the Bronco password** in files, settings, logs, or credentials storage, and never passes it as a command argument. Authentication output after automatic password submission is withheld to prevent credential echo. SSH host-key verification remains enabled.
- Local Docker and school SSH sessions automatically report their real shell user and absolute folder, for example `Current user: max | Folder: /home/max/work`. This describes the connected terminal, not the host Mac/Windows user. The result stays visible across tabs and clears on disconnection.
- **Check current location** in the toolbar above the tabs refreshes the result after `cd` or a user switch. Use it at a shell prompt; paths containing spaces are supported. **Use local max account** also refreshes the actual location.
- Windows and macOS terminal backends remain supported. The testing window title is **Quantum ESPRESSO Controller v0.2.0**. `app_code/settings.py` holds the central Python `VERSION` constant; the root `VERSION` file contains `0.2.0`, with a regression test checking they agree.

## Run in PyCharm

1. Open this project and select a Python interpreter with tkinter support.
2. Run the app. If terminal packages are missing, first-time setup installs them into the current Python environment. Internet access is needed only for installation; setup shows errors and allows retry. You can also install manually with `python -m pip install -r requirements.txt`.
3. Run `main.py`.

For local use, open Docker Desktop and choose your own Compose YAML file. The service must be named `quantum-mobile`, with the user `max` and a work directory at `/home/max/work`. The Compose file and scientific data are not included in this repository.

For remote use, join an approved school network, select School Server, check the network, and enter your Bronco ID and password. OpenSSH connects to `10.104.94.21` and handles normal host-key verification. For SSH keys or interactive multi-factor authentication, leave the password field blank and answer the normal terminal prompts instead. Automatic password authentication times out after 60 seconds; close the connection and retry if needed. The configured server address is in `app_code/settings.py`.

## Controls

The toolbar above the tabs stays visible on every tab: **Check current location**, **List current directory** (including hidden files in the connected terminal), and **Interrupt calculation**. Directory actions are enabled when connected and idle; interrupt remains available during a calculation.

- **Connection:** open a local or remote terminal, disconnect, or stop the local container.
- **Calculations:** start pw.x, run an existing input file, interrupt the foreground program, or check its location.
- **Files & User:** manage the local shared folder, list remote files, or use the local max account.

Disconnect interrupts the foreground terminal program and exits the shell; it does not stop the local container. Stop Docker shuts down the local container. File deletion is permanent and affects the shared host folder.

## Development

See [EDITING_GUIDE.md](EDITING_GUIDE.md) for the function-specific modules.

Run offline regression tests:

```text
python -m unittest discover -s automated_checks -v
```

The suite includes non-graphical network, login, Compose selection, location, and version checks, plus Tk UI regression tests. UI tests skip with a reason if a subprocess cannot initialize a graphical Tk session. Platform command responses are simulated; these tests do not establish compatibility with every Docker setup, GlobalProtect version, or school-server login. School-server file upload and job-scheduler integration are not implemented.
