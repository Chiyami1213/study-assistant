"""Backup and restore of the Library, kept in a folder the user chooses (default <data folder>/Backups/Library).

The folder holds files/ (a copy of every stored PDF and HTML file), manifest.json (what each file is: title, type, lecture, courses, size and a
fingerprint, so a file can also be found again in the folders the user keeps the originals in), study.db (the database) and settings.json.
Nothing here deletes or changes anything outside this app's own data folder, and nothing is ever removed from the user's own drives."""
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import crud
import settings
from database import BASE_DIR, DATA_DIR, PDF_DIR, data_path, stored_path

DEFAULT_DIR = DATA_DIR / "Backups" / "Library"
SMALL_FOLDERS = ("syllabus", "grading", "annotations", "equation_sheets", "outlines", "course_photos")


def backup_dir():
    return Path(settings.get_backup().get("dir") or DEFAULT_DIR)


def source_dirs():
    return [Path(p) for p in settings.get_backup().get("sources", []) if p and Path(p).is_dir()]


def _fingerprint(path):
    """Size and a hash of the first and last megabyte: enough to recognise a file without reading all of it."""
    size = path.stat().st_size
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
        if size > 2 << 20:
            f.seek(-(1 << 20), os.SEEK_END)
            h.update(f.read(1 << 20))
    return size, h.hexdigest()


def manifest():
    """What the Library holds, one entry per file, with the course codes (ids can change, codes do not)."""
    courses = {c["id"]: c for c in crud.list_courses(section=None)}
    out = []
    for b in crud.list_books():
        f = data_path(b["pdf_path"])
        if not f.exists():
            continue
        size, sha = _fingerprint(f)
        out.append({"id": b["id"], "file": f.name, "title": b["title"], "author": b.get("author") or "", "edition": b.get("edition") or "",
                    "year": b.get("year") or "", "lecture": b.get("lecture") or "", "kind": b["kind"], "pages": b.get("total_pages"),
                    "courses": [{"code": courses[i]["code"], "name": courses[i]["name"]} for i in b["course_ids"] if i in courses],
                    "size": size, "sha": sha, "orig_name": b.get("orig_name") or ""})
    return out


