"""calculation controls."""
"""calculations for the main application window."""

import secrets

import shlex

from tkinter import simpledialog

class CalculationControls:
    def check_qe(self):
        self.send_command(
            "printf '\\nUser: '; whoami; "
            "printf 'Folder: '; pwd; "
            "printf 'pw.x: '; command -v pw.x"
        )


    def switch_to_max(self):
        if self.method.get() != "local" or not self.connected or self.calculating or self.disconnecting:
            return
        # Reuse max's existing shell if already logged in, avoiding nested su sessions.
        confirm = "printf '\\n" + self.max_marker + "\\n'"
        login = "cd ~/work && " + confirm + " && exec bash -i"
        command = (
            'if [ "$(id -un)" = max ]; then cd ~/work && ' + confirm
            + "; else exec su - max -c " + shlex.quote(login) + "; fi"
        )
        try:
            self.user_status.set("Local user: checking / switching…")
            self.activity.set("Switch to max requested. The terminal will confirm max in ~/work.")
            self.send(command + "\r")
        except Exception as error:
            self.user_status.set("Local user: switch not confirmed")
            self.activity.set(str(error))


    def run_calculation(self):
        if not self.connected or self.calculating:
            return

        location = (
            "inside the local container"
            if self.method.get() == "local"
            else "on the school server"
        )

        filename = simpledialog.askstring(
            "Run Quantum ESPRESSO",
            f"Enter the input file path {location}.\n\n"
            "Use an absolute path or a path relative to the current folder.\n"
            "Example: calculation.in\n\n"
            "This does not upload a file from Windows.",
            parent=self,
        )

        if filename is None:
            return

        filename = filename.strip()

        if not filename or "\n" in filename or "\r" in filename:
            self.activity.set("Enter a valid input file path.")
            return

        self.start_qe_command(f"pw.x -in {shlex.quote(filename)}")


    def run_pw_direct(self):
        self.start_qe_command("pw.x")


    def start_qe_command(self, executable_command):
        if not self.connected or self.calculating or self.disconnecting:
            return
        self.job_marker = "QM_JOB_DONE_" + secrets.token_hex(16)

        # The wrapper survives Ctrl+C long enough to report the job's exit code.
        # pw.x receives the foreground terminal interrupt normally.
        script = (
            "trap ':' INT; "
            + executable_command + "; "
            + "result=$?; "
            + f"printf '\\n{self.job_marker}:%s\\n' \"$result\""
        )

        command = "sh -c " + shlex.quote(script)

        try:
            self.calculating = True
            self.job_status.set("Calculation: RUNNING")
            self.activity.set("Starting pw.x. It may display Waiting for input; use Stop Calculation to interrupt it." if executable_command == "pw.x" else "Starting calculation. Output appears below.")
            self.update_controls()
            self.send(command + "\r")

        except Exception as error:
            self.calculating = False
            self.job_status.set("Calculation: could not start")
            self.activity.set(str(error))
            self.update_controls()


    def stop_calculation(self):
        if not self.connected:
            return

        try:
            self.send("\x03")
            self.job_status.set("Calculation: STOP REQUESTED — waiting for confirmation")
            self.activity.set(
                "Ctrl+C sent. Waiting for the foreground program to return."
            )
        except Exception as error:
            self.activity.set(str(error))
