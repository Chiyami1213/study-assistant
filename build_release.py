"""Developer tool: build the release that people download.   python build_release.py

  1. the app           dist/StudyAssistant/StudyAssistant.exe            (build_exe.py)
  2. the installer     dist/installer/Install Study Assistant.exe        (build_installer.py)
  3. the zip           dist/release/StudyAssistant-<version>-Windows-Installer.zip

The zip is a CLEAN install: the installer, a README and payload/program (the code and the built app). It holds none of the developer's own files
(those live in the data folder, %APPDATA%\\Study Assistant, which is never read here). Upload the zip as the asset of a GitHub release.
Use --no-build to zip what is already built.
"""
import os
import sys
import zipfile
from pathlib import Path

from version import VERSION

ROOT = Path(__file__).parent
INSTALLER = ROOT / "dist" / "installer" / "Install Study Assistant.exe"
OUT = ROOT / "dist" / "release"
SKIP_TOP = {".git", "__pycache__", "build", "static", "data", ".venv", "venv", "node_modules", ".claude", ".pytest_cache", ".idea"}   # only directly under the project
SKIP_REL = {"dist/installer", "dist/release", "exports", "docs", "dist/StudyAssistant/project_path.txt"}
SKIP_FILES = {"CLAUDE.md", ".gitignore", "build_exe.py", "build_installer.py", "build_release.py"}      # developer files: people do not need them
SKIP_SUFFIX = {".pyc", ".spec", ".tmp", ".part"}
STORE = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".zip", ".gif"}


def _is_link(path):
    try:
        return path.is_symlink() or bool(os.stat(path, follow_symlinks=False).st_file_attributes & 0x400)
    except (OSError, AttributeError):
        return False


def program_files():
    """(file, path relative to the project) of the program: the code, and dist/StudyAssistant (the built app). Links are never followed."""
    out = []
    for dp, dns, fns in os.walk(ROOT):
        here = Path(dp)
        rel = here.relative_to(ROOT)
        top = not rel.parts
        dns[:] = sorted(d for d in dns if not (d == "__pycache__" or (top and d in SKIP_TOP)) and not _is_link(here / d)
                        and (rel / d).as_posix() not in SKIP_REL)
        for f in sorted(fns):
            p = here / f
            if p.suffix.lower() not in SKIP_SUFFIX and not _is_link(p) and not (top and f in SKIP_FILES) and (rel / f).as_posix() not in SKIP_REL:
                out.append((p, rel / f))
    return out


def readme():
    return "\r\n".join([f"Study Assistant {VERSION}: clean installation package", "",
                        "1. Extract this whole zip (right click > Extract All).",
                        "2. Open the extracted folder and run \"Install Study Assistant.exe\". Keep the payload folder next to it.",
                        "3. The installer copies the program to Documents\\study-assistant, puts a shortcut on the Desktop and lists Study Assistant under",
                        "   Settings > Apps, where it can be uninstalled. The app starts empty and makes its own data folder (AppData\\Roaming\\Study Assistant).",
                        "   A folder that is already there is never overwritten: it is renamed to \"... (old date)\" first.", "",
                        "To bring your files from another device: Settings > Backup > Import in the app, with a zip made by Export My Files.", ""])


def make_zip():
    exe = ROOT / "dist" / "StudyAssistant" / "StudyAssistant.exe"
    if not exe.exists() or not INSTALLER.exists():
        raise SystemExit("Build the app and the installer first (python build_release.py).")
    OUT.mkdir(parents=True, exist_ok=True)
    final = OUT / f"StudyAssistant-{VERSION}-Windows-Installer.zip"
    part = final.with_name(final.name + ".part")
    files = program_files()
    with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        z.writestr("README.txt", readme())
        z.write(INSTALLER, INSTALLER.name)
        for p, rel in files:
            info = zipfile.ZipInfo.from_file(p, "payload/program/" + rel.as_posix())
            info.compress_type = zipfile.ZIP_STORED if p.suffix.lower() in STORE else zipfile.ZIP_DEFLATED
            with open(p, "rb") as fi, z.open(info, "w", force_zip64=True) as fo:
                while True:
                    block = fi.read(1 << 20)
                    if not block:
                        break
                    fo.write(block)
    with zipfile.ZipFile(part) as z:
        bad = z.testzip()
    if bad:
        part.unlink()
        raise SystemExit(f"The zip check failed ({bad}).")
    if final.exists():
        final.unlink()                              # the previous build of this same version (a file this tool made)
    part.rename(final)
    return final, len(files)


def main():
    if "--no-build" not in sys.argv:
        import build_exe
        build_exe.main()                            # the app, then the installer
    final, n = make_zip()
    print(f"Built: {final}  ({final.stat().st_size / 2**20:.0f} MB, {n} program files)")


if __name__ == "__main__":
    main()
