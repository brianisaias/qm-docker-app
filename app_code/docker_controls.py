"""docker controls."""
"""local controls for the main application window."""

import json

import threading

from pathlib import Path

from tkinter import filedialog

from .settings import SERVICE, SETTINGS_FOLDER, SETTINGS_FILE

from .system_tools import run_command, find_program

from .file_manager import resolve_shared_work

class LocalControls:
    def load_path(self):
        try:
            return SETTINGS_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return ""


    @staticmethod
    def inspect_docker(path):
        if not Path(path).is_file():
            raise RuntimeError("Choose an existing YAML file.")
        docker = find_program("docker")
        ids = run_command([docker, "compose", "-f", path, "ps", "--all", "--quiet", SERVICE]).splitlines()
        if not ids:
            return docker, None, {}
        if len(ids) != 1:
            raise RuntimeError("Expected one Quantum Mobile container.")
        state = json.loads(run_command([docker, "inspect", "--format", "{{json .State}}", ids[0]]))
        return docker, ids[0], state


    @staticmethod
    def docker_description(container, state):
        if container is None:
            return "Docker: NOT CREATED — click Start / Connect", "#555555"
        if state.get("Paused"):
            return "Docker: PAUSED", "#9a6700"
        if state.get("Restarting"):
            return "Docker: RESTARTING", "#9a6700"
        if state.get("Running"):
            health = state.get("Health", {}).get("Status", "")
            extra = f" — health: {health}" if health else ""
            return "Docker: RUNNING" + extra, "#16723a"
        return "Docker: STOPPED", "#ad2424"


    def refresh_docker_status(self):
        path = self.compose_path.get()
        if self.method.get() == "remote":
            self.docker_status.set("Docker: not used for School Server")
            self.docker_badge.configure(fg="#555555")
        elif not path:
            self.docker_status.set("Docker: choose a YAML file")
        elif not self.docker_busy and not self.docker_checking:
            self.docker_checking = True
            revision = self.docker_revision
            def check():
                try:
                    _, container, state = self.inspect_docker(path)
                    result = self.docker_description(container, state)
                except Exception as error:
                    result = ("Docker: STATUS UNAVAILABLE — " + str(error).splitlines()[0], "#9a6700")
                self.events.put(("docker_checked", (path, revision, result)))
            threading.Thread(target=check, daemon=True).start()
        self.after(5000, self.refresh_docker_status)


    def stop_docker(self):
        if self.method.get() != "local" or self.docker_busy:
            return
        path = self.compose_path.get()
        self.docker_busy = True
        self.docker_revision += 1
        self.docker_status.set("Docker: STOPPING…")
        self.docker_badge.configure(fg="#9a6700")
        self.activity.set("Stopping the local container. This interrupts its calculations.")
        self.update_controls()
        def stop():
            try:
                docker, container, state = self.inspect_docker(path)
                if container and state.get("Running"):
                    run_command([docker, "stop", container])
                _, container, state = self.inspect_docker(path)
                self.events.put(("docker_stopped", self.docker_description(container, state)))
            except Exception as error:
                self.events.put(("docker_stop_error", str(error)))
        threading.Thread(target=stop, daemon=True).start()


    def choose_yaml(self):
        selected = filedialog.askopenfilename(
            title="Choose your Docker Compose YAML file",
            filetypes=[("YAML files", "*.yml *.yaml"), ("All files", "*.*")],
        )

        if selected:
            self.compose_path.set(selected)

            try:
                SETTINGS_FOLDER.mkdir(parents=True, exist_ok=True)
                SETTINGS_FILE.write_text(selected, encoding="utf-8")
            except OSError as error:
                self.activity.set(f"Selected, but could not save the path: {error}")


    def show_files(self):
        if self.method.get() != "local":
            self.send_command("pwd; ls -lh")
            return
        path = self.compose_path.get()
        self.activity.set("Opening the local shared work folder…")
        def locate():
            try:
                docker, container, _ = self.inspect_docker(path)
                if container is None:
                    raise RuntimeError("Connect to Local Docker first.")
                mounts = json.loads(run_command([docker, "inspect", "--format", "{{json .Mounts}}", container]))
                folder, writable = resolve_shared_work(mounts)
                self.events.put(("local_files_ready", (folder, writable)))
            except Exception as error:
                self.events.put(("error", "Local files: " + str(error)))
        threading.Thread(target=locate, daemon=True).start()
