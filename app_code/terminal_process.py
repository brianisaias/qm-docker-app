"""Windows and macOS pseudo-terminal adapters."""
from .settings import WINDOWS, MAC

class TerminalProcess:
    """A real pseudo-terminal for either Docker or SSH."""

    def __init__(self, arguments):
        if WINDOWS:
            try:
                from winpty import PtyProcess
            except ImportError:
                raise RuntimeError(
                    "Run this in PyCharm's Terminal:\n"
                    "python -m pip install pywinpty pyte"
                ) from None

            self.process = PtyProcess.spawn(
                arguments,
                dimensions=(24, 100),
            )

        elif MAC:
            try:
                import pexpect
            except ImportError:
                raise RuntimeError(
                    "Run this in PyCharm's Terminal:\n"
                    "python -m pip install pexpect pyte"
                ) from None

            self.process = pexpect.spawn(
                arguments[0],
                arguments[1:],
                encoding="utf-8",
                codec_errors="replace",
                dimensions=(24, 100),
            )

        else:
            raise RuntimeError("This app supports Windows and macOS.")

    def read(self):
        if WINDOWS:
            # Avoid waiting forever when the child has already exited.
            import select

            readable, _, _ = select.select(
                [self.process.fileobj], [], [], 0.2
            )

            if not readable:
                if not self.alive():
                    raise EOFError
                return ""

            return self.process.read(4096)

        import pexpect

        try:
            return self.process.read_nonblocking(4096, timeout=0.2)
        except pexpect.TIMEOUT:
            return ""
        except pexpect.EOF:
            raise EOFError

    def write(self, text):
        if WINDOWS:
            self.process.write(text)
        else:
            self.process.send(text)

    def alive(self):
        return self.process.isalive()

    def close(self):
        self.process.close()


