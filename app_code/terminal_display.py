"""terminal display."""
import re

import secrets

class TerminalDisplay:
    def terminal_key(self, event):
        if event.state & 4 and event.keysym.lower() == "v":
            return self.paste_terminal()

        special = {
            "Return": "\r",
            "BackSpace": "\x7f",
            "Tab": "\t",
            "Up": "\x1b[A",
            "Down": "\x1b[B",
            "Right": "\x1b[C",
            "Left": "\x1b[D",
        }

        text = special.get(event.keysym, event.char)

        if event.state & 4 and event.keysym.lower() == "c":
            text = "\x03"

        if text and self.terminal and self.active:
            try:
                self.send(text)
            except Exception as error:
                self.activity.set(f"Terminal input error: {error}")

        # Only the terminal's own echo is displayed, not local keystrokes.
        return "break"


    def paste_terminal(self, event=None):
        try:
            if self.terminal and self.active:
                self.send(self.clipboard_get())
        except Exception as error:
            self.activity.set(f"Paste error: {error}")

        return "break"


    def process_output(self, output):
        self.received = (self.received + output)[-16000:]
        # Windows ConPTY may use cursor movement instead of newline characters.
        # Read the rendered screen as well as the raw stream for confirmation.
        if self.stream:
            self.stream.feed(output)
        rendered_rows = [row.strip() for row in self.screen.display] if self.screen else []
        if self.max_marker in rendered_rows:
            self.check_current_location()
            self.max_marker = "QM_MAX_" + secrets.token_hex(16)

        if not self.connected:
            pattern = (
                r"(?:^|\n)"
                + re.escape(self.ready_marker)
                + r"\r?\n"
            )

            if self.ready_marker and (re.search(pattern, self.received) or self.ready_marker in rendered_rows):
                self.connected = True

                label = (
                    "Local Docker"
                    if self.method.get() == "local"
                    else "School Server"
                )

                self.connection_status.set(f"Terminal: CONNECTED — {label}")
                self.check_current_location()
                self.activity.set(
                    "Ready. Check QE, show files, or run an input file."
                )
                self.update_controls()

        if self.connected and not self.disconnecting and self.location_marker:
            pattern = re.escape(self.location_marker) + r":([0-9a-f\s]+):([0-9a-f\s]+):END"
            match = re.search(pattern, self.received)
            if match is None:
                match = re.search(pattern, "".join(rendered_rows))
            if match:
                try:
                    user, folder = (
                        bytes.fromhex(field).decode("utf-8").removesuffix("\n")
                        for field in match.groups()
                    )
                    if not user or not folder.startswith("/"):
                        raise ValueError("Missing user or absolute folder")
                    self.user_status.set(f"Current user: {user} | Folder: {folder}")
                except (ValueError, UnicodeDecodeError):
                    self.user_status.set("Current user: unavailable")
                self.location_marker = ""

        if self.calculating and self.job_marker:
            pattern = (
                r"(?:^|\n)"
                + re.escape(self.job_marker)
                + r":(\d+)\r?\n"
            )
            match = re.search(pattern, self.received)
            if match is None:
                for row in rendered_rows:
                    match = re.fullmatch(re.escape(self.job_marker) + r":(\d+)", row)
                    if match:
                        break

            if match:
                code = int(match.group(1))
                self.calculating = False
                self.job_status.set(f"Calculation: FINISHED — exit code {code}")

                if code == 0:
                    self.activity.set(
                        "Calculation process finished with exit code 0. "
                        "Review the output for results."
                    )
                else:
                    self.activity.set(
                        f"Calculation ended with exit code {code}. "
                        "Review the terminal output."
                    )

                self.update_controls()

        if self.stream:
            if self.method.get() == "remote" and not self.connected:
                row = self.screen.display[self.screen.cursor.y].strip()
                if re.search(r"(?:password|passphrase).*[:：]\s*$", row, re.I):
                    self.activity.set(
                        "PASSWORD REQUIRED: click the terminal, type your password, "
                        "then press Enter. Typed characters stay invisible."
                    )
                elif "yes/no" in row.lower():
                    self.activity.set(
                        "SSH HOST KEY: read and verify the server fingerprint "
                        "in the terminal before answering."
                    )


    def render_terminal(self):
        if not self.screen:
            return

        # pyte interprets terminal escape sequences instead of printing them.
        text = "\n".join(self.screen.display)

        self.terminal_view.configure(state="normal")
        self.terminal_view.delete("1.0", "end")
        self.terminal_view.insert("1.0", text)

        cursor = self.screen.cursor
        self.terminal_view.mark_set(
            "insert",
            f"{cursor.y + 1}.{cursor.x}",
        )

        self.terminal_view.configure(state="disabled")
        self.terminal_view.see("insert")
