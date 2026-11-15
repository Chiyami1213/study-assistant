"""Build the macOS app and its disk image:  python3 build_mac.py   (on a Mac; the GitHub workflow .github/workflows/build-macos.yml does it for the releases)

    dist/Study Assistant.app                                   the app: Python, the libraries and the program's code (Contents/Resources/project)
    dist/release/StudyAssistant-<version>-macOS-<arch>.dmg     the download: open it and drag Study Assistant into Applications

PyInstaller cannot build a Mac app on Windows, so this has to run on macOS (Apple silicon builds the "Apple-Silicon" image, an Intel Mac the "Intel" one). The
app is signed ad hoc (no Apple developer account): macOS asks the user to approve it once (right-click > Open). Nothing personal goes into the package: the user's
files live in ~/Library/Application Support/Study Assistant, outside the app."""
import hashlib
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from version import VERSION

ROOT = Path(__file__).parent
APP_NAME = "Study Assistant"
DIST = ROOT / "dist"
OUT = DIST / "release"
BUNDLE_ID = "com.studyassistant.app"
STDLIB = ["base64", "calendar", "colorsys", "csv", "datetime", "difflib", "hashlib", "html", "importlib", "io", "json",
          "math", "pathlib", "re", "shutil", "sqlite3", "subprocess", "tempfile", "textwrap", "urllib.parse",
          "urllib.request", "uuid", "warnings", "zipfile", "zoneinfo", "collections", "itertools", "functools",
          "dataclasses", "random", "statistics", "time", "string", "mimetypes", "unicodedata", "xml.etree.ElementTree"]
LIBS = ["pymupdf", "fitz", "pypdf", "PIL", "pillow_heif", "pagerender", "psutil"]
MAC_LIBS = ["objc", "AppKit", "Foundation", "WebKit", "Quartz", "Security", "UniformTypeIdentifiers"]      # pywebview's Cocoa side (and the F2 screenshot)
# What the program needs at run time: its code. Developer files (the build scripts, the Windows installer) stay out.
SKIP_PY = {"build_exe.py", "build_installer.py", "build_release.py", "build_mac.py", "buildinfo.py", "installer.py", "launcher.py"}
KEEP_DIRS = ["views", ".streamlit"]


def arch_name():
    return "Apple-Silicon" if platform.machine() == "arm64" else "Intel"


def make_icon(path):
    """The app icon as .icns (the same picture as the Windows icon, drawn large)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 248, 248), 48, fill=(14, 17, 23, 255), outline=(255, 75, 75, 255), width=8)
    d.polygon([(128, 60), (222, 108), (128, 156), (34, 108)], fill=(255, 255, 255, 255))
    d.polygon([(70, 136), (70, 176), (128, 200), (186, 176), (186, 136), (128, 162)], fill=(220, 224, 232, 255))
    img.resize((1024, 1024), Image.Resampling.LANCZOS).save(path, format="ICNS")


def build_app():
    if sys.platform != "darwin":
        raise SystemExit("build_mac.py has to run on a Mac (PyInstaller cannot build a Mac app on another system).")
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    icon = build / "app.icns"
    make_icon(icon)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed", "--name", APP_NAME, "--icon", str(icon),
           "--osx-bundle-identifier", BUNDLE_ID,
           "--collect-all", "streamlit", "--copy-metadata", "streamlit", "--collect-all", "webview", "--collect-all", "pymupdf",
           "--collect-all", "pillow_heif", "--collect-submodules", "pypdf", "--collect-submodules", "PIL"]
    for m in STDLIB + LIBS + MAC_LIBS:
        cmd += ["--hidden-import", m]
    cmd += ["--distpath", str(DIST), "--workpath", str(build / "mac"), "--specpath", str(build / "mac"), str(ROOT / "launcher.py")]
    subprocess.run(cmd, check=True, cwd=ROOT)
    app = DIST / f"{APP_NAME}.app"
    if not app.is_dir():
        raise SystemExit(f"PyInstaller did not make {app}")
    return app


def add_program(app):
    """Copy the program's code into the app (Contents/Resources/project); the launcher finds app.py there."""
    project = app / "Contents" / "Resources" / "project"
    if project.exists():
        shutil.rmtree(project)                              # a folder made by this script in an earlier build
    project.mkdir(parents=True)
    n = 0
    for p in sorted(ROOT.glob("*.py")):
        if p.name not in SKIP_PY:
            shutil.copy2(p, project / p.name)
            n += 1
    for d in KEEP_DIRS:
        src = ROOT / d
        if src.is_dir():
            shutil.copytree(src, project / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            n += sum(1 for f in (project / d).rglob("*") if f.is_file())
    shutil.copy2(ROOT / "requirements.txt", project / "requirements.txt")
    return n


def sign(app):
    """An ad hoc signature (no developer account): Apple silicon refuses to run unsigned code; the user still approves the app once."""
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)


DMG_README = f"""Study Assistant {VERSION} for macOS

Install: drag "Study Assistant" onto the Applications folder in this window. If it is already there, choose Replace: your files are kept.
         They live in ~/Library/Application Support/Study Assistant, outside the app.

First start: macOS may say it cannot check the app for malware. That is expected for an app that is not from the App Store. Study Assistant contains no virus and its
full source code is public: https://github.com/Chiyami1213/study-assistant
         Open Applications, right-click (or Control-click) "Study Assistant", choose Open, then Open again. You only do this once.
         If the message still blocks it, open System Settings > Privacy & Security and choose "Open Anyway" next to Study Assistant.

Help and problem reports: https://github.com/Chiyami1213/study-assistant/blob/main/docs/HELP.md
"""


def make_dmg(app):
    OUT.mkdir(parents=True, exist_ok=True)
    stage = DIST / "dmg-stage"
    if stage.exists():
        shutil.rmtree(stage)                                # made by this script
    stage.mkdir()
    shutil.copytree(app, stage / app.name, symlinks=True)
    (stage / "Applications").symlink_to("/Applications")
    (stage / "READ ME FIRST.txt").write_text(DMG_README, encoding="utf-8")
    final = OUT / f"StudyAssistant-{VERSION}-macOS-{arch_name()}.dmg"
    final.unlink(missing_ok=True)                           # the previous build of this same version
    subprocess.run(["hdiutil", "create", "-volname", f"{APP_NAME} {VERSION}", "-srcfolder", str(stage), "-ov", "-format", "UDZO", str(final)], check=True)
    shutil.rmtree(stage)
    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    (OUT / f"SHA256SUMS-macOS-{arch_name()}.txt").write_text(f"{digest}  {final.name}\n", encoding="utf-8")
    return final


def main():
    app = build_app()
    print("Program files copied into the app:", add_program(app))
    sign(app)
    final = make_dmg(app)
    print(f"Built: {final}  ({final.stat().st_size / 2**20:.0f} MB)")


if __name__ == "__main__":
    main()
