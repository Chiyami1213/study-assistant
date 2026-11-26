"""The folders of the project: the root keeps only the entry points, every module is importable from its folder, and the exe never bundles the app's own packages."""
import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ["core", "library", "study", "datafiles", "desktop", "planner", "views"]


def test_the_root_holds_only_the_entry_points():
    assert sorted(p.name for p in ROOT.glob("*.py")) == ["app.py", "launcher.py", "launcher_qt.py", "run.py", "run_qt.py", "version.py"]


@pytest.mark.usefixtures("fresh_data")
@pytest.mark.parametrize("package", PACKAGES)
def test_every_module_of_a_folder_imports(package):
    assert (ROOT / package / "__init__.py").exists()
    for path in sorted((ROOT / package).glob("*.py")):
        if path.name != "__init__.py":
            importlib.import_module(f"{package}.{path.stem}")


def test_the_data_folder_logic_finds_the_project_root():
    from core import database
    assert database.BASE_DIR == ROOT and (database.BASE_DIR / "app.py").exists()


def test_the_launcher_reads_the_app_packages_by_name_and_the_build_does_not_bundle_them():
    launcher = (ROOT / "launcher.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import) (core|library|study|datafiles|desktop|planner|views)\b", launcher, re.M)     # a plain import would bundle the package into the exe
    assert importlib.import_module("core.database") and importlib.import_module("library.pagerender")
    for name in ("build_exe.py", "build_mac.py"):
        libs = re.search(r"LIBS = \[(.*?)\]", (ROOT / "tools" / name).read_text(encoding="utf-8"))
        assert libs and not any(pkg in libs.group(1) for pkg in ("pagerender", "core", "library"))


def test_a_guides_three_js_comes_from_the_app_not_from_the_network():
    from study import htmlnotes
    page = ('<html><head><script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-svg.js" async></script></head><body>'
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script><script>if(!window.THREE){document.title="no three"}</script></body></html>')
    out = htmlnotes.safe_html(page)
    assert "three.js/r128" not in out and "WebGLRenderer" in out and "Three.js Authors" in out            # the library is inside the page
    assert "mathjax/3.2.2/es5/tex-svg.js" in out                                                             # other CDN scripts are left alone
    assert "</script" not in htmlnotes._vendor_text("three-r128.min.js")


def test_the_native_interface_never_imports_streamlit():
    for path in (ROOT / "qtui").rglob("*.py"):
        assert not re.search(r"^\s*(from|import) streamlit", path.read_text(encoding="utf-8"), re.M), path
