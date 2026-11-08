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

PORT = 8765
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
        webview.create_window(TITLE, url, width=1100, height=850, min_size=(600, 400), background_color="#0e1117")


def main():
    import webview

    project = find_project()
    server = None
    if not port_open(PORT):        # a copy that is already running keeps serving; this window just attaches to it
        creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        cmd = [sys.executable, "--server", str(PORT), "--parent", str(os.getpid())] if getattr(sys, "frozen", False) \
            else [sys.executable, str(Path(__file__).resolve()), "--server", str(PORT), "--parent", str(os.getpid())]
        quiet = getattr(sys, "frozen", False)      # from the exe the server is silent; from `python run.py` it prints here
        server = subprocess.Popen(cmd, cwd=project, creationflags=creation if quiet else 0,
                                  stdout=subprocess.DEVNULL if quiet else None,
                                  stderr=subprocess.DEVNULL if quiet else None, stdin=subprocess.DEVNULL)

    url = f"http://127.0.0.1:{PORT}"
    window = webview.create_window(TITLE, html=SPLASH, width=1440, height=900, min_size=(900, 600),
                                   background_color="#0e1117", js_api=Api())

    def wait_then_load():
        for _ in range(600):
            try:
                with urllib.request.urlopen(url + "/_stcore/health", timeout=1) as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(0.1)
        window.load_url(url)

    threading.Thread(target=wait_then_load, daemon=True).start()
    storage = project / "data" / "webview"          # inside the project, so copying the project folder also carries the browser-side settings
    storage.mkdir(parents=True, exist_ok=True)       # keeps the theme and other browser-side settings
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True        # the File page's Download buttons (quizzes, notes) save files
        webview.start(storage_path=str(storage), private_mode=False)
    finally:
        stop_server(server)                          # closing the window stops the server it started


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--server":
        run_server(int(sys.argv[2]), int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[3] == "--parent" else None)
    elif len(sys.argv) > 2 and sys.argv[1] == "--render":          # page renderer for the scrolling PDF view
        import pagerender
        pagerender.main(sys.argv[2:])
    else:
        main()
