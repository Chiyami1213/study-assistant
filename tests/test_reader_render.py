"""The page renderer of the scrolling PDF view is started as its own process: the script it runs must exist (it moved into library/ with the regrouping, and a missing file made the render fail silently)."""
import sys
from pathlib import Path

from core import database
from study import reader


def test_the_render_command_points_to_a_script_that_exists(monkeypatch):
    started = {}
    monkeypatch.setattr("subprocess.Popen", lambda cmd, **kw: started.setdefault("cmd", cmd))
    reader._inflight.clear()
    reader._render_files("x.pdf", 1.0, 0, 2, )
    script = Path(started["cmd"][1])
    assert script.exists() and script.name == "pagerender.py" and script.parent.name == "library"


def test_the_exe_adds_the_project_folder_before_it_imports_the_renderer():
    launcher = (Path(database.BASE_DIR) / "launcher.py").read_text(encoding="utf-8")
    branch = launcher.split('sys.argv[1] == "--render"', 1)[1].split("else:", 1)[0]
    assert branch.index("sys.path.insert(0, str(find_project()))") < branch.index('import_module("library.pagerender")')
