"""Settings > Backup > Import: bring the files of an export into this app's data folder.

The zip is the one made by Settings > Backup > Export My Files: the user's files are under `payload/data/`.
Nothing is deleted. Every file of the zip is written: a file that is not there yet is added; a file that is there and differs is first copied to
<data folder>\\Backups\\Before Import <date time>\\ and then replaced; a file that is there with the same content is written again (there is nothing to keep).
The database is replaced through sqlite's own
backup (so it also works while the app has it open), after the current one was copied to the same Backups folder. The zip itself is only read.
Restart the app afterwards."""
import os
import shutil
import sqlite3
import threading
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

from database import DATA_DIR

PREFIX = "payload/data/"
SKIP_TOP = {"webview", "Backups", "__pycache__"}


def _members(z):
    """[(ZipInfo, relative path)] of the data files in the zip, refusing anything that could land outside the data folder."""
    out = []
    root = DATA_DIR.resolve()
    for i in z.infolist():
        if i.is_dir() or not i.filename.startswith(PREFIX):
            continue
        rel = i.filename[len(PREFIX):]
        parts = Path(rel).parts
        if not parts or Path(rel).is_absolute() or ".." in parts or ":" in rel:
            raise RuntimeError(f"The zip holds an unsafe path ({i.filename}); nothing was imported.")
        if parts[0] in SKIP_TOP:
            continue
        target = (DATA_DIR / rel).resolve()
        if root != target and root not in target.parents:
            raise RuntimeError(f"The zip holds an unsafe path ({i.filename}); nothing was imported.")
        out.append((i, rel))
    return out


def inspect(path):
    """What an import of this zip would bring: {files, bytes, has_db}. Raises RuntimeError with a clear reason when it cannot be used."""
    p = Path(str(path).strip().strip('"'))
    if not p.is_file():
        raise RuntimeError("That zip file was not found.")
    try:
        with zipfile.ZipFile(p) as z:
            members = _members(z)
    except zipfile.BadZipFile:
        raise RuntimeError("That file is not a zip, or it is damaged.")
    if not members:
        raise RuntimeError("This zip holds no Study Assistant files. Use a zip made by Settings > Backup > Export My Files.")
    return {"files": len(members), "bytes": sum(i.file_size for i, _ in members), "has_db": any(r == "study.db" for _, r in members)}


def _same(target, info):
    """True when the file that is there has exactly the content of the zip's file (the size, then the CRC of every byte)."""
    try:
        if target.stat().st_size != info.file_size:
            return False
    except OSError:
        return False
    crc = 0
    with open(target, "rb") as f:
        while True:
            block = f.read(1 << 20)
            if not block:
                break
            crc = zlib.crc32(block, crc)
    return crc == info.CRC


def import_zip(path, progress=None):
    """Import the zip; returns {added, replaced, same, backup}. progress(fraction, message). Raises RuntimeError with a clear reason."""
    progress = progress or (lambda f, m: None)
    p = Path(str(path).strip().strip('"'))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = DATA_DIR / "Backups" / f"Before Import {stamp}"
    added = replaced = same = 0
    with zipfile.ZipFile(p) as z:
        members = _members(z)
        total = sum(i.file_size for i, _ in members) or 1
        need = total + (200 << 20)
        free = shutil.disk_usage(DATA_DIR if DATA_DIR.exists() else DATA_DIR.parent).free
        if free < need:
            raise RuntimeError(f"Not enough free space for the import: about {need / 2**30:.1f} GB are needed and {free / 2**30:.1f} GB are free.")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        done = 0
        scratch = DATA_DIR / "Backups" / f"import-{stamp}.tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        try:
            db_info = None
            for info, rel in members:
                target = DATA_DIR / rel
                if rel == "study.db":
                    db_info = info
                    continue
                progress(min(done / total, 0.97), f"Importing {rel}")
                if target.exists():
                    if _same(target, info):
                        same += 1                                          # written again below; the old content is the same, so there is nothing to keep
                    else:
                        keep = backup / rel
                        keep.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(target, keep)
                        replaced += 1
                else:
                    added += 1
                target.parent.mkdir(parents=True, exist_ok=True)
                part = target.with_name(target.name + ".part")           # written beside it, then moved over it: a file is never left half written
                with z.open(info) as fi, open(part, "wb") as fo:
                    shutil.copyfileobj(fi, fo, 1 << 20)
                if part.stat().st_size != info.file_size:
                    part.unlink()
                    raise RuntimeError(f"{rel} could not be copied completely (is the disk full?).")
                os.replace(part, target)
                done += info.file_size
            if db_info is not None:
                progress(0.98, "Importing the database")
                new_db = scratch / "study.db"
                with z.open(db_info) as fi, open(new_db, "wb") as fo:
                    shutil.copyfileobj(fi, fo, 1 << 20)
                _replace_database(new_db, backup)
                replaced += 1
        finally:
            shutil.rmtree(scratch, ignore_errors=True)                # the temporary copy this call made
    progress(1.0, "Done")
    return {"added": added, "replaced": replaced, "same": same, "backup": str(backup) if backup.exists() else ""}


def _replace_database(new_db, backup):
    """Put the contents of new_db into the live database with sqlite's backup, after copying the current one to the backup folder."""
    check = sqlite3.connect(f"file:{new_db}?mode=ro", uri=True)
    try:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("The database in the zip is damaged; the import was stopped before it was replaced.")
        if not check.execute("SELECT 1 FROM sqlite_master WHERE name='courses'").fetchone():
            raise RuntimeError("The database in the zip is not a Study Assistant database.")
    finally:
        check.close()
    live = DATA_DIR / "study.db"
    if live.exists():
        backup.mkdir(parents=True, exist_ok=True)
        a, b = sqlite3.connect(live, timeout=30), sqlite3.connect(backup / "study.db")
        try:
            a.backup(b)
        finally:
            b.close()
            a.close()
    src, dst = sqlite3.connect(f"file:{new_db}?mode=ro", uri=True), sqlite3.connect(live, timeout=30)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


# --- background job, for the Settings page ----------------------------------------------------------------------------------------------------
JOB = {"running": False, "fraction": 0.0, "message": "", "result": None, "error": None}
_lock = threading.Lock()


def start(path):
    with _lock:
        if JOB["running"]:
            return False
        JOB.update(running=True, fraction=0.0, message="Starting...", result=None, error=None)

    def work():
        try:
            JOB["result"] = import_zip(path, lambda f, m: JOB.update(fraction=f, message=m))
        except Exception as e:
            JOB["error"] = str(e)
        finally:
            JOB["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return True
