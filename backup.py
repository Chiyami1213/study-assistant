"""Safety copies of everything in data/ that cannot be made again from the original files: the database, the settings and the small
folders of notes, grades, syllabus data, drawings and equation sheets. They go to <data folder>/Backups/Snapshots/<date and time>/ (the data folder is
AppData/Roaming/Study Assistant, outside the project, so a damaged project folder cannot take the copies with it). The PDFs themselves are not copied (they exist where they were imported from).

run() is called when the app starts; it makes a copy at most once every 30 minutes and keeps the newest 20."""
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from database import DATA_DIR

DATA = DATA_DIR
ROOT = DATA_DIR / "Backups" / "Snapshots"
FOLDERS = ("syllabus", "grading", "annotations", "equation_sheets", "quiz_progress", "outlines", "course_photos")     # small; covers and pdfs are not copied
KEEP = 20
EVERY = 30 * 60


def _latest():
    snaps = sorted(p for p in ROOT.glob("20*") if p.is_dir()) if ROOT.exists() else []
    return snaps[-1] if snaps else None


def run(force=False):
    """Copy now unless a copy was made in the last 30 minutes. Never raises: a backup problem must not stop the app. Returns the folder or None."""
    try:
        db = DATA / "study.db"
        if not db.exists():
            return None
        last = _latest()
        if not force and last and time.time() - last.stat().st_mtime < EVERY:
            return None
        # a database with no courses and no books is a fresh one: do not let it push real copies out of the rotation
        con = sqlite3.connect(db)
        try:
            real = (con.execute("select count(*) from books").fetchone()[0] > 0) or (con.execute("select count(*) from homework_pairs").fetchone()[0] > 0)
        finally:
            con.close()
        if not real and last:
            return None
        dest = ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
        dest.mkdir(parents=True, exist_ok=True)
        src, out = sqlite3.connect(db), sqlite3.connect(dest / "study.db")
        try:
            src.backup(out)                                   # a consistent copy even while the app writes to it
        finally:
            out.close()
            src.close()
        for name in ("settings.json", "settings.json.bak"):
            if (DATA / name).exists():
                shutil.copyfile(DATA / name, dest / name)
        for folder in FOLDERS:
            if (DATA / folder).is_dir():
                shutil.copytree(DATA / folder, dest / folder, dirs_exist_ok=True)
        for old in sorted(p for p in ROOT.glob("20*") if p.is_dir())[:-KEEP]:
            shutil.rmtree(old, ignore_errors=True)
        return dest
    except Exception:
        return None
