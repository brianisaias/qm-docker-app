# Quantum ESPRESSO app — editing guide

Run **main.py** in PyCharm. Keep `app_code` beside it.

## User interface

- **Connection:** choose local or school, connect, close the terminal, or stop the local container.
- **Calculations:** start pw.x, run an input file, interrupt a calculation, or find the program.
- **Files & User:** manage local files, list school files, or switch to the local max account.

Every action has an explanation beside its button. The current status and terminal remain visible across tabs.

## Where to edit

| File | Responsibility |
|---|---|
| `main.py` | Run entry point |
| `app_code/window.py` | Application startup and shared state |
| `app_code/interface_layout.py` | Button names, descriptions, tabs, widget layout and enabled states |
| `app_code/connection_manager.py` | Docker/SSH terminal connection and disconnection |
| `app_code/calculation_controls.py` | Run/stop pw.x, input files, max account action |
| `app_code/docker_controls.py` | Docker state, container shutdown, saved YAML selection |
| `app_code/file_manager.py` | Local browse/import/rename/delete operations |
| `app_code/terminal_display.py` | Keyboard input, terminal rendering, password prompts |
| `app_code/status_events.py` | Background event handling, messages and window closing |
| `app_code/terminal_process.py` | Windows/macOS terminal backend |
| `app_code/system_tools.py` | Locate programs and execute commands |
| `app_code/settings.py` | Server address and preferences location |
| `automated_checks/test_app.py` | Offline regression tests |

Run tests from this project folder: `python -m unittest discover -s automated_checks -v`.

The control classes share window state through inheritance. Most changes belong in one of the function-specific files above. Files and saved settings are not deleted by this cleanup.

`app_code/startup_setup.py` controls automatic dependency checking and first-time installation. Python, tkinter, Docker Desktop, and GlobalProtect are not installed by this helper.

`app_code/docker_desktop.py` opens Docker Desktop minimized on startup and waits for the Linux engine before local connection. Docker may still show first-time setup or update prompts.
