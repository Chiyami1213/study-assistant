"""The classic (Streamlit) pages inside the native window: until a page is ported it is shown by the old interface running as a hidden local server (`?qt=1` makes it draw without its own menu)."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("STUDY_ASSISTANT_QT_PORT") or 8766)             # not 8765, so the classic window and this one can run side by side


def url(page, course=None):
    """The address of a classic page inside the native window."""
    return f"http://localhost:{PORT}/?qt=1&page={page.replace(' ', '%20')}" + (f"&course={course}" if course else "")


def start():
    """Starts the hidden server (a child process that ends with this one). Returns the process."""
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    cmd = [sys.executable, "-m", "streamlit", "run", str(PROJECT / "app.py"), "--server.port", str(PORT), "--server.headless", "true",
           "--browser.gatherUsageStats", "false", "--server.fileWatcherType", "none"]
    return subprocess.Popen(cmd, cwd=PROJECT, creationflags=creation, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)


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
