"""Starts the native Study Assistant: `python run_qt.py`."""
import atexit
import sys


def run(argv=None):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from core.database import init_db
    from qtui import server

    argv = list(sys.argv if argv is None else argv)
    use_server = "--no-server" not in argv
    app = QApplication(argv)
    app.setApplicationName("Study Assistant")
    init_db()
    proc = None
    if use_server and not server.ready():
        proc = server.start()
        atexit.register(lambda: proc.poll() is None and proc.terminate())
    from qtui.window import MainWindow
    win = MainWindow(use_server=use_server)
    win.show()
    code = app.exec()
    if proc is not None and proc.poll() is None:
        proc.terminate()
    return code


if __name__ == "__main__":
    sys.exit(run())
