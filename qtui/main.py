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
    from PySide6.QtWebEngineCore import QWebEngineProfile
    from core.database import DATA_DIR
    profile = QWebEngineProfile.defaultProfile()                       # what the web views keep lives with the user's other files, not in the user profile
    folder = DATA_DIR / "webview_qt"
    folder.mkdir(parents=True, exist_ok=True)
    profile.setPersistentStoragePath(str(folder))
    profile.setCachePath(str(folder / "cache"))
    holder = {"proc": None, "log": None}
    if use_server and not server.ready():
        holder["log"] = server.open_log()
        holder["proc"] = server.start(holder["log"])
        atexit.register(lambda: holder["proc"] and holder["proc"].poll() is None and holder["proc"].terminate())
    from qtui.window import MainWindow
    win = MainWindow(use_server=use_server)
    win.show()
    keeper = server.Keeper(holder, win.reload_classic) if holder["proc"] else None     # a crashed hidden server is started again (the classic pages would stay on "Connection error")
    code = app.exec()
    if keeper:
        keeper.stop()
    proc = holder["proc"]
    if proc is not None and proc.poll() is None:
        try:
            import launcher                                           # stops the server and the page renderers it started
            launcher.stop_server(proc)
        except Exception:
            proc.terminate()
    return code


if __name__ == "__main__":
    sys.exit(run())
