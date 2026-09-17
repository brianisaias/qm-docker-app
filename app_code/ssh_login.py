"""Transient SSH password handling; credentials never enter UI output events."""
import re
import threading
import time


class LoginSecret:
    def __init__(self, password):
        self.password = password
        self.sent = False
        self.sent_at = None
        self.prompt = ""
        self.lock = threading.RLock()

    def clear(self):
        with self.lock:
            self.password = ""
            self.prompt = ""

    def process(self, output, terminal, ready_marker):
        with self.lock:
            self.prompt = (self.prompt + output)[-4096:]
            # Once a password is submitted, suppress authentication output
            # entirely, including any echo split across terminal reads. Resume
            # only at the random session-ready marker, after authentication.
            if self.sent:
                if ready_marker in self.prompt:
                    remaining = self.prompt.split(ready_marker, 1)[1]
                    self.clear()
                    return "\r\n" + ready_marker + remaining
                if re.search(r"(?i)permission denied|authentication failed|password.*:\s*$", self.prompt):
                    self.clear()
                    raise RuntimeError("School authentication failed. Close the connection and try again.")
                # MFA and other prompts can still be handled by keyboard, but
                # never risk displaying the credential echo.
                return ""
            if self.password and re.search(r"(?i)(?:^|[\r\n])[^\r\n]*password[^\r\n]*:\s*$", self.prompt):
                self.sent = True
                self.sent_at = time.monotonic()
                self.prompt = ""
                terminal.write(self.password + "\r")
                # Drop the secret immediately after handing it to SSH. Output
                # stays suppressed until authentication succeeds or fails.
                self.clear()
                return "\r\nAuthenticating school login…\r\n"
            if ready_marker in self.prompt:
                self.clear()
            return output