def back_up(folder=None):
    """Copy the Library to the backup folder: new or changed files only, the manifest, the database and the settings. Returns a summary."""
    dest = Path(folder) if folder else backup_dir()
    (dest / "files").mkdir(parents=True, exist_ok=True)
    entries = manifest()
    copied = 0
    for e in entries:
        src, target = PDF_DIR / e["file"], dest / "files" / e["file"]
        if not target.exists() or target.stat().st_size != src.stat().st_size:
            shutil.copyfile(src, target)
            copied += 1
    (dest / "manifest.json").write_text(json.dumps({"saved": datetime.now().isoformat(timespec="seconds"), "books": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
    db = DATA_DIR / "study.db"
    if db.exists():
        a, b = sqlite3.connect(db), sqlite3.connect(dest / "study.db")
        try:
            a.backup(b)
        finally:
            b.close()
            a.close()
    for name in ("settings.json",):
        if (DATA_DIR / name).exists():
            shutil.copyfile(DATA_DIR / name, dest / name)
    for folder_name in SMALL_FOLDERS:
        if (DATA_DIR / folder_name).is_dir():
            shutil.copytree(DATA_DIR / folder_name, dest / folder_name, dirs_exist_ok=True)
    settings.set_backup(last=datetime.now().isoformat(timespec="seconds"), dir=str(dest))
    return {"books": len(entries), "copied": copied, "folder": str(dest)}


def auto():
    """After a file is added: refresh the backup when a backup folder has been chosen. Never raises."""
    try:
        if settings.get_backup().get("dir"):
            back_up()
    except Exception:
        pass


def _find_in_sources(entry, index):
    for cand in index.get(entry["size"], []):
        try:
            if _fingerprint(cand)[1] == entry["sha"]:
                return cand
        except OSError:
            continue
    return None


def _index(folders):
    idx = {}
    for root in folders:
        for dp, dn, fn in os.walk(root):                       # reading only
            for f in fn:
                if f.lower().endswith((".pdf", ".html", ".htm")):
                    p = Path(dp) / f
                    try:
                        idx.setdefault(p.stat().st_size, []).append(p)
                    except OSError:
                        pass
    return idx


def restore(folder=None, sources=None):
    """Bring back every file of the manifest that the Library does not have: from the backup folder, else found again in the source folders
    (by size and fingerprint). Files that are already there are left alone. Returns {restored, skipped, missing: [titles]}."""
    src = Path(folder) if folder else backup_dir()
    data = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    by_code = {c["code"]: c["id"] for c in crud.list_courses(section=None) if c["code"]}
    by_name = {c["name"]: c["id"] for c in crud.list_courses(section=None) if not c["code"]}
    folders = [Path(p) for p in (sources if sources is not None else settings.get_backup().get("sources", [])) if p and Path(p).is_dir()]
    index = _index(folders) if folders else {}
    have = {(b["kind"], b["title"], b.get("lecture") or "", tuple(sorted(b["course_ids"]))) for b in crud.list_books()}
    restored = skipped = 0
    missing = []
    for e in data["books"]:
        course_ids = sorted(by_code.get(c["code"]) if c["code"] else by_name.get(c["name"]) for c in e["courses"])
        course_ids = [i for i in course_ids if i]
        if (e["kind"], e["title"], e["lecture"], tuple(course_ids)) in have:
            skipped += 1
            continue
        origin = src / "files" / e["file"]
        if not origin.exists():
            origin = _find_in_sources(e, index)
        if not origin:
            missing.append(e["title"])
            continue
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        dest = PDF_DIR / f"book_{uuid.uuid4().hex[:10]}{Path(e['file']).suffix}"
        shutil.copyfile(origin, dest)                          # a copy; the backup or the original stays where it is
        crud.add_book(e["title"], e["author"], e["edition"], stored_path(dest), e["pages"], course_ids, e["kind"], e["year"], e["lecture"])
        restored += 1
    return {"restored": restored, "skipped": skipped, "missing": missing}


def restore_database(folder=None):
    """Put the backed up database and settings back. The current ones are kept next to them as *.before-restore."""
    src = Path(folder) if folder else backup_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for name in ("study.db", "settings.json"):
        if (src / name).exists():
            target = DATA_DIR / name
            if target.exists():
                shutil.copyfile(target, target.with_name(f"{name}.before-restore-{stamp}"))
            shutil.copyfile(src / name, target)
    return True


def clear_library():
    """Remove every file from the Library: the records and the stored copies. A backup is made first, and nothing is deleted if it fails. Only
    single files inside the app's own data/pdfs, data/covers and static/covers folders are removed, one by one: never a folder, never through a link,
    and never anything in the user's own drives. Returns the number of books removed."""
    summary = back_up()                                         # raises if it cannot: then nothing is removed
    books = crud.list_books()
    for b in books:
        crud.delete_book(b["id"])
    removed = 0
    for folder in (PDF_DIR, DATA_DIR / "covers", BASE_DIR / "static" / "covers"):
        if not folder.is_dir() or folder.is_symlink() or _is_link(folder):
            continue
        for f in list(folder.iterdir()):
            if f.is_file() and not f.is_symlink() and not _is_link(f) and f.resolve().parent == folder.resolve():
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass
    return {"books": len(books), "files": removed, "backup": summary["folder"]}


def _is_link(path):
    """True for symbolic links and Windows junctions."""
    try:
        return path.is_symlink() or bool(os.stat(path, follow_symlinks=False).st_file_attributes & 0x400)     # FILE_ATTRIBUTE_REPARSE_POINT
    except (OSError, AttributeError):
        return False
