"""status events."""
import queue

from tkinter import messagebox

from .file_manager import LocalFilesWindow

class StatusEvents:
    def record_activity(self, *_):
        if hasattr(self, "connection_log"):
            self.connection_log.configure(state="normal")
            self.connection_log.insert("end", self.activity.get() + "\n")
            self.connection_log.see("end")
            self.connection_log.configure(state="disabled")


    def report_callback_exception(self, exception_type, value, traceback):
        # Make GUI callback failures visible instead of leaving an inert button.
        self.activity.set(f"App error: {exception_type.__name__}: {value}")
        messagebox.showerror("App error", f"{exception_type.__name__}: {value}", parent=self)


    def close_app(self):
        self.password.set("")
        if self.login_secret is not None:
            self.login_secret.clear()
        if self.active:
            self.closing = True
            self.disconnect()
        else:
            self.destroy()


    def poll_events(self):
        redraw = False

        try:
            while True:
                kind, value = self.events.get_nowait()

                if kind == "network_checked":
                    self.network_checking = False
                    self.network_approved, message = value
                    self.network_status.set(message)
                    self.activity.set(message)
                    if not self.network_approved:
                        self.password.set("")
                    self.update_controls()

                elif kind == "local_files_ready":
                    folder, writable = value
                    LocalFilesWindow(self, folder, writable)
                    self.activity.set("Local file manager opened. Changes affect your shared work folder.")

                elif kind == "local_started":
                    self.docker_status.set("Docker: RUNNING")
                    self.docker_badge.configure(fg="#16723a")
                    self.activity.set("Docker started. Opening the Max terminal…")

                elif kind == "docker_checked":
                    self.docker_checking = False
                    path, revision, result = value
                    if self.method.get() == "local" and path == self.compose_path.get() and revision == self.docker_revision and not self.docker_busy:
                        self.docker_status.set(result[0])
                        self.docker_badge.configure(fg=result[1])

                elif kind == "docker_stopped":
                    self.docker_busy = False
                    self.docker_status.set(value[0])
                    self.docker_badge.configure(fg=value[1])
                    self.activity.set(value[0] + " — Docker Desktop itself remains open.")
                    self.update_controls()

                elif kind == "docker_stop_error":
                    self.docker_busy = False
                    self.docker_status.set("Docker: STOP FAILED — state not confirmed")
                    self.docker_badge.configure(fg="#ad2424")
                    self.activity.set(value)
                    self.update_controls()

                elif kind == "output":
                    self.process_output(value)
                    redraw = True

                elif kind == "activity":
                    self.activity.set(value)

                elif kind == "focus":
                    self.terminal_view.focus_set()

                elif kind == "error":
                    self.activity.set(value)

                elif kind == "disconnect_attempt_finished":
                    self.disconnecting = False
                    self.update_controls()

                elif kind == "closed":
                    self.password.set("")
                    if self.login_secret is not None:
                        self.login_secret.clear()
                        self.login_secret = None
                    was_connected = self.connected
                    if self.calculating:
                        self.job_status.set("Calculation: session closed — completion not confirmed")
                    self.active = False
                    self.connected = False
                    self.calculating = False
                    self.disconnecting = False
                    self.connection_status.set("Terminal: DISCONNECTED")
                    self.user_status.set("Terminal user: not connected")
                    self.location_marker = ""
                    self.activity.set("Session closed." if was_connected else "Connection ended before it became ready. See the connection log and terminal above.")
                    self.update_controls()

        except queue.Empty:
            pass

        if redraw:
            self.render_terminal()

        if self.closing and not self.active:
            self.destroy()
            return

        self.after(100, self.poll_events)
