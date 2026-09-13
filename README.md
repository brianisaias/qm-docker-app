# Quantum ESPRESSO Controller

Python desktop controls for local Quantum Mobile Docker and a school SSH server.

## Run in PyCharm

1. Open this project and select a Python interpreter with tkinter support.
2. Run the app. If terminal packages are missing, first-time setup installs them into the current Python environment. Internet access is needed only for installation; setup shows errors and allows retry. You can also install manually with `python -m pip install -r requirements.txt`.
3. Run `main.py`.

For local use, open Docker Desktop and choose your own Compose YAML file. The service must be named `quantum-mobile`, with the user `max` and a work directory at `/home/max/work`. The Compose file and scientific data are not included in this repository.

For remote use, connect the required school VPN, select School Server, and enter your Bronco ID. OpenSSH handles authentication. The app does not store passwords. The configured server address is in `app_code/settings.py`.

## Controls

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

The saved checkpoint passed 15 offline tests. Those tests simulate connections and do not establish compatibility with every Docker setup or school-server login. School-server file upload and job-scheduler integration are not implemented.
