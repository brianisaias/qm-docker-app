"""calculation controls."""
"""calculations for the main application window."""

import secrets

import shlex

from pathlib import PurePosixPath

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


    def create_calculation_folder(self):
        if not self.connected or self.calculating or self.disconnecting:
            return
        name = simpledialog.askstring(
            "Create calculation folder",
            "Enter one folder name for this calculation.\n\nExample: basic",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name or name in (".", "..") or any(c in name for c in "/\\:\x00\r\n"):
            self.activity.set("Enter one valid folder name without slashes.")
            return
        quoted = shlex.quote(name)
        self.send_command(f"mkdir -p -- {quoted} && cd -- {quoted} && pwd -P")
        self.activity.set(f"Created or entered '{name}'. Use Review required files before running.")
        self.after(500, self.check_current_location)


    def review_calculation_files(self):
        if not self.connected or self.calculating or self.disconnecting:
            return
        self.send_command(
            "printf '\\nCurrent folder: '; pwd -P; "
            "printf '\\nInput and pseudopotential files:\\n'; "
            "find . -maxdepth 1 -type f \\( -name '*.in' -o -name '*.UPF' \\) -print | sort"
        )
        self.activity.set("Reviewing .in and .UPF files in the current calculation folder.")


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

        path = PurePosixPath(filename)
        if path.suffix.lower() != ".in":
            self.activity.set("Choose a Quantum ESPRESSO input file ending in .in.")
            return
        output = str(path.with_suffix(".out"))
        input_arg = shlex.quote(filename)
        output_arg = shlex.quote(output)
        command = (
            f"if [ -f {input_arg} ]; then "
            f"pw.x -input {input_arg} > {output_arg} 2>&1; "
            f"else printf 'INPUT FILE NOT FOUND: %s\\n' {input_arg} >&2; false; fi"
        )
        self.last_input_file = filename
        self.last_output_file = output
        self.start_qe_command(command, output)


    def check_calculation_results(self):
        if not self.connected or self.calculating or self.disconnecting:
            return
        output = simpledialog.askstring(
            "Check calculation results",
            "Enter the output file to check for JOB DONE and total energy.",
            initialvalue=self.last_output_file or "calculation.out",
            parent=self,
        )
        if output is None:
            return
        output = output.strip()
        if not output or "\n" in output or "\r" in output:
            self.activity.set("Enter a valid output file path.")
            return
        target = shlex.quote(output)
        command = (
            f"if [ ! -f {target} ]; then printf 'OUTPUT FILE NOT FOUND: %s\\n' {target}; else "
            f"printf '\\nRESULT CHECK: %s\\n' {target}; "
            f"if grep -q 'JOB DONE\\.' -- {target}; then printf 'STATUS: JOB DONE\\n'; "
            "else printf 'STATUS: JOB DONE not found\\n'; fi; "
            f"energy=$(grep -E '^[[:space:]]*!.*total energy' -- {target} | tail -n 1); "
            "if [ -n \"$energy\" ]; then printf '%s\\n' \"$energy\"; "
            "else printf 'TOTAL ENERGY: not found\\n'; fi; "
            f"printf '\\nLAST 12 LINES\\n'; tail -n 12 -- {target}; fi"
        )
        self.last_output_file = output
        self.send_command(command)
        self.activity.set(f"Checking {output} for JOB DONE and total energy.")


    def run_pw_direct(self):
        self.start_qe_command("pw.x")


    def start_qe_command(self, executable_command, output_file=None):
        if not self.connected or self.calculating or self.disconnecting:
            return
        self.job_marker = "QM_JOB_DONE_" + secrets.token_hex(16)
        self.job_output_file = output_file or ""

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
            self.activity.set(
                "Starting pw.x without an input file. It may wait for input; use Interrupt calculation to stop it."
                if executable_command == "pw.x"
                else f"Running the calculation. Output is being saved to {output_file}."
            )
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
