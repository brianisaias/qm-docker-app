"""interface layout."""
import tkinter as tk

from tkinter import ttk

from .settings import SERVER, WINDOWS

class InterfaceLayout:
    def build_gui(self):
        panel = ttk.Frame(self, padding=12)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="Quantum ESPRESSO", font=("Arial", 19, "bold")).pack(anchor="w")
        ttk.Label(panel, text="Connect to a computer, run a calculation, and manage your work.").pack(anchor="w", pady=(2, 8))
        self.sections = ttk.Notebook(panel)
        self.sections.pack(fill="x", pady=(0, 8))
        connection = ttk.Frame(self.sections, padding=10)
        calculations = ttk.Frame(self.sections, padding=10)
        files = ttk.Frame(self.sections, padding=10)
        for page, title in [(connection, "1. Connection"), (calculations, "2. Calculations"), (files, "3. Files & User")]:
            self.sections.add(page, text=title)
        self.buttons = {}

        def action(parent, key, label, description, callback):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=4)
            button = ttk.Button(row, text=label, command=callback, width=25)
            button.pack(side="left")
            ttk.Label(row, text=description, wraplength=510).pack(side="left", padx=12, fill="x", expand=True)
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
        ttk.Label(local, text="Docker setup file:").pack(side="left")
        ttk.Entry(local, textvariable=self.compose_path, state="readonly").pack(side="left", fill="x", expand=True, padx=8)
        self.choose_button = ttk.Button(local, text="Choose setup file", command=self.choose_yaml)
        self.choose_button.pack(side="left")
        account = ttk.Frame(connection)
        account.pack(fill="x", pady=3)
        ttk.Label(account, text="School Bronco ID:").pack(side="left")
        self.id_entry = ttk.Entry(account, textvariable=self.bronco_id, width=22)
        self.id_entry.pack(side="left", padx=8)
        ttk.Label(account, text=f"Server: {SERVER} | Use GlobalProtect if required.").pack(side="left")
        action(connection, "Connect", "Connect", "Open a terminal on your chosen computer. Local mode starts Quantum Mobile if needed.", self.connect)
        action(connection, "Disconnect", "Close connection", "Interrupt the foreground program and close the terminal. Local Docker stays running.", self.disconnect)
        self.stop_docker_button = action(connection, None, "Shut down local Docker", "Stop the Quantum Mobile container and its work. Does not shut down the school server.", self.stop_docker)

        action(calculations, "Run pw.x", "Start pw.x", "Open Quantum ESPRESSO without an input file. It may wait for input; this is not a completed calculation.", self.run_pw_direct)
        action(calculations, "Run Calculation", "Run an input file", "Choose an existing input-file path on the connected computer and run the calculation.", self.run_calculation)
        action(calculations, "Stop Calculation", "Interrupt calculation", "Send Ctrl+C to the foreground program. Keep the terminal connection open.", self.stop_calculation)
        action(calculations, "Check QE", "Check program location", "Show the current user, folder, and where pw.x is installed. Does not run a calculation.", self.check_qe)

        action(files, "Show Files", "Open local files", "Local: browse, import, rename, and delete shared files. School: list files in the terminal.", self.show_files)
        self.max_button = action(files, None, "Use local max account", "Local only: switch to max if needed and return to the shared work folder (~/work).", self.switch_to_max)
        ttk.Label(files, textvariable=self.user_status, font=("Arial", 10, "bold")).pack(anchor="w", pady=8)
        ttk.Label(files, text="Shared local file changes also affect your Windows/Mac work folder.", wraplength=720).pack(anchor="w")

        status = ttk.LabelFrame(panel, text="Current status", padding=8)
        status.pack(fill="x")
        self.docker_badge = tk.Label(status, textvariable=self.docker_status, font=("Arial", 11, "bold"), fg="#555555", anchor="w")
        self.docker_badge.pack(anchor="w")
        ttk.Label(status, textvariable=self.connection_status, font=("Arial", 11, "bold")).pack(anchor="w")
        ttk.Label(status, textvariable=self.job_status).pack(anchor="w")
        ttk.Label(status, textvariable=self.activity, wraplength=800).pack(anchor="w", pady=(3, 0))
        self.connection_log = tk.Text(panel, height=2, wrap="word", state="disabled")
        self.connection_log.pack(fill="x", pady=6)
        ttk.Label(panel, text="Terminal — click below to type. Password characters remain invisible.").pack(anchor="w")
        self.terminal_view = tk.Text(panel, width=100, height=24, wrap="none", background="#151515", foreground="#eeeeee", insertbackground="#eeeeee", font=("Consolas" if WINDOWS else "Menlo", 10), state="disabled")
        self.terminal_view.pack(fill="both", expand=True, pady=(4, 0))
        self.terminal_view.bind("<KeyPress>", self.terminal_key)
        self.terminal_view.bind("<<Paste>>", self.paste_terminal)
        self.terminal_view.bind("<<Cut>>", lambda event: "break")
        self.update_controls()

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

        self.buttons["Connect"].configure(
            state="normal" if idle else "disabled"
        )

        self.buttons["Connect"].configure(text="Start & connect locally" if local else "Connect to school")
        self.buttons["Show Files"].configure(text="Open local files" if local else "List server files")
        self.buttons["Disconnect"].configure(text="Close connection")
        if not local:
            self.docker_status.set("Docker: not used for School Server")
            self.docker_badge.configure(fg="#555555")
        self.stop_docker_button.configure(
            state="normal" if local and not self.docker_busy and self.compose_path.get() and (not self.active or self.connected) else "disabled"
        )
        ready = self.connected and not self.calculating and not self.disconnecting and not self.docker_busy
        self.max_button.configure(state="normal" if ready and local else "disabled")

        for name in ("Check QE", "Show Files", "Run Calculation", "Run pw.x"):
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
