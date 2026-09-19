"""interface layout."""
import tkinter as tk

from tkinter import ttk

from .settings import SERVER, WINDOWS, VERSION
from .interface_style import configure_style, SURFACE, MUTED

class InterfaceLayout:
    def build_gui(self):
        self.interface_style = configure_style(self)
        panel = ttk.Frame(self, padding=14, style="Page.TFrame")
        panel.pack(fill="both", expand=True)
        header = ttk.Frame(panel, style="Page.TFrame")
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text="Quantum ESPRESSO", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"v{VERSION}  ·  Testing", style="Version.TLabel").pack(side="right")
        ttk.Label(panel, text="Your workspace for connections, calculations, and files.", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 10))
        self.buttons = {}
        self.quick_actions = ttk.Frame(panel, padding=(12, 8))
        self.quick_actions.pack(fill="x", pady=(0, 8))
        ttk.Label(self.quick_actions, text="QUICK ACTIONS", style="Section.TLabel").pack(side="left", padx=(0, 16))
        for key, label, callback in (
            ("Check current location", "Check current location", self.check_current_location),
            ("List current directory", "List current directory", self.list_current_directory),
            ("Stop Calculation", "Interrupt calculation", self.stop_calculation),
        ):
            button = ttk.Button(self.quick_actions, text=label, command=callback, style="Stop.TButton" if key == "Stop Calculation" else "TButton")
            button.pack(side="left", padx=(0, 8))
            self.buttons[key] = button
        self.section_nav = ttk.Frame(panel)
        self.section_nav.pack(fill="x", pady=(0, 4))
        self.sections = ttk.Notebook(panel)
        self.sections.pack(fill="x", pady=(0, 8))
        connection = ttk.Frame(self.sections, padding=(14, 8))
        calculations = ttk.Frame(self.sections, padding=(14, 8))
        files = ttk.Frame(self.sections, padding=(14, 8))
        for page, title in [(connection, "1. Connection"), (calculations, "2. Calculations"), (files, "3. Files & User")]:
            self.sections.add(page, text=title)
        # App-wide keyboard navigation keeps notebook pages reachable even
        # when a native window manager does not forward notebook mouse clicks.
        self.bind_all("<KeyPress>", self.app_key_shortcut, add="+")

        def action(parent, key, label, description, callback):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=3)
            button = ttk.Button(row, text=label, command=callback, width=25, style="Primary.TButton" if key in ("Connect", "Run Calculation") else "TButton")
            button.pack(side="left")
            ttk.Label(row, text=description, wraplength=465, style="Muted.TLabel").pack(side="left", padx=12, fill="x", expand=True)
            if key:
                self.buttons[key] = button
            return button

        choice = ttk.Frame(connection)
        choice.pack(fill="x", pady=(0, 6))
        self.local_radio = ttk.Radiobutton(choice, text="My computer (Docker)", variable=self.method, value="local", command=self.update_controls)
        self.local_radio.pack(side="left")
        self.remote_radio = ttk.Radiobutton(choice, text="School server (SSH)", variable=self.method, value="remote", command=self.update_controls)
        self.remote_radio.pack(side="left", padx=20)
        local = ttk.Frame(connection)
        local.pack(fill="x", pady=3)
        ttk.Label(local, text="Docker Compose file:", width=20).pack(side="left")
        ttk.Entry(local, textvariable=self.compose_path, state="readonly").pack(side="left", fill="x", expand=True, padx=8)
        self.choose_button = ttk.Button(local, text="Choose Docker Compose File", command=self.choose_yaml)
        self.choose_button.pack(side="left")
        account = ttk.Frame(connection)
        account.pack(fill="x", pady=3)
        ttk.Label(account, text="School Bronco ID:", width=20).pack(side="left")
        self.id_entry = ttk.Entry(account, textvariable=self.bronco_id, width=22)
        self.id_entry.pack(side="left", padx=8)
        ttk.Label(account, text=f"SSH · {SERVER}", style="Muted.TLabel").pack(side="left")
        password_row = ttk.Frame(connection)
        password_row.pack(fill="x", pady=3)
        ttk.Label(password_row, text="School password:", width=20).pack(side="left")
        self.password_entry = ttk.Entry(password_row, textvariable=self.password, show="*", width=22)
        self.password_entry.pack(side="left", padx=8)
        action(connection, "Connect", "Connect", "Open a terminal on your chosen computer. Local mode starts Quantum Mobile if needed.", self.connect)
        action(connection, "Disconnect", "Close connection", "Interrupt the foreground program and close the terminal. Local Docker stays running.", self.disconnect)
        self.stop_docker_button = action(connection, None, "Shut down local Docker", "Stop the Quantum Mobile container and its work. Does not shut down the school server.", self.stop_docker)

        action(calculations, "Run pw.x", "Start pw.x", "Open Quantum ESPRESSO without an input file. It may wait for input; this is not a completed calculation.", self.run_pw_direct)
        action(calculations, "Run Calculation", "Run an input file", "Choose an existing input-file path on the connected computer and run the calculation.", self.run_calculation)
        action(calculations, "Check QE", "Check program location", "Show the current user, folder, and where pw.x is installed. Does not run a calculation.", self.check_qe)

        action(files, "Show Files", "Open local files", "Local: browse, import, rename, and delete shared files. School: list the current server folder in the terminal.", self.show_files)
        self.max_button = action(files, None, "Use local max account", "Local only: switch to max if needed and return to the shared work folder (~/work).", self.switch_to_max)
        ttk.Label(files, text="Shared local file changes also affect your Windows/Mac work folder.", wraplength=720, style="Muted.TLabel").pack(anchor="w")

        status = ttk.Frame(panel, padding=(14, 8))
        status.pack(fill="x", pady=(0, 8))
        status.columnconfigure(0, weight=1)
        status.columnconfigure(1, weight=1)
        ttk.Label(status, textvariable=self.connection_status, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.docker_badge = tk.Label(status, textvariable=self.docker_status, font=("Segoe UI" if WINDOWS else "Helvetica", 10), fg=MUTED, bg=SURFACE, anchor="w", borderwidth=0)
        self.docker_badge.grid(row=0, column=1, sticky="e")
        ttk.Label(status, textvariable=self.user_status, wraplength=760, style="Section.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 3))
        ttk.Label(status, textvariable=self.job_status, style="Muted.TLabel").grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(status, textvariable=self.activity, wraplength=760, style="Muted.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(3, 0))
        self.connection_log = tk.Text(panel, height=2, wrap="word", state="disabled", background="#e7edf4", foreground=MUTED, relief="flat", borderwidth=0, padx=10, pady=3, font=("Segoe UI" if WINDOWS else "Helvetica", 9), highlightthickness=0)
        self.connection_log.pack(fill="x", pady=(0, 8))
        terminal_header = ttk.Frame(panel, style="Page.TFrame")
        terminal_header.pack(fill="x", pady=(0, 5))
        ttk.Label(terminal_header, text="TERMINAL", style="Subtitle.TLabel").pack(side="left")
        ttk.Label(terminal_header, text="Click to type  ·  Passwords stay hidden", style="Subtitle.TLabel").pack(side="right")
        self.terminal_view = tk.Text(panel, width=100, height=24, wrap="none", background="#122033", foreground="#e1e9f3", insertbackground="#8dc2ff", selectbackground="#31567e", relief="flat", borderwidth=0, highlightthickness=1, highlightbackground="#263c55", highlightcolor="#568cca", padx=12, pady=10, font=("Consolas" if WINDOWS else "Menlo", 10), state="disabled")
        self.terminal_view.pack(fill="both", expand=True)
        self.terminal_view.bind("<KeyPress>", self.terminal_key)
        self.terminal_view.bind("<<Paste>>", self.paste_terminal)
        self.terminal_view.bind("<<Cut>>", lambda event: "break")
        self.update_controls()

    def app_key_shortcut(self, event):
        # Command on macOS (Mod2/0x10) and Control on Windows/Linux (0x4)
        # avoid Option-number characters such as # or £ on Mac keyboards.
        if not event.state & (4 | 16):
            return None
        if event.keysym in ("1", "2", "3"):
            tabs = self.sections.tabs()
            self.sections.select(tabs[int(event.keysym) - 1])
            return "break"
        if event.keysym.lower() == "o":
            self.show_files()
            return "break"
        return None

    def update_controls(self):
        idle = not self.active and not self.docker_busy
        local = self.method.get() == "local"

        self.local_radio.configure(state="normal" if idle else "disabled")
        self.remote_radio.configure(state="normal" if idle else "disabled")

        self.choose_button.configure(
            state="normal" if idle and local else "disabled"
        )
        self.id_entry.configure(
            state="normal" if idle and not local else "disabled"
        )

        self.password_entry.configure(state="normal" if idle and not local else "disabled")
        if local:
            self.password.set("")
        self.buttons["Connect"].configure(
            state="normal" if idle else "disabled"
        )

        self.buttons["Connect"].configure(text="Start & connect locally" if local else "Connect to school")
        self.buttons["Show Files"].configure(text="Open local files" if local else "List school files")
        self.buttons["Disconnect"].configure(text="Close connection")
        if not local:
            self.docker_status.set("Docker: not used for School Server")
            self.docker_badge.configure(fg="#555555")
        self.stop_docker_button.configure(
            state="normal" if local and not self.docker_busy and self.compose_path.get() and (not self.active or self.connected) else "disabled"
        )
        ready = self.connected and not self.calculating and not self.disconnecting and not self.docker_busy
        self.max_button.configure(state="normal" if ready and local else "disabled")

        for name in ("Check QE", "Show Files", "Run Calculation", "Run pw.x", "Check current location", "List current directory"):
            self.buttons[name].configure(
                state="normal" if ready else "disabled"
            )

        self.buttons["Stop Calculation"].configure(
            state=(
                "normal"
                if self.connected and not self.disconnecting
                else "disabled"
            )
        )

        self.buttons["Disconnect"].configure(
            state="normal" if self.active and not self.disconnecting else "disabled"
        )
