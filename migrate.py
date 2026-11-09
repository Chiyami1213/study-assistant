"""Migration package: everything needed to set Study Assistant up on another laptop, made from Settings > Migrate.

make_package() writes ONE zip file:
    Install Study Assistant.exe     (the installer, see installer.py)
    README.txt
    payload/program/...             the program: code, notes, quizzes and (optionally) the app's exe          -> <Documents>\\study-assistant
    payload/data/...                (full migration only) the database, settings and every imported file       -> %APPDATA%\\Study Assistant
On the new laptop: extract the zip, run the installer.

Nothing here changes or deletes anything of the user's: the data folder, the project and the user's own drives are only READ; the only file
ever removed is the half-written .part file of a package that failed. The zip may not be written inside the project or the data folder."""
import os
import sqlite3
import sys
import tempfile
import threading
import zipfile
from datetime import datetime
from pathlib import Path

from database import BASE_DIR, DATA_DIR

INSTALLER_NAME = "Install Study Assistant.exe"
SKIP_PROGRAM_DIRS = {".git", "__pycache__", "build", "static", "data", ".venv", "venv", "node_modules", ".claude", ".pytest_cache", ".idea"}
SKIP_DATA_DIRS = {"webview", "Backups", "__pycache__"}          # browser cache; safety copies (the new laptop makes its own)
SKIP_SUFFIX = {".pyc", ".spec", ".tmp", ".part"}
STORE = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".zip", ".gif"}      # already compressed: stored as they are


def _is_link(path):
    """True for symbolic links and Windows junctions (never followed)."""
    try:
        return path.is_symlink() or bool(os.stat(path, follow_symlinks=False).st_file_attributes & 0x400)
    except (OSError, AttributeError):
        return False


def _walk(root, skip_dirs, skip_rel=()):
    """Yield (file, path relative to root) under root, skipping the named folders, links and temporary files."""
    for dp, dns, fns in os.walk(root):
        here = Path(dp)
        rel = here.relative_to(root)
        dns[:] = sorted(d for d in dns if d not in skip_dirs and not _is_link(here / d) and (rel / d).as_posix() not in skip_rel)
        for f in sorted(fns):
            p = here / f
            if p.suffix.lower() in SKIP_SUFFIX or _is_link(p):
                continue
            yield p, rel / f


def installer_exe():
    return BASE_DIR / "dist" / "installer" / INSTALLER_NAME


def program_files(include_exe):
    skip_rel = {"dist/installer", "dist/release"} | (set() if include_exe else {"dist"})
    skip_dirs = SKIP_PROGRAM_DIRS
    out = []
    for p, rel in _walk(BASE_DIR, skip_dirs, skip_rel):
        if rel.parts[0] == "dist" and not include_exe:
            continue
        out.append((p, rel))
    return out


def data_files():
    return [(p, rel) for p, rel in _walk(DATA_DIR, SKIP_DATA_DIRS) if not (len(rel.parts) == 1 and rel.name.startswith("study.db"))]


def estimate(include_exe=True, include_data=True):
    """Sizes in bytes and file counts, for the page to show before the package is made."""
    prog = program_files(include_exe)
    data = data_files() if include_data else []
    return {"program_bytes": sum(p.stat().st_size for p, _ in prog), "program_files": len(prog),
            "data_bytes": sum(p.stat().st_size for p, _ in data), "data_files": len(data), "installer": installer_exe().exists()}


def _inside(path, folder):
    a, b = Path(path).resolve(), Path(folder).resolve()
    return a == b or b in a.parents


def _readme(full, include_exe):
    lines = ["Study Assistant: " + ("migration package (program and all of your files)" if full else "clean installation package (no personal files)"),
             f"Made {datetime.now():%Y-%m-%d %H:%M}.", "",
             "1. Extract this whole zip (right click > Extract All).",
             f"2. Open the extracted folder and run \"{INSTALLER_NAME}\". Keep the payload folder next to it.",
             "3. The installer copies the program to Documents\\study-assistant"
             + (" and your files to AppData\\Roaming\\Study Assistant." if full else "; the app makes its own empty data folder the first time it runs."),
             "   A folder that is already there is never overwritten: it is renamed to \"... (old date)\" first.", ""]
    lines.append("Start the app with the Study Assistant shortcut the installer puts on the Desktop." if include_exe
                 else "Start the app with:  pip install -r requirements.txt  then  python run.py  (inside Documents\\study-assistant).")
    lines += ["", "After checking that everything is there, the extracted folder and this zip can be deleted."]
    return "\r\n".join(lines) + "\r\n"


