"""Desktop launcher: opens Study Assistant in its own window (no Chrome / Edge tab).

    python launcher.py            run the window from source
    StudyAssistant.exe            the same, packaged by build_exe.py

The app's code and data are always read from the project folder, so edits made in VS Code show up here and
everything saved in the app lands in <project>/data. The app is a Streamlit server (started as a hidden
child process of this program) shown inside a native WebView2 window.
"""
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

PORT = int(os.environ.get("STUDY_ASSISTANT_PORT") or 8765)         # the variable is for tests: a second copy on another port
TITLE = "Study Assistant"


def find_project():
    """The folder that holds app.py: STUDY_ASSISTANT_HOME, project_path.txt, or the exe's folder and its parents."""
    if os.environ.get("STUDY_ASSISTANT_HOME"):
        return Path(os.environ["STUDY_ASSISTANT_HOME"])
    here = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    pointer = here / "project_path.txt"
    if pointer.exists():
        p = Path(pointer.read_text(encoding="utf-8").strip())
        if (p / "app.py").exists():
            return p
    for p in (here, *here.parents):
        if (p / "app.py").exists():
            return p
    raise SystemExit("Study Assistant: project folder (with app.py) not found. "
                     "Set STUDY_ASSISTANT_HOME or write its path into project_path.txt next to the exe.")


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def stop_server(server):
    """Stop the server this program started and anything it started (the page renderers): a normal terminate, no taskkill."""
    if not server or server.poll() is not None:
        return
    try:
        import psutil
        procs = psutil.Process(server.pid).children(recursive=True)
    except Exception:
        procs = []
    server.terminate()
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    try:
        server.wait(timeout=5)
    except Exception:
        server.kill()


def watch_parent(parent_pid):
    """If the window program disappears without cleaning up (a crash), the server and its renderers stop themselves."""
    def loop():
        try:
            import psutil
        except Exception:
            return
        while True:
            time.sleep(3)
            if not psutil.pid_exists(parent_pid):
                try:
                    for p in psutil.Process().children(recursive=True):
                        p.terminate()
                finally:
                    os._exit(0)

    threading.Thread(target=loop, daemon=True).start()


def run_server(port, parent_pid=None):
    """Child mode: run the Streamlit server in this process (needs the main thread for its signal handlers)."""
    if parent_pid:
        watch_parent(parent_pid)
    project = find_project()
    os.chdir(project)
    sys.path.insert(0, str(project))
    from streamlit.web import bootstrap
    options = {"server.headless": True, "server.port": port, "server.address": "127.0.0.1",
               "global.developmentMode": False, "browser.gatherUsageStats": False,
               "server.fileWatcherType": "auto", "server.runOnSave": True,
               "client.toolbarMode": "minimal",
               "server.disconnectedSessionTTL": 86400,      # a window that lost its connection (sleep, a locked screen, a busy computer) comes back to the same page for a day, not 2 minutes
               "server.enableStaticServing": True}
    bootstrap.load_config_options(options)
    bootstrap.run(str(project / "app.py"), False, [], options)


SPLASH = """<html><body style="margin:0;background:#0e1117;color:#c9d1d9;font-family:Segoe UI,sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh"><div style="text-align:center">
<div style="font-size:26px;font-weight:600;margin-bottom:10px">Study Assistant</div>
<div style="opacity:.6">Starting...</div></div></body></html>"""


class Api:
    """Called from the page: a Note Reader tab dragged out of the window opens as its own window."""

    def open_window(self, url):
        import webview
        webview.create_window(TITLE, url, width=1100, height=850, min_size=(600, 400), background_color="#0e1117", js_api=Api())

    def toggle_fullscreen(self):
        """F11 in the page: the window that has the focus goes full screen, or back to a window."""
        import webview
        window = webview.active_window() or (webview.windows[0] if webview.windows else None)
        if window:
            window.toggle_fullscreen()


def start_server(project, log=None):
    """The hidden Streamlit server as a child process. From the exe its messages go to <data folder>\\logs\\server.log; from `python run.py` they print here."""
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    cmd = [sys.executable, "--server", str(PORT), "--parent", str(os.getpid())] if getattr(sys, "frozen", False) \
        else [sys.executable, str(Path(__file__).resolve()), "--server", str(PORT), "--parent", str(os.getpid())]
    quiet = getattr(sys, "frozen", False)
    return subprocess.Popen(cmd, cwd=project, creationflags=creation if quiet else 0,
                            stdout=(log or subprocess.DEVNULL) if quiet else None,
                            stderr=(log or subprocess.DEVNULL) if quiet else None, stdin=subprocess.DEVNULL)


def open_log(data_dir):
    """The server's log file (kept small: it starts again when it passes 2 MB)."""
    try:
        folder = data_dir / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "server.log"
        if path.exists() and path.stat().st_size > 2 << 20:
            path.write_text("", encoding="utf-8")
        f = open(path, "ab")
        f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} server starting\n".encode("utf-8"))
        f.flush()
        return f
    except OSError:
        return None


def main():
    import webview

    project = find_project()
    sys.path.insert(0, str(project))
    from database import DATA_DIR
    holder = {"server": None, "log": None}
    if not port_open(PORT):        # a copy that is already running keeps serving; this window just attaches to it
        holder["log"] = open_log(DATA_DIR) if getattr(sys, "frozen", False) else None
        holder["server"] = start_server(project, holder["log"])

    url = f"http://127.0.0.1:{PORT}"
    window = webview.create_window(TITLE, html=SPLASH, width=1440, height=900, min_size=(900, 600),
                                   background_color="#0e1117", js_api=Api())

    def wait_healthy(seconds=60):
        for _ in range(int(seconds * 10)):
            try:
                with urllib.request.urlopen(url + "/_stcore/health", timeout=1) as r:
                    if r.status == 200:
                        return True
            except Exception:
                time.sleep(0.1)
        return False

    def wait_then_load():
        wait_healthy()
        window.load_url(url)

    def keep_server_alive():
        """If the server this window started stops on its own (a crash), start it again and reload the page: the window would otherwise stay on 'Connection error'."""
        restarts = []
        while True:
            time.sleep(2)
            server = holder["server"]
            if server is None or server.poll() is None:
                continue
            restarts = [t for t in restarts if time.time() - t < 600]
            if len(restarts) >= 5:                    # not a loop of crashes
                return
            restarts.append(time.time())
            if holder["log"]:
                holder["log"].write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} the server stopped (exit {server.returncode}); starting it again\n".encode("utf-8"))
                holder["log"].flush()
            holder["server"] = start_server(project, holder["log"])
            if wait_healthy():
                try:
                    window.evaluate_js("location.reload()")
                except Exception:
                    pass

    threading.Thread(target=wait_then_load, daemon=True).start()
    threading.Thread(target=keep_server_alive, daemon=True).start()
    storage = DATA_DIR / "webview"                 # the browser-side settings live with the user's other files
    storage.mkdir(parents=True, exist_ok=True)       # keeps the theme and other browser-side settings
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True        # the File page's Download buttons (quizzes, notes) save files
        webview.start(storage_path=str(storage), private_mode=False)
    finally:
        holder["server"], server = None, holder["server"]
        stop_server(server)                          # closing the window stops the server it started


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--server":
        run_server(int(sys.argv[2]), int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[3] == "--parent" else None)
    elif len(sys.argv) > 2 and sys.argv[1] == "--render":          # page renderer for the scrolling PDF view
        import pagerender
        pagerender.main(sys.argv[2:])
    else:
        main()
