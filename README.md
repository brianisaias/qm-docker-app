# Quantum ESPRESSO Controller

Python desktop controls for local Quantum Mobile Docker and a school SSH server.

## Current testing checkpoint: v0.4.0

- The included `compose.yaml` works from the project folder on Windows and macOS. It keeps work in the relative `work` folder, avoids host-specific paths, and requests x86 emulation for Apple Silicon. **Choose Docker Compose File** still accepts a custom `.yml` or `.yaml` file and remembers it on that computer.
- Local Connect finds or opens Docker Desktop in the background, validates that the selected Compose file contains the `quantum-mobile` service, and displays the useful Docker error instead of an obsolete-version warning.
- School Connect goes directly to SSH after validating the Bronco ID. The app does not attempt to decide whether GlobalProtect or the school network is ready; connect them first when they are required.
- The Bronco password is held only in memory while connecting. The field clears when connection starts; the worker discards its copy after submitting it to SSH, or on failure, cancellation, or disconnection. **The app never permanently saves the Bronco password** in files, settings, logs, or credentials storage, and never passes it as a command argument. Authentication output after automatic password submission is withheld to prevent credential echo. SSH host-key verification remains enabled.
- Local Docker and school SSH sessions automatically report their real shell user and absolute folder, for example `Current user: max | Folder: /home/max/work`. This describes the connected terminal, not the host Mac/Windows user. The result stays visible across tabs and clears on disconnection.
- **Check current location** in the toolbar above the tabs refreshes the result after `cd` or a user switch. Use it at a shell prompt; paths containing spaces are supported. **Use local max account** also refreshes the actual location.
- The Calculations tab now follows the basic course workflow: check pw.x, create a calculation folder, review `.in` and `.UPF` files, run the input into a matching `.out` file, and check for `JOB DONE` and total energy.
- Windows and macOS terminal backends remain supported. The testing window title is **Quantum ESPRESSO Controller v0.4.0**.

## Run in PyCharm

1. Open this project and select a Python interpreter with tkinter support.
2. Run the app. If terminal packages are missing, first-time setup installs them into the current Python environment. Internet access is needed only for installation; setup shows errors and allows retry. You can also install manually with `python -m pip install -r requirements.txt`.
3. Run `main.py`.

For local use, select **My computer (Docker)** and click **Start & connect locally**. The included Compose file is selected automatically on a new computer. Docker Desktop opens in the background when possible. If Docker displays an update, license, or first-run prompt, finish it once and retry. Scientific files stay in the ignored `work` folder and are not committed to GitHub.

For remote use, connect GlobalProtect or the required school network first, select **School server (SSH)**, and enter your Bronco ID and password. OpenSSH connects to `10.104.94.21` and handles normal host-key verification. For SSH keys or interactive multi-factor authentication, leave the password field blank and answer the terminal prompts instead. Automatic password authentication times out after 60 seconds; close the connection and retry if needed.

## Controls

The toolbar above the tabs stays visible on every tab: **Check current location**, **List current directory** (including hidden files in the connected terminal), and **Interrupt calculation**. Directory actions are enabled when connected and idle; interrupt remains available during a calculation.

- **Connection:** open a local or remote terminal, disconnect, or stop the local container.
- **Calculations:** follow five numbered steps from setup through checking `JOB DONE` and total energy. A separate manual button starts pw.x without an input file.
- **Files & User:** manage the local shared folder, list remote files, or use the local max account.

Disconnect interrupts the foreground terminal program and exits the shell; it does not stop the local container. Stop Docker shuts down the local container. File deletion is permanent and affects the shared host folder.

## Development

See [EDITING_GUIDE.md](EDITING_GUIDE.md) for the function-specific modules.

Run offline regression tests:

```text
python -m unittest discover -s automated_checks -v
```

The suite includes non-graphical login, portable Compose, location, and version checks, plus Tk button and layout tests. UI tests skip with a reason if a graphical Tk session is unavailable. School-server file upload and job-scheduler integration are not implemented.
