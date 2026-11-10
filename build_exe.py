"""Build the desktop app:  python build_exe.py   ->   dist/StudyAssistant/StudyAssistant.exe

The exe bundles Python and the libraries only. app.py, views/ and data/ are read from this project folder at
run time, so code edits and saved data are shared with VS Code.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
STDLIB = ["base64", "calendar", "colorsys", "csv", "datetime", "difflib", "hashlib", "html", "importlib", "io", "json",
          "math", "pathlib", "re", "shutil", "sqlite3", "subprocess", "tempfile", "textwrap", "urllib.parse",
          "urllib.request", "uuid", "warnings", "zipfile", "zoneinfo", "collections", "itertools", "functools",
          "dataclasses", "random", "statistics", "time", "string", "mimetypes", "unicodedata", "xml.etree.ElementTree"]
LIBS = ["pymupdf", "fitz", "pypdf", "PIL", "pillow_heif", "pagerender", "psutil"]


def make_icon(path):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 248, 248), 48, fill=(14, 17, 23, 255), outline=(255, 75, 75, 255), width=8)
    d.polygon([(128, 60), (222, 108), (128, 156), (34, 108)], fill=(255, 255, 255, 255))      # mortarboard
    d.polygon([(70, 136), (70, 176), (128, 200), (186, 176), (186, 136), (128, 162)], fill=(220, 224, 232, 255))
    img.save(path, sizes=[(256, 256), (64, 64), (32, 32), (16, 16)])


def main():
    icon = ROOT / "build" / "app.ico"
    icon.parent.mkdir(exist_ok=True)
    make_icon(icon)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
           "--name", "StudyAssistant", "--icon", str(icon),
           "--collect-all", "streamlit", "--copy-metadata", "streamlit",
           "--collect-all", "webview", "--collect-all", "pymupdf", "--collect-all", "pillow_heif",
           "--collect-submodules", "pypdf", "--collect-submodules", "PIL"]
    for m in STDLIB + LIBS:
        cmd += ["--hidden-import", m]
    cmd += ["--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
            str(ROOT / "launcher.py")]
    subprocess.run(cmd, check=True, cwd=ROOT)
    out = ROOT / "dist" / "StudyAssistant"
    (out / "project_path.txt").write_text(str(ROOT), encoding="utf-8")
    print("Built:", out / "StudyAssistant.exe")
    import build_installer                      # the installer that goes into the release zip (build_release.py)
    print("Built:", build_installer.build())


if __name__ == "__main__":
    main()
