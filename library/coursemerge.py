"""Merging courses inside the app (MA 266 / MA 303 as one Differential Equations, MA 161 / 162 / 261 as one Calculus). No Streamlit here.

Every file, homework and exam title of a part ends with its tag in brackets ("HW 10 (MA 266)"); a textbook stays untagged and belongs to every part; the outline, the syllabus and the quiz
chapters are kept per part. All that belonged to the courses that are dropped moves to the course that is kept, and the dropped courses are deleted. Before anything changes the database and the
settings are copied to <data folder>\\Backups\\Before Merge <time>."""
import re
import shutil
import sqlite3
from datetime import datetime

from core import crud
from core import database
from core import settings
from library import syllabus


def course_tables(conn):
    """[(table, column)] of every table that points at a course."""
    out = []
    for t in [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]:
        if t == "courses":
            continue
        for fk in conn.execute(f"PRAGMA foreign_key_list({t})"):
            if fk[2] == "courses":
                out.append((t, fk[3]))
    return out


def preview(kept_id, dropped_ids):
    """{table: rows that move} for the dropped courses, for the confirmation."""
    counts = {}
    with database.get_conn() as conn:
        for table, col in course_tables(conn):
            n = sum(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col}=?", (d,)).fetchone()[0] for d in dropped_ids)
            if n:
                counts[table] = n
    return counts


def default_tag(course):
    return crud.show_code(course["code"] or course["name"]).split(" / ")[0] if course["code"] else course["name"]


def merged_code(courses):
    """"MA 266 / 303" from the codes of the courses ("MA 266", "MA 303"): the letters once when they are the same."""
    codes = [c["code"] for c in courses if c.get("code")]
    letters = {re.match(r"[A-Za-z]+", c).group().upper() for c in codes if re.match(r"[A-Za-z]+", c)}
    if len(letters) == 1 and all(re.fullmatch(r"[A-Za-z]+\s*\d+[A-Za-z]?", c.strip()) for c in codes):
        first, *rest = [c.strip() for c in codes]
        return " / ".join([first] + [re.sub(r"^[A-Za-z]+\s*", "", c) for c in rest])
    return " / ".join(codes)


def backup():
    folder = database.DATA_DIR / "Backups" / f"Before Merge {datetime.now():%Y-%m-%d %H-%M-%S}"
    folder.mkdir(parents=True, exist_ok=True)
    src, dst = sqlite3.connect(database.DB_PATH), sqlite3.connect(folder / "study.db")
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    if settings.SETTINGS_FILE.exists():
        shutil.copy2(settings.SETTINGS_FILE, folder / "settings.json")
    if syllabus.DIR.exists():
        shutil.copytree(syllabus.DIR, folder / "syllabus", dirs_exist_ok=True)
    return folder


def _tag_title(title, tag):
    return title if crud.part_tag(title) else f"{title} ({tag})"


def merge(kept_id, dropped_ids, tags, code=None, name=None):
    """Merge the dropped courses into the kept one. `tags`: {course id: tag} for every course (the kept one too). Returns {"moved": {table: rows}, "tagged": n, "backup": folder}."""
    dropped_ids = [d for d in dropped_ids if d != kept_id]
    if not dropped_ids:
        raise ValueError("Choose at least two courses.")
    everyone = [kept_id] + dropped_ids
    if any(not (tags.get(c) or "").strip() for c in everyone):
        raise ValueError("Every course needs a tag.")
    if len({tags[c].strip().upper().replace(" ", "") for c in everyone}) != len(everyone):
        raise ValueError("The tags have to be different.")
    folder = backup()
    moved = preview(kept_id, dropped_ids)
    books = crud.list_books()
    tagged = 0
    with database.get_conn() as conn:
        for cid in everyone:
            tag = tags[cid].strip()
            mine = [b for b in books if cid in b["course_ids"] and sum(1 for c in everyone if c in b["course_ids"]) == 1 and b["kind"] != "Textbook"]   # a file of two parts is shared: untagged
            for b in mine:
                new = _tag_title(b["title"], tag)
                if new != b["title"]:
                    conn.execute("UPDATE books SET title=? WHERE id=?", (new, b["id"]))
                    tagged += 1
            for h in conn.execute("SELECT id, title FROM homework_pairs WHERE course_id=?", (cid,)).fetchall():
                new = _tag_title(h["title"], tag)
                if new != h["title"]:
                    conn.execute("UPDATE homework_pairs SET title=? WHERE id=?", (new, h["id"]))
                    tagged += 1
            for e in conn.execute("SELECT id, title FROM events WHERE course_id=?", (cid,)).fetchall():
                new = _tag_title(e["title"], tag)
                if new != e["title"]:
                    conn.execute("UPDATE events SET title=? WHERE id=?", (new, e["id"]))
                    tagged += 1
            conn.execute("UPDATE course_outline SET part=? WHERE course_id=? AND part=''", (re.sub(r"\s+", "", tag).upper(), cid))
        conn.commit()
    for cid in everyone:                                                       # the syllabus data and the state of the outline of each part
        part = re.sub(r"\s+", "", tags[cid]).upper()
        data = syllabus.load(cid)
        if data and not syllabus.load(kept_id, part):
            syllabus.save(kept_id, data, part)
        state = settings.get_outline_state(cid, None)
        if state:
            settings.set_outline_state(kept_id, state.get("source", "manual"), state.get("sig", ""), part)
    with database.get_conn() as conn:
        for table, col in course_tables(conn):
            for d in dropped_ids:
                conn.execute(f"UPDATE OR IGNORE {table} SET {col}=? WHERE {col}=?", (kept_id, d))
        for d in dropped_ids:
            for table, col in course_tables(conn):                               # whatever could not move (a duplicate row) goes with the course
                conn.execute(f"DELETE FROM {table} WHERE {col}=?", (d,))
            conn.execute("DELETE FROM courses WHERE id=?", (d,))
        if code:
            conn.execute("UPDATE courses SET code=? WHERE id=?", (code.strip(), kept_id))
        if name:
            conn.execute("UPDATE courses SET name=? WHERE id=?", (name.strip(), kept_id))
        conn.commit()
    for d in dropped_ids:
        settings.forget_block(f"course:{d}")
        for f in syllabus.DIR.glob(f"{d}.json") if syllabus.DIR.exists() else []:
            f.unlink(missing_ok=True)
    return {"moved": moved, "tagged": tagged, "backup": folder}
