"""Server address, platform detection, and saved settings location."""
import os
import platform
from pathlib import Path

VERSION = "0.2.0"

SERVER = "10.104.94.21"


SERVICE = "quantum-mobile"


WINDOWS = platform.system() == "Windows"


MAC = platform.system() == "Darwin"


SETTINGS_FOLDER = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    if WINDOWS
    else Path.home() / "Library/Application Support"
) / "QuantumMobileController"


SETTINGS_FILE = SETTINGS_FOLDER / "compose-path.txt"


