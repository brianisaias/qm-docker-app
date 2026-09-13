"""Open Docker Desktop in the background and wait for its engine."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from .system_tools import find_program, run_command

_launch_lock = threading.Lock()
_launched = False


def engine_ready(docker):
    try:
        return run_command([docker, "info", "--format", "{{.OSType}}"], timeout=5) == "linux"
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        return False


def launch_desktop():
    global _launched
    with _launch_lock:
        if _launched:
            return
        if sys.platform == "win32":
            candidates = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker/Docker/Docker Desktop.exe",
                          Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs/Docker/Docker/Docker Desktop.exe"]
            executable = next((p for p in candidates if p.is_file()), None)
            if executable is None:
                raise RuntimeError("Docker Desktop is not installed in a standard location. Open it manually, then Connect.")
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 7  # Minimize without activating the window.
            subprocess.Popen([str(executable)], startupinfo=startup,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "darwin":
            run_command(["/usr/bin/open", "-g", "-j", "-a", "Docker"], timeout=20)
        else:
            raise RuntimeError("Automatic Docker Desktop launch supports Windows and macOS.")
        _launched = True


def ensure_docker_ready(notify, canceled=lambda: False, timeout=120):
    docker = find_program("docker")
    if engine_ready(docker):
        return docker
    notify("Opening Docker Desktop minimized. Waiting for its Linux engine…")
    launch_desktop()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if canceled():
            raise RuntimeError("Connection canceled while Docker was starting.")
        if engine_ready(docker):
            notify("Docker engine is ready. You can connect locally.")
            return docker
        time.sleep(2)
    raise RuntimeError("Docker Desktop did not become ready within two minutes. Open it to check for a setup prompt or error, then retry Connect.")


def start_for_app(events):
    try:
        ensure_docker_ready(lambda text: events.put(("activity", text)))
    except Exception as error:
        events.put(("activity", "Docker startup: " + str(error)))
