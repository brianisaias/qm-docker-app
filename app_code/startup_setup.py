"""Install missing terminal dependencies into the interpreter running the app."""
import importlib
import importlib.util
from pathlib import Path
import queue
import subprocess
import sys
import threading


def missing_packages():
    required = ["pyte"]
    if sys.platform == "win32":
        required.append("winpty")
    elif sys.platform == "darwin":
        required.append("pexpect")
    return [name for name in required if importlib.util.find_spec(name) is None]


def install_packages():
    requirements = Path(__file__).resolve().parent.parent / "requirements.txt"
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements),
         "--disable-pip-version-check"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600, **options,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())
    importlib.invalidate_caches()
    missing = missing_packages()
    if missing:
        raise RuntimeError("Packages are still unavailable: " + ", ".join(missing))


def ensure_dependencies():
    if not missing_packages():
        return True
    import tkinter as tk
    from tkinter import ttk
    window = tk.Tk()
    window.title("Quantum ESPRESSO — First-time setup")
    window.geometry("650x350")
    panel = ttk.Frame(window, padding=16)
    panel.pack(fill="both", expand=True)
    message = tk.StringVar(value="Installing missing terminal packages. Internet access is required.")
    ttk.Label(panel, textvariable=message, wraplength=610).pack(anchor="w", pady=8)
    progress = ttk.Progressbar(panel, mode="indeterminate")
    progress.pack(fill="x", pady=8)
    details = tk.Text(panel, height=9, wrap="word", state="disabled")
    details.pack(fill="both", expand=True)
    events = queue.Queue()
    state = {"success": False, "busy": False}

    def worker():
        try:
            install_packages()
            events.put(None)
        except Exception as error:
            events.put(str(error))

    def start():
        state["busy"] = True
        retry.configure(state="disabled")
        message.set("Installing missing terminal packages. This may take a few minutes.")
        progress.start()
        threading.Thread(target=worker, daemon=True).start()

    def close():
        if state["busy"]:
            message.set("Setup is still working. It will finish or report an error before closing.")
        else:
            window.destroy()

    def poll():
        try:
            error = events.get_nowait()
        except queue.Empty:
            window.after(100, poll)
            return
        state["busy"] = False
        progress.stop()
        if error is None:
            state["success"] = True
            window.destroy()
            return
        message.set("Setup failed. Check your internet connection, then Retry. Details are below.")
        details.configure(state="normal")
        details.insert("end", error + "\n")
        details.configure(state="disabled")
        retry.configure(state="normal")
        window.after(100, poll)

    retry = ttk.Button(panel, text="Retry setup", command=start)
    retry.pack(side="left", pady=8)
    ttk.Button(panel, text="Close", command=close).pack(side="right", pady=8)
    window.protocol("WM_DELETE_WINDOW", close)
    window.after(100, poll)
    start()
    window.mainloop()
    return state["success"]
