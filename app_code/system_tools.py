"""Executable discovery and noninteractive commands."""
import os
import shutil
import subprocess
from pathlib import Path
from .settings import WINDOWS

def run_command(arguments, timeout=120):
    options = {}

    if WINDOWS:
        options["creationflags"] = subprocess.CREATE_NO_WINDOW

    result = subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        **options,
    )

    if result.returncode:
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or f"Command failed: exit code {result.returncode}"
        )

    return result.stdout.strip()


def find_program(name):
    found = shutil.which(name)

    if found:
        return found

    candidates = []

    if name == "docker":
        candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Docker/Docker/resources/bin/docker.exe",
            Path("/usr/local/bin/docker"),
            Path("/opt/homebrew/bin/docker"),
            Path("/Applications/Docker.app/Contents/Resources/bin/docker"),
            Path.home() / ".docker/bin/docker",
        ]

    elif name == "ssh":
        candidates = [
            Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32/OpenSSH/ssh.exe",
            Path("/usr/bin/ssh"),
        ]

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    raise RuntimeError(f"{name} was not found on this computer.")


