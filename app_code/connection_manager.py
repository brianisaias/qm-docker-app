from .docker_desktop import ensure_docker_ready
"""connection manager."""
"""connections for the main application window."""

import re

import secrets

import threading

import time

from pathlib import Path

from .settings import SERVER, SERVICE

from .system_tools import run_command, find_program

from .terminal_process import TerminalProcess
from .ssh_login import LoginSecret
from .school_network import WARNING, detect_school_network

class ConnectionControls:
    def connect(self):
        if self.active:
            self.activity.set("A session is already active or starting. Disconnect it before reconnecting.")
            return

        selected_method = self.method.get()
        path = self.compose_path.get()
        username = self.bronco_id.get().strip()
        self.activity.set("Connect clicked: " + ("Local Docker" if selected_method == "local" else "School Server"))

        if selected_method == "local":
            if not path:
                self.choose_yaml()
                path = self.compose_path.get()

            if not path:
                self.activity.set("Connection canceled: no YAML file selected.")
                return

            if not Path(path).is_file():
                self.activity.set("The selected YAML file does not exist.")
                return

        else:
            if not self.network_approved or self.network_checking:
                self.password.set("")
                self.activity.set(WARNING)
                return
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", username):
                self.password.set("")
                self.activity.set("Enter your Bronco ID without @ or spaces.")
                return

        try:
            import pyte

            self.screen = pyte.Screen(100, 24)
            self.stream = pyte.Stream(self.screen)

        except ImportError:
            self.password.set("")
            self.activity.set(
                "Missing terminal display package. "
                "Run: python -m pip install pyte"
            )
            return

        self.login_secret = LoginSecret(self.password.get()) if selected_method == "remote" else None
        self.password.set("")
        self.terminal = None
        self.active = True
        self.connected = False
        self.calculating = False
        self.disconnecting = False
        self.cancel_connection = False
        self.received = ""
        self.location_marker = ""
        self.user_status.set("Current user: checking…")
        self.job_marker = ""
        self.ready_marker = "QM_READY_" + secrets.token_hex(16)

        self.connection_status.set("Terminal: CONNECTING — not connected yet")
        self.activity.set("Connecting…")
        if selected_method == "local":
            self.docker_revision += 1
            self.docker_status.set("Docker: STARTING / CHECKING…")
            self.docker_badge.configure(fg="#9a6700")
        self.render_terminal()
        self.update_controls()

        threading.Thread(
            target=self.connection_worker,
            args=(selected_method, path, username, self.ready_marker),
            daemon=True,
        ).start()
        self.after(15000, self.connection_wait_notice)


    def connection_wait_notice(self):
        if self.active and not self.connected and not self.disconnecting:
            self.activity.set(
                "Still waiting for the terminal session. Check the terminal for an SSH "
                "password or host-key prompt, or the connection log for Docker setup progress."
            )


    def connection_worker(self, method, path, username, marker):
        terminal = None

        try:
            if method == "local":
                self.events.put(("activity", "Locating Docker and checking the selected setup…"))
                docker = ensure_docker_ready(
                    lambda text: self.events.put(("activity", text)),
                    canceled=lambda: self.cancel_connection,
                )
                base = [docker, "compose", "-f", path]

                ids = run_command(
                    base + ["ps", "--all", "--quiet", SERVICE]
                ).splitlines()

                if not ids:
                    self.events.put(
                        (
                            "activity",
                            "Creating Quantum Mobile. The image download may "
                            "take several minutes.",
                        )
                    )
                    run_command(
                        base + ["up", "-d", SERVICE],
                        timeout=1800,
                    )

                    ids = run_command(
                        base + ["ps", "--all", "--quiet", SERVICE]
                    ).splitlines()

                if len(ids) != 1:
                    raise RuntimeError(
                        "Expected one Quantum Mobile container for this YAML."
                    )

                container = ids[0]

                running = run_command(
                    [
                        docker,
                        "inspect",
                        "--format",
                        "{{.State.Running}}",
                        container,
                    ]
                )

                if running != "true":
                    run_command(base + ["start", SERVICE])

                confirmed = run_command([
                    docker, "inspect", "--format", "{{.State.Running}}", container
                ])
                if confirmed != "true":
                    raise RuntimeError("Docker did not stay running. Check Docker Desktop for the container error.")
                self.events.put(("local_started", ""))

                shell_command = (
                    "cd ~/work && printf '\\n%s\\n' "
                    + marker
                    + " && exec bash -i"
                )

                arguments = [
                    docker,
                    "exec",
                    "-it",
                    "--user",
                    "root",
                    container,
                    "su",
                    "-",
                    "max",
                    "-c",
                    shell_command,
                ]

            else:
                approved, network_message = detect_school_network()
                self.events.put(("network_checked", (approved, network_message)))
                if not approved:
                    raise RuntimeError(WARNING)
                ssh = find_program("ssh")

                remote_command = (
                    "printf '\\n%s\\n' "
                    + marker
                    + '; exec "${SHELL:-/bin/sh}" -l'
                )

                arguments = [
                    ssh,
                    "-tt",
                    "-o",
                    "ConnectTimeout=20",
                    "-o",
                    "NumberOfPasswordPrompts=1",
                    "-o",
                    "ServerAliveInterval=15",
                    "-o",
                    "ServerAliveCountMax=3",
                    f"{username}@{SERVER}",
                    remote_command,
                ]

                self.events.put(
                    (
                        "activity",
                        "Answer the normal SSH prompts in the terminal below.",
                    )
                )

            if self.cancel_connection:
                return

            terminal = TerminalProcess(arguments)
            self.events.put(("activity", "Terminal process opened. Waiting for the session to confirm it is ready…"))
            self.terminal = terminal
            self.events.put(("focus", ""))

            while True:
                if (self.login_secret is not None and self.login_secret.sent_at is not None
                        and time.monotonic() - self.login_secret.sent_at > 60):
                    raise RuntimeError("School authentication timed out.")
                try:
                    output = terminal.read()
                except EOFError:
                    break

                if output:
                    if method == "remote" and self.login_secret is not None:
                        output = self.login_secret.process(output, terminal, marker)
                        if marker in output:
                            self.login_secret.clear()
                            self.login_secret = None
                    if output:
                        self.events.put(("output", output))
                elif not terminal.alive():
                    break

        except Exception as error:
            self.events.put(("error", "School connection failed. Check the network and login details." if method == "remote" else str(error)))
            if terminal and method == "remote":
                try:
                    terminal.close()
                except Exception:
                    pass

        finally:
            if self.login_secret is not None:
                self.login_secret.clear()
                self.login_secret = None
            if terminal:
                if terminal.alive():
                    self.events.put(
                        (
                            "error",
                            "Terminal reading stopped while the process is "
                            "still active. Use Disconnect.",
                        )
                    )

                    while terminal.alive():
                        time.sleep(0.2)

                try:
                    terminal.close()
                except Exception as error:
                    self.events.put(("error", f"Cleanup error: {error}"))

            self.events.put(("closed", ""))


    def send(self, text):
        if not self.terminal or not self.active:
            raise RuntimeError("No terminal connection is open.")

        with self.write_lock:
            self.terminal.write(text)


    def send_command(self, command):
        if not self.connected or self.calculating:
            return

        try:
            self.send(command + "\r")
        except Exception as error:
            self.activity.set(str(error))


    def list_current_directory(self):
        """List the active shell folder, including hidden files, on either connection."""
        if not self.connected or self.calculating or self.disconnecting or self.docker_busy:
            return
        self.send_command("pwd -P; ls -lah")


    def check_current_location(self):
        """Query the existing shell, so cd and user switches are respected."""
        if not self.connected or self.calculating or self.disconnecting:
            return
        self.location_marker = "QM_LOCATION_" + secrets.token_hex(16)
        self.user_status.set("Current user: checking…")
        # Hex preserves spaces, Unicode and terminal wrapping. The marker plus
        # encoded fields cannot be mistaken for the terminal's command echo.
        command = (
            "printf '\\n%s:' " + self.location_marker
            + "; id -un | od -An -tx1 | tr -d ' \\n'; printf ':'; "
            + "pwd -P | od -An -tx1 | tr -d ' \\n'; printf ':END\\n'"
        )
        try:
            self.send(command + "\r")
            marker = self.location_marker
            def expired():
                if self.location_marker == marker:
                    self.location_marker = ""
                    self.user_status.set("Current user: unavailable — check again at a shell prompt")
            self.after(10000, expired)
        except Exception as error:
            self.location_marker = ""
            self.user_status.set("Current user: unavailable")
            self.activity.set(f"Location check failed: {error}")


    def disconnect(self):
        if not self.active or self.disconnecting:
            return

        self.password.set("")
        if self.login_secret is not None:
            self.login_secret.clear()
        self.disconnecting = True
        self.cancel_connection = True
        self.connection_status.set("Terminal: DISCONNECTING…")
        self.activity.set("Closing the terminal session. Local Docker stays running unless you use Stop Docker Container.")
        self.update_controls()

        threading.Thread(
            target=self.disconnect_worker,
            daemon=True,
        ).start()


    def disconnect_worker(self):
        try:
            # During a Docker setup, wait for its current command to finish.
            # The connection worker will then honor cancel_connection.
            if self.terminal is None:
                self.events.put(
                    (
                        "activity",
                        "Connection cancellation requested. "
                        "Waiting for the current setup command to finish.",
                    )
                )
                return

            self.send("\x03")
            time.sleep(1)

            if self.terminal.alive():
                self.send("exit\r")

            deadline = time.monotonic() + 10

            while self.terminal.alive() and time.monotonic() < deadline:
                time.sleep(0.1)

            if self.terminal.alive():
                self.events.put(
                    (
                        "error",
                        "The session has not exited. A program may be ignoring "
                        "Ctrl+C. Inspect the terminal, then try Disconnect again.",
                    )
                )

        except Exception as error:
            self.events.put(("error", f"Disconnect error: {error}"))

        finally:
            self.events.put(("disconnect_attempt_finished", ""))
