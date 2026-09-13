"""Run this file in PyCharm. Missing terminal packages are installed on startup."""
from app_code.startup_setup import ensure_dependencies


def main():
    if not ensure_dependencies():
        return
    from app_code.window import QuantumApp
    app = QuantumApp()
    import threading
    from app_code.docker_desktop import start_for_app
    threading.Thread(target=start_for_app, args=(app.events,), daemon=True).start()
    app.mainloop()


if __name__ == "__main__":
    main()
