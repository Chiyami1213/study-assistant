"""The classic (Streamlit) pages inside the native window: until a page is ported it is shown by the old interface running as a hidden local server (`?qt=1` makes it draw without its own menu)."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("STUDY_ASSISTANT_QT_PORT") or 8766)             # not 8765, so the classic window and this one can run side by side


def url(page, course=None, book=None):
    """The address of a classic page inside the native window (a course for Courses, a file to open for Library)."""
    return f"http://localhost:{PORT}/?qt=1&page={page.replace(' ', '%20')}" + (f"&course={course}" if course else "") + (f"&open_book={book}" if book else "")


def open_log():
    """The hidden server's messages go to <data folder>/logs/server_qt.log (kept small: it starts again when it passes 2 MB), so a crash can be looked at afterwards."""
    try:
        from core.database import DATA_DIR
        folder = DATA_DIR / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "server_qt.log"
        if path.exists() and path.stat().st_size > 2 << 20:
            path.write_text("", encoding="utf-8")
        f = open(path, "ab")
        f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} server starting\n".encode("utf-8"))
        f.flush()
        return f
    except OSError:
        return None


def start(log=None):
    """Starts the hidden server (a child process that ends with this one). Returns the process."""
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    if getattr(sys, "frozen", False):                       # the built app: the same exe, started in server mode (launcher_qt.py)
        cmd = [sys.executable, "--server", str(PORT), "--parent", str(os.getpid())]
    else:
        cmd = [sys.executable, "-m", "streamlit", "run", str(PROJECT / "app.py"), "--server.port", str(PORT), "--server.headless", "true",
               "--browser.gatherUsageStats", "false", "--server.fileWatcherType", "none"]
    return subprocess.Popen(cmd, cwd=PROJECT, creationflags=creation, stdout=log or subprocess.DEVNULL, stderr=log or subprocess.DEVNULL, stdin=subprocess.DEVNULL)


def ready(timeout=0.4):
    try:
        urllib.request.urlopen(f"http://localhost:{PORT}/_stcore/health", timeout=timeout)
        return True
    except Exception:
        return False


def wait(seconds=90):
    end = time.time() + seconds
    while time.time() < end:
        if ready():
            return True
        time.sleep(0.3)
    return False


class Keeper:
    """Watches the hidden server this window started: when it stops on its own (a crash), it is started again and the classic pages are loaded again. Gives up after 5 stops in 10 minutes (not a loop of crashes)."""

    def __init__(self, holder, on_restarted, interval_ms=2000):
        from PySide6.QtCore import QTimer
        self.holder, self.on_restarted, self.stops, self.waiting = holder, on_restarted, [], False
        self.timer = QTimer()
        self.timer.timeout.connect(self.check)
        self.timer.start(interval_ms)

    def stop(self):
        self.timer.stop()

    def check(self):
        proc = self.holder["proc"]
        if self.waiting:                                           # restarted: when it answers, the pages are loaded again
            if ready():
                self.waiting = False
                self.on_restarted()
            return
        if proc is None or proc.poll() is None:
            return
        self.stops = [t for t in self.stops if time.time() - t < 600]
        if len(self.stops) >= 5:
            self.timer.stop()
            return
        self.stops.append(time.time())
        log = self.holder.get("log")
        if log:
            try:
                log.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} the server stopped (exit {proc.returncode}); starting it again\n".encode("utf-8"))
                log.flush()
            except OSError:
                pass
        self.holder["proc"] = start(log)
        self.waiting = True