def make_package(dest_dir, include_exe=True, include_data=True, progress=None, name=None):
    """Write the zip into dest_dir and return its path. progress(fraction, message) is called along the way. Raises RuntimeError with a clear reason."""
    progress = progress or (lambda f, m: None)
    dest_dir = Path(dest_dir)
    if _inside(dest_dir, BASE_DIR) or _inside(dest_dir, DATA_DIR):
        raise RuntimeError("Choose a folder outside the project and outside the data folder (the Desktop, a USB drive, ...).")
    exe = installer_exe()
    if not exe.exists() and not getattr(sys, "frozen", False):
        progress(0.0, "Building the installer...")
        import build_installer
        build_installer.build()
    if not exe.exists():
        raise RuntimeError("The installer exe is not built yet. Run  python build_installer.py  once in the project folder, then try again.")
    dest_dir.mkdir(parents=True, exist_ok=True)
    progress(0.0, "Listing the files...")
    prog = program_files(include_exe)
    data = data_files() if include_data else []
    total = sum(p.stat().st_size for p, _ in prog + data) + exe.stat().st_size
    free = __import__("shutil").disk_usage(dest_dir).free
    if free < total + (200 << 20):
        raise RuntimeError(f"Not enough free space in {dest_dir}: about {total / 2**30:.1f} GB are needed, {free / 2**30:.1f} GB are free.")
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    final = dest_dir / (name or f"StudyAssistant-{'Migration' if include_data else 'Clean'}-{stamp}.zip")
    part = final.with_name(final.name + ".part")
    done = 0
    expected = {}
    tmp_root = DATA_DIR / "Backups"; tmp_root.mkdir(parents=True, exist_ok=True)
    tmpdir = tempfile.TemporaryDirectory(dir=tmp_root)        # the temporary database copy stays inside the data folder
    try:
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as z:
            def add(src, arc):
                nonlocal done
                method = zipfile.ZIP_STORED if Path(arc).suffix.lower() in STORE else zipfile.ZIP_DEFLATED
                info = zipfile.ZipInfo.from_file(src, arc)
                info.compress_type = method
                info._compresslevel = 1
                with open(src, "rb") as fi, z.open(info, "w", force_zip64=True) as fo:
                    while True:
                        block = fi.read(1 << 20)
                        if not block:
                            break
                        fo.write(block)
                        done += len(block)
                        progress(min(done / total, 0.99), f"Packing {arc}")
                expected[arc] = Path(src).stat().st_size

            z.writestr("README.txt", _readme(include_data, include_exe))
            add(exe, INSTALLER_NAME)
            for p, rel in prog:
                add(p, "payload/program/" + rel.as_posix())
            if include_data:
                db = DATA_DIR / "study.db"
                if db.exists():                                          # a consistent copy even while the app is writing to it
                    copy = Path(tmpdir.name) / "study.db"
                    a, b = sqlite3.connect(db), sqlite3.connect(copy)
                    try:
                        a.backup(b)
                    finally:
                        b.close()
                        a.close()
                    add(copy, "payload/data/study.db")
                for p, rel in data:
                    add(p, "payload/data/" + rel.as_posix())
        progress(0.99, "Checking the package...")
        with zipfile.ZipFile(part) as z:
            sizes = {i.filename: i.file_size for i in z.infolist()}
        bad = [a for a, s in expected.items() if sizes.get(a) != s]
        if bad:
            raise RuntimeError(f"The package check failed for {len(bad)} files (first: {bad[0]}).")
        if final.exists():
            final = final.with_name(final.stem + f"-{datetime.now():%S}" + final.suffix)
        part.rename(final)
    except BaseException:
        try:
            part.unlink()                                                # only the half-written file this call made
        except OSError:
            pass
        raise
    finally:
        tmpdir.cleanup()
    progress(1.0, "Done")
    return final


# --- background job, for the Settings page -------------------------------------------------------------------------------------------------
JOB = {"running": False, "fraction": 0.0, "message": "", "result": None, "error": None}
_lock = threading.Lock()


def start(dest_dir, include_exe=True, include_data=True):
    with _lock:
        if JOB["running"]:
            return False
        JOB.update(running=True, fraction=0.0, message="Starting...", result=None, error=None)

    def work():
        try:
            def cb(f, m):
                JOB.update(fraction=f, message=m)
            JOB["result"] = str(make_package(dest_dir, include_exe, include_data, cb))
        except Exception as e:
            JOB["error"] = str(e)
        finally:
            JOB["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return True
