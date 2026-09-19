"""window."""
import threading
from tkinter import filedialog, simpledialog, messagebox
from .file_manager import LocalFilesWindow

import queue

import secrets

import threading

import tkinter as tk

from .docker_controls import LocalControls

from .connection_manager import ConnectionControls

from .calculation_controls import CalculationControls

from .interface_layout import InterfaceLayout

from .terminal_display import TerminalDisplay

from .status_events import StatusEvents
from .settings import VERSION

class QuantumApp(InterfaceLayout, TerminalDisplay, StatusEvents, LocalControls, ConnectionControls, CalculationControls, tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(f"Quantum ESPRESSO Controller v{VERSION}")
        self.geometry("1080x900")
        self.minsize(900, 800)

        self.events = queue.Queue()
        self.docker_busy = False
        self.docker_checking = False
        self.docker_revision = 0
        self.docker_status = tk.StringVar(value="Docker: not checked")
        self.job_status = tk.StringVar(value="Calculation: not started")
        self.write_lock = threading.Lock()

        self.terminal = None
        self.screen = None
        self.stream = None

        self.active = False
        self.connected = False
        self.calculating = False
        self.disconnecting = False
        self.cancel_connection = False
        self.closing = False
        self.connection_error = ""

        self.location_marker = ""
        self.ready_marker = ""
        self.job_marker = ""
        self.max_marker = "QM_MAX_" + secrets.token_hex(16)
        self.user_status = tk.StringVar(value="Terminal user: not connected")
        self.received = ""

        self.method = tk.StringVar(value="local")
        self.compose_path = tk.StringVar(value=self.load_path())
        self.bronco_id = tk.StringVar()
        self.password = tk.StringVar()
        self.login_secret = None

        self.connection_status = tk.StringVar(value="Terminal: DISCONNECTED")
        self.activity = tk.StringVar(value="Choose a connection method.")
        self.activity.trace_add("write", self.record_activity)

        self.build_gui()

        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self.after(100, self.poll_events)
        self.after(300, self.refresh_docker_status)
