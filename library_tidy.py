"""Library tidy: files that are the same file, and titles that can be written the Library's way. No Streamlit here; the window is in views/library_view.py.

Nothing is changed before the student confirms. Before anything is removed the database is copied to <data folder>\\Backups\\Before Tidy <time>. Only the Library's own stored copies
are removed (never a file on the student's own drives)."""
import hashlib
import re
import shutil
import sqlite3
from datetime import datetime

import crud
import database
import naming
from database import data_path

TITLE_KINDS = ("Homework", "Homework Solution", "Graded Homework", "Homework Helper", "Grade Explanation", "Exam", "Practice Exam", "Exam Solution", "Graded Exam", "Exam Helper",
               "Exam Grade Explanation", "Exam Preparation", "Exam Reflection", "Equation Sheet")


def _digest(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_duplicates():
    """[[book, ...]]: groups of books whose stored files have exactly the same content (compared by size first, then by content). In a group the book to keep comes first (the one linked
    to the most courses, then the oldest)."""
    by_size = {}
    for b in crud.list_books():
        try:
            p = data_path(b["pdf_path"])
            by_size.setdefault(p.stat().st_size, []).append((b, p))
        except (OSError, TypeError):
            continue
    groups = []
    for items in by_size.values():
        if len(items) < 2:
            continue
        same = {}
        for b, p in items:
            try:
                same.setdefault(_digest(p), []).append(b)
            except OSError:
                continue
        groups += [sorted(g, key=lambda b: (-len(b["course_ids"]), b["id"])) for g in same.values() if len(g) > 1]
    return sorted(groups, key=lambda g: g[0]["title"].lower())


def backup(label="Before Tidy"):
    """A copy of the database in Backups; returns the folder."""
    folder = database.DATA_DIR / "Backups" / f"{label} {datetime.now():%Y-%m-%d %H-%M-%S}"
    folder.mkdir(parents=True, exist_ok=True)
    src, dst = sqlite3.connect(database.DB_PATH), sqlite3.connect(folder / "study.db")
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return folder


def remove_duplicates(groups):
    """Keep the first book of each group, give it the courses of the others, and remove the others (their stored files too, when no other book uses the file). Returns how many were removed."""
    if not groups:
        return 0
    backup()
    removed = 0
    for group in groups:
        keep, others = group[0], group[1:]
        courses = list(dict.fromkeys(c for b in group for c in b["course_ids"]))
        crud.set_book_courses(keep["id"], courses)
        for b in others:
            path = data_path(b["pdf_path"])
            crud.delete_book(b["id"])
            removed += 1
            try:
                import covers
                covers.remove_cover(b["id"])
            except Exception:
                pass
            if not any(x["pdf_path"] == b["pdf_path"] for x in crud.list_books()) and database.DATA_DIR in path.parents:
                path.unlink(missing_ok=True)
    return removed


def tidy_title(book):
    """(title, lecture) written the Library's way, or the book's own when it already is."""
    title, lecture, kind = book["title"], book.get("lecture") or "", book["kind"]
    text = re.sub(r"\.(pdf|html?)$", "", title.replace("_", " "), flags=re.I)
    text = crud.fix_course_ids(re.sub(r"\s+", " ", text).strip())
    if kind in TITLE_KINDS and not re.match(r"(?i)^(hw|midterm|final)\b", text.strip()):
        named, number = naming.default_title(kind, text)
        if named:
            text, lecture = named, lecture or number
    elif kind in ("Notes", "Lecture Notes"):
        named, number = naming.default_title(kind, text)
        if named and number and not lecture:
            text, lecture = named, number
        elif named and number and lecture == number:
            text = named
    return text, lecture


def suggest_renames():
    """[{id, kind, old, new, old_lecture, new_lecture}] for the books whose title can be written better."""
    out = []
    for b in crud.list_books():
        new, lecture = tidy_title(b)
        if new != b["title"] or lecture != (b.get("lecture") or ""):
            out.append({"id": b["id"], "kind": b["kind"], "old": b["title"], "new": new, "old_lecture": b.get("lecture") or "", "new_lecture": lecture})
    return out


def apply_renames(changes):
    """Save the titles (and lecture numbers) of the changes the student kept. Returns how many books changed."""
    n = 0
    for c in changes:
        book = crud.get_book(c["id"])
        if not book or not (c["new"] or "").strip():
            continue
        crud.update_book(book["id"], c["new"].strip(), book["author"] or "", book["edition"] or "", book["kind"], book["course_ids"], book.get("year"), (c.get("new_lecture") or "").strip() or None)
        n += 1
    return n
