"""Settings > Backup > Export: one zip with the user's own files, to keep as a backup or to bring to another device.

make_export() writes ONE zip file:
    README.txt
    payload/data/...    the database (a consistent copy), settings and every imported file         <- Settings > Backup > Import reads this

The zip holds the user's files only; the app is installed from the installer (see build_release.py). Nothing here changes or deletes anything of
the user's: the data folder is only READ; the only file ever removed is the half-written .part file of an export that failed. The zip may not be
written inside the project or the data folder."""
import os
import sqlite3
import tempfile
import threading
import zipfile
from datetime import datetime
from pathlib import Path

from database import BASE_DIR, DATA_DIR
from version import VERSION

SKIP_DATA_DIRS = {"webview", "Backups", "logs", "__pycache__"}          # browser cache; safety copies (the other device makes its own)
SKIP_SUFFIX = {".pyc", ".spec", ".tmp", ".part"}
STORE = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".zip", ".gif"}      # already compressed: stored as they are


def _is_link(path):
    """True for symbolic links and Windows junctions (never followed)."""
    try:
        return path.is_symlink() or bool(os.stat(path, follow_symlinks=False).st_file_attributes & 0x400)
    except (OSError, AttributeError):
        return False


def _walk(root, skip_dirs):
    """Yield (file, path relative to root) under root, skipping links, temporary files and the named folders directly under root."""
    for dp, dns, fns in os.walk(root):
        here = Path(dp)
        rel = here.relative_to(root)
        top = not rel.parts
        dns[:] = sorted(d for d in dns if not (d == "__pycache__" or (top and d in skip_dirs)) and not _is_link(here / d))
        for f in sorted(fns):
            p = here / f
            if p.suffix.lower() in SKIP_SUFFIX or _is_link(p):
                continue
            yield p, rel / f


def data_files():
    return [(p, rel) for p, rel in _walk(DATA_DIR, SKIP_DATA_DIRS) if not (len(rel.parts) == 1 and rel.name.startswith("study.db"))]


def estimate():
    """{bytes, files} of what an export holds, for the page to show before it is made."""
    data = data_files()
    return {"bytes": sum(p.stat().st_size for p, _ in data), "files": len(data)}


def _existing(path):
    """The folder itself, or the nearest parent that exists (the export folder may not have been made yet)."""
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    return p


def check_space(dest_dir, info):
    """Is there enough free disk space for the zip? It is at most as big as the files in it (pdfs and pictures are stored as they are), plus some
    room; the temporary copy of the database is made in the data folder, which counts too when that is the same drive.
    Returns {ok, needed, free, drive}; sizes in bytes."""
    import shutil
    needed = info["bytes"] + (200 << 20)
    where = _existing(dest_dir)
    free = shutil.disk_usage(where).free
    db = DATA_DIR / "study.db"
    if db.exists() and os.path.splitdrive(str(where.resolve()))[0].lower() == os.path.splitdrive(str(DATA_DIR.resolve()))[0].lower():
        needed += db.stat().st_size
    drive = os.path.splitdrive(str(where.resolve()))[0] or str(where)
    return {"ok": free >= needed, "needed": needed, "free": free, "drive": drive}


def _inside(path, folder):
    a, b = Path(path).resolve(), Path(folder).resolve()
    return a == b or b in a.parents


def _readme():
    lines = [f"Study Assistant {VERSION}: export of your files (no program)", f"Made {datetime.now():%Y-%m-%d %H:%M}.", "",
             "As a backup: keep this zip somewhere safe.",
             "On another device (or to restore): install Study Assistant, open it, go to Settings > Backup > Import, choose this zip and press Import.",
             "Files that are already there and differ are kept in Backups\\Before Import ... inside the data folder; nothing is deleted.", ""]
    return "\r\n".join(lines)


def make_export(dest_dir, progress=None, name=None):
    """Write the zip into dest_dir and return its path. progress(fraction, message) is called along the way. Raises RuntimeError with a clear reason."""
    progress = progress or (lambda f, m: None)
    dest_dir = Path(dest_dir)
    if _inside(dest_dir, BASE_DIR) or _inside(dest_dir, DATA_DIR):
        raise RuntimeError("Choose a folder outside the program folder and outside the data folder (the Desktop, a USB drive, OneDrive ...).")
    dest_dir.mkdir(parents=True, exist_ok=True)
    progress(0.0, "Listing the files...")
    data = data_files()
    total = sum(p.stat().st_size for p, _ in data) or 1
    space = check_space(dest_dir, {"bytes": total})
    if not space["ok"]:
        raise RuntimeError(f"Not enough free space on {space['drive']}: the zip needs about {space['needed'] / 2**30:.1f} GB and only "
                           f"{space['free'] / 2**30:.1f} GB are free. Free some space or save it on another drive.")
    final = dest_dir / (name or f"StudyAssistant-Files-{datetime.now():%Y%m%d-%H%M}.zip")
    part = final.with_name(final.name + ".part")
    done = 0
    expected = {}
    tmp_root = DATA_DIR / "Backups"; tmp_root.mkdir(parents=True, exist_ok=True)
    tmpdir = tempfile.TemporaryDirectory(dir=tmp_root)        # the temporary database copy stays inside the data folder
    try:
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as z:
            def add(src, arc):
                nonlocal done
                info = zipfile.ZipInfo.from_file(src, arc)
                info.compress_type = zipfile.ZIP_STORED if Path(arc).suffix.lower() in STORE else zipfile.ZIP_DEFLATED
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

            z.writestr("README.txt", _readme())
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
        progress(0.99, "Checking the export...")
        with zipfile.ZipFile(part) as z:
            sizes = {i.filename: i.file_size for i in z.infolist()}
        bad = [a for a, s in expected.items() if sizes.get(a) != s]
        if bad:
            raise RuntimeError(f"The export check failed for {len(bad)} files (first: {bad[0]}).")
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


def start(dest_dir):
    with _lock:
        if JOB["running"]:
            return False
        JOB.update(running=True, fraction=0.0, message="Starting...", result=None, error=None)

    def work():
        try:
            JOB["result"] = str(make_export(dest_dir, lambda f, m: JOB.update(fraction=f, message=m)))
        except Exception as e:
            JOB["error"] = str(e)
        finally:
            JOB["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return True
