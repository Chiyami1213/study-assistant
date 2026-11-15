"""Bulk import into the Library: from a zip file, or from a folder the software reads again whenever the student presses Update.

Nothing is imported before the student confirms a list of what was found. A source file is only READ (a folder on the student's own drive is never changed, never deleted); an import is a COPY
into pdfs/ of the data folder. Folder files that were imported before are remembered (`settings` key `import_sources`: size and time of each), so an Update lists only what is new, and
what changed since (an updated file replaces the stored copy of its book)."""
import io
import os
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import crud
import settings
from database import PDF_DIR, data_path, stored_path

SUPPORTED = (".pdf", ".html", ".htm")
MAX_FILE = 600 * 1024 * 1024            # a single file in a zip
MAX_TOTAL = 3 * 1024 * 1024 * 1024      # everything in a zip
MAX_FILES = 3000
SKIP_DIRS = {"__macosx", ".git", "node_modules", "$recycle.bin", "system volume information"}


@dataclass
class Candidate:
    key: str                    # where it came from: the path in the folder or in the zip (what is remembered for an Update)
    name: str                   # the file name
    size: int
    mtime: float
    status: str                 # "New", "Changed" (a stored copy exists but the file is newer) or "In Library" (already there)
    book_id: int = None         # the book a changed file replaces
    kind: str = "Textbook"
    title: str = ""
    lecture: str = ""
    course_ids: list = field(default_factory=list)
    reader: object = None       # a function that returns the bytes of the file (read only when it is imported)


# ---------------------------------------------------------------- finding files
def _skipped(parts):
    return any(p.lower() in SKIP_DIRS or p.startswith(".") for p in parts[:-1]) or parts[-1].startswith(("~$", "._", ".")) or parts[-1].lower().endswith((".tmp", ".part", ".crdownload"))


def scan_folder(folder, limit=MAX_FILES):
    """[(key, path, size, mtime)] of the pdf and html files in a folder and the folders in it. A link to another folder is not entered (nothing outside the chosen folder is read)."""
    root = Path(folder)
    out = []
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".") and not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(root)
            if p.suffix.lower() in SUPPORTED and not _skipped(rel.parts) and not p.is_symlink():
                try:
                    st = p.stat()
                except OSError:
                    continue
                out.append((str(p), p, st.st_size, st.st_mtime))
                if len(out) >= limit:
                    return out
    return sorted(out, key=lambda x: x[0].lower())


def scan_zip(data):
    """[(key, name, size, reader)] of the pdf and html files in zip bytes. Refused (ValueError): not a zip, too many files, or too large when unpacked (a zip bomb). Folders inside
    the zip are read; a zip inside the zip is not opened; a path that leaves the zip is ignored."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("That is not a zip file.")
    infos = [i for i in zf.infolist() if not i.is_dir()]
    if len(infos) > MAX_FILES * 4 or sum(i.file_size for i in infos) > MAX_TOTAL:
        raise ValueError("That zip holds too much to import at once.")
    out = []
    for i in infos:
        parts = [p for p in i.filename.replace("\\", "/").split("/") if p]
        if not parts or ".." in parts or parts[0].endswith(":") or _skipped(parts) or not parts[-1].lower().endswith(SUPPORTED) or i.file_size > MAX_FILE:
            continue
        out.append(("/".join(parts), parts[-1], i.file_size, (lambda info=i: zf.read(info))))
    return sorted(out, key=lambda x: x[0].lower())[:MAX_FILES]


# ---------------------------------------------------------------- what each file probably is
FOLDER_KINDS = (("solution", None), ("syllab", "Syllabus"), ("equation", "Equation Sheet"), ("formula", "Equation Sheet"), ("helper", "Homework Helper"), ("homework", "Homework"),
                ("assignment", "Homework"), ("problem set", "Homework"), ("midterm", "Exam"), ("final", "Exam"), ("exam", "Exam"), ("quiz", "Exam"), ("lecture", "Lecture Notes"), ("slide", "Lecture Notes"),
                ("notes", "Notes"), ("note", "Notes"), ("textbook", "Textbook"), ("book", "Textbook"), ("reference", "Textbook"), ("paper", "Textbook"))


def kind_from_folders(key):
    """The type the folders a file is in suggest ('.../AE 6765/Homework/HW 5/x.pdf' -> Homework); None when no folder says. The nearest folder counts most."""
    parts = [p.lower() for p in re.split(r"[\/]", key or "")[:-1]]
    for part in reversed(parts):
        for word, kind in FOLDER_KINDS:
            if word in part:
                return kind
    return None


def guess_fields(name, default_course=None, key=""):
    """(kind, title, lecture, course ids) guessed from the file name alone (the file itself is read when it is imported)."""
    from views import library_view as L
    stem = Path(name).stem
    kind = L.detect_kind(name, "") or kind_from_folders(key) or "Textbook"           # the file name first, then the folders it is in
    lec, clean = L.split_lecture(stem.replace("_", " ").replace("-", " ") if " " not in stem else stem)
    title = crud.fix_course_ids(L.strip_notes_prefix(clean) if kind in ("Lecture Notes", "Notes") else stem.replace("_", " ").strip())
    lecture = ""
    if kind in L.HW_KINDS:
        m = re.search(r"(?:hw|homework|problem\s*set|pset|ps)[\s_#-]*(\d+)", stem, re.I) or re.search(r"(\d+)(?!.*\d)", stem)
        lecture = m.group(1) if m else ""
        if lecture and not title.lower().startswith("hw"):
            title = f"HW {lecture}" + {"Homework Solution": " Solution", "Graded Homework": " Graded", "Homework Helper": " Helper", "Grade Explanation": " Grade Explanation"}.get(kind, "")
    elif kind in ("Lecture Notes", "Notes"):
        lecture = lec or L.guess_lecture(stem, "") or ""
    import naming
    named, named_lecture = naming.default_title(kind, name)                 # the Library's own forms: HW 5 Solution, Midterm 1 Practice, a note's topic with its number apart
    if named:
        title, lecture = named, named_lecture or lecture
    courses = {c["id"] for c in crud.list_courses(section=None)}
    guessed = L.detect_course(name, title) or L.detect_course(" ".join(re.split(r"[\/]", key or "")[:-1]), "")      # the course may be named by a folder
    ids = [guessed] if guessed in courses else ([default_course] if default_course in courses else [])
    return kind, title or stem, lecture, ids


def _stored_by_size():
    """{size: [(book id, path)]} of the files the Library keeps (read once per scan)."""
    out = {}
    for b in crud.list_books():
        try:
            p = data_path(b["pdf_path"])
            out.setdefault(p.stat().st_size, []).append((b["id"], p))
        except (OSError, TypeError):
            continue
    return out


def _digest(data):
    import hashlib
    return hashlib.sha1(data).hexdigest()


def same_file_in_library(size, reader, stored):
    """The id of a book whose stored copy has exactly the same content, or None. Only files of the same size are read and compared."""
    same = stored.get(size)
    if not same:
        return None
    try:
        mine = _digest(reader())
    except Exception:
        return None
    for book_id, path in same:
        try:
            if _digest(path.read_bytes()) == mine:
                return book_id
        except OSError:
            continue
    return None


def classify(entries, remembered=None, default_course=None):
    """Candidates for [(key, name, size, mtime, reader)]: New, Changed (remembered and different) or In Library (remembered and the same, or a book with that file name and size)."""
    remembered = remembered or {}
    names = {}
    for b in crud.list_books():
        if b.get("orig_name"):
            names.setdefault(b["orig_name"].lower(), []).append(b)
    out = []
    stored = _stored_by_size()
    for key, name, size, mtime, reader in entries:
        known = remembered.get(key)
        status, book_id = "New", None
        if known:
            if crud.get_book(known.get("book_id")) is None:
                status = "New"                                              # its book was deleted since: a new import
            elif known.get("size") != size or abs(known.get("mtime", 0) - mtime) > 1:
                status, book_id = "Changed", known["book_id"]
            else:
                status, book_id = "In Library", known["book_id"]
        elif (same := same_file_in_library(size, reader, stored)) is not None:
            status, book_id = "In Library", same                                 # the very same file, whatever it is titled
        elif name.lower() in names:
            status, book_id = "In Library", names[name.lower()][0]["id"]
        kind, title, lecture, ids = guess_fields(name, default_course, key)
        out.append(Candidate(key, name, size, mtime, status, book_id, kind, title, lecture, ids, reader))
    return sorted(out, key=priority)


def priority(c):
    """The order files are listed in: homework and exam documents first (the homework, its solution, helper, grade explanation; the exam, practice exam, preparation, reflection, equation sheet),
    then the syllabus, then notes and lecture slides, then everything else. Inside a group by type, then by title with the numbers in order."""
    from views import library_view as L
    if c.kind in L.HW_GROUP or c.kind in L.EXAM_GROUP or c.kind == "Equation Sheet":
        group = 0
    elif c.kind == "Syllabus":
        group = 1
    elif c.kind in ("Notes", "Lecture Notes"):
        group = 2
    else:
        group = 3
    kind_rank = L.KINDS.index(c.kind) if c.kind in L.KINDS else 99
    return (group, c.course_ids[0] if c.course_ids else 10 ** 9, kind_rank, crud._natural_key(c.title))


def folder_candidates(folder, default_course=None):
    remembered = settings.get_import_sources()
    entries = [(key, p.name, size, mtime, (lambda p=p: p.read_bytes())) for key, p, size, mtime in scan_folder(folder)]
    return classify(entries, remembered, default_course)


def zip_candidates(data, default_course=None):
    entries = [(key, name, size, 0.0, reader) for key, name, size, reader in scan_zip(data)]
    return classify(entries, {}, default_course)


# ---------------------------------------------------------------- importing
def import_candidate(c, remember=False, default_course=None):
    """Copy one file into the Library (a New file is a new book, a Changed file replaces the stored copy of its book). Returns the book id. The title, author, edition, year and page
    count are read from the file like the Add File window does."""
    import pdfmeta
    import syllabus
    data = c.reader()
    is_pdf = c.name.lower().endswith(".pdf")
    try:
        info = (pdfmeta.extract_info if is_pdf else pdfmeta.extract_html_info)(data, c.name)
    except Exception:
        info = {"title": "", "author": "", "edition": "", "year": "", "pages": None}
    if c.status == "Changed" and c.book_id and crud.get_book(c.book_id):
        book = crud.get_book(c.book_id)
        dest = data_path(book["pdf_path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)                                              # the stored copy is ours to replace; the source file is untouched
        crud._exec("UPDATE books SET total_pages=? WHERE id=?", (info.get("pages"), c.book_id))
        try:
            import covers
            covers.remove_cover(c.book_id)
        except Exception:
            pass
        book_id = c.book_id
    else:
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        dest = PDF_DIR / f"book_{uuid.uuid4().hex[:10]}{'.pdf' if is_pdf else '.html'}"
        dest.write_bytes(data)
        title = c.title.strip() or info.get("title") or Path(c.name).stem
        ids = c.course_ids or ([default_course] if default_course else [])
        year = info.get("year") or ("" if c.kind not in ("Lecture Notes", "Notes") else str(__import__("datetime").date.today().year))
        book_id = crud.add_book(title, info.get("author") or "", info.get("edition") or "", stored_path(dest), info.get("pages"), ids, c.kind, year, c.lecture, orig_name=c.name)
        if c.kind == "Syllabus" and is_pdf:
            try:
                syllabus.auto_build(ids, book_id, dest)
            except Exception:
                pass
    if remember:
        settings.remember_import_source(c.key, c.size, c.mtime, book_id)
    return book_id


def import_all(candidates, remember=False, default_course=None):
    """Import the given candidates. Returns (new books, replaced books, [problems])."""
    added = replaced = 0
    problems = []
    for c in candidates:
        try:
            import_candidate(c, remember, default_course)
            if c.status == "Changed":
                replaced += 1
            else:
                added += 1
        except Exception as e:
            problems.append(f"{c.name}: {e}")
    if added or replaced:
        try:
            import libbackup
            libbackup.auto()
        except Exception:
            pass
    return added, replaced, problems


# ---------------------------------------------------------------- the confirmation page
def _table(candidates, key):
    """The page where the student confirms: every file found, with its guessed type, title, lecture and course, all editable; unchecked files are not imported. Returns the checked candidates
    (with what was edited)."""
    import pandas as pd
    import streamlit as st
    from views import library_view as L
    courses = {c["id"]: crud.label(c) for c in crud.list_courses(section=None)}
    labels = ["(none)"] + list(courses.values())
    frame = pd.DataFrame([{"Import": c.status != "In Library", "File": c.key if len(c.key) < 90 else "..." + c.key[-87:], "Status": c.status, "Type": c.kind, "Title": c.title, "Lecture": c.lecture,
                           "Course": courses.get(c.course_ids[0], "(none)") if c.course_ids else "(none)"} for c in candidates])
    edited = st.data_editor(frame, key=key, hide_index=True, width="stretch", num_rows="fixed",
                            column_config={"Import": st.column_config.CheckboxColumn("Import"), "File": st.column_config.TextColumn("File", disabled=True), "Status": st.column_config.TextColumn("Status", disabled=True),
                                           "Type": st.column_config.SelectboxColumn("Type", options=L.KINDS, required=True), "Title": st.column_config.TextColumn("Title", required=True),
                                           "Lecture": st.column_config.TextColumn("Lecture / HW No."), "Course": st.column_config.SelectboxColumn("Course", options=labels)})
    by_label = {v: k for k, v in courses.items()}
    chosen = []
    for c, row in zip(candidates, edited.to_dict("records")):
        if not row["Import"]:
            continue
        c.kind, c.title, c.lecture = row["Type"], (row["Title"] or "").strip() or c.title, (row["Lecture"] or "").strip()
        c.course_ids = [by_label[row["Course"]]] if row["Course"] in by_label else []
        chosen.append(c)
    return chosen


def _summary(added, replaced, problems):
    import streamlit as st
    text = f"Imported {added} file{'s' if added != 1 else ''}" + (f" and updated {replaced}" if replaced else "") + "."
    st.session_state["lib_toast"] = text + (f" Not imported: {'; '.join(problems[:3])}" if problems else "")


def zip_dialog(default_course=None):
    """Import a zip of pdf and html files: choose it, check what it holds on the confirmation page, then import."""
    import streamlit as st

    @st.dialog("Import a Zip", width="large")
    def dialog():
        up = st.file_uploader("Zip File", type=["zip"], key="bulk_zip")
        st.caption("The zip may hold folders; every pdf and html file in it is listed. Nothing is imported until you press Import.")
        if not up:
            return
        try:
            cands = zip_candidates(up.getvalue(), default_course)
        except ValueError as e:
            st.error(str(e))
            return
        if not cands:
            st.warning("That zip has no pdf or html files.", icon=":material/warning:")
            return
        new = sum(c.status != "In Library" for c in cands)
        st.markdown(f"**{len(cands)} files found, {new} new.** Check the type, title and course of each, and uncheck what you do not want.")
        chosen = _table(cands, f"bulk_zip_table_{up.file_id}")
        if st.button(f"Import {len(chosen)} File{'s' if len(chosen) != 1 else ''}", key="bulk_zip_go", type="primary", disabled=not chosen):
            _summary(*import_all(chosen, False, default_course))
            st.rerun()
    dialog()


def folder_dialog(course_id=None):
    """Update the Library from the chosen folder: the new and the changed files are listed for confirmation; files imported before are not listed again."""
    import streamlit as st

    @st.dialog("Update From Folder", width="large")
    def dialog():
        import folderpick
        own = settings.get_own_import_folder(course_id)
        folder = settings.get_import_folder(course_id)
        label = "this course" if course_id else "the Library"
        st.markdown(f"**Folder for {label}:** " + (f"`{folder}`" + ("" if own or not course_id else " (the general folder)") if folder else "none chosen yet"))
        a, b = st.columns([1, 3])
        if a.button("Choose Folder", key="imp_choose", icon=":material/folder_open:"):
            picked = folderpick.pick(folder or "", "Choose the folder your pdf and html files are in")
            if picked:
                settings.set_import_folder(picked, course_id)
                st.rerun()
        typed = b.text_input("Folder", own or folder, key=f"imp_path_{course_id}", label_visibility="collapsed", placeholder="Or type the folder path here")
        if typed.strip() and typed.strip() != (own or folder) and Path(typed.strip()).is_dir():
            settings.set_import_folder(typed.strip(), course_id)
            st.rerun()
        if not folder:
            st.caption("Choose the folder where your pdf and html files are kept. The software only reads it; your files there are never changed.")
            return
        if not Path(folder).is_dir():
            st.warning("That folder can not be found. Choose it again.", icon=":material/warning:")
            return
        with st.spinner("Reading the folder..."):
            cands = folder_candidates(folder, course_id)
        fresh = [c for c in cands if c.status != "In Library"]
        st.caption(f"{len(cands)} pdf and html files in the folder: {sum(c.status == 'New' for c in cands)} new, {sum(c.status == 'Changed' for c in cands)} changed since they were imported, "
                   f"{sum(c.status == 'In Library' for c in cands)} already in the Library.")
        if not fresh:
            st.success("The Library is up to date with this folder.", icon=":material/check_circle:")
            for c in cands:                                                  # remember the files that were already there, so a later change is noticed
                if c.book_id:
                    settings.remember_import_source(c.key, c.size, c.mtime, c.book_id)
            return
        chosen = _table(fresh, f"imp_table_{course_id}_{len(fresh)}")
        if st.button(f"Import {len(chosen)} File{'s' if len(chosen) != 1 else ''}", key="imp_go", type="primary", disabled=not chosen):
            for c in cands:
                if c.status == "In Library" and c.book_id:
                    settings.remember_import_source(c.key, c.size, c.mtime, c.book_id)
            _summary(*import_all(chosen, True, course_id))
            st.rerun()
    dialog()


def add_syllabus(course_id, name, data, part=None):
    """Add a syllabus file to the Library as the Syllabus of a course and read it: the grading breakdown, the letter-grade scale and the instructor are kept for the course page (an outline
    that was not typed by hand follows it). For one part of a merged course the data is kept for that part. Returns (book id, the data read or None)."""
    import syllabus
    before = syllabus.load(course_id)
    candidate = Candidate(key=name, name=name, size=len(data), mtime=0.0, status="New", kind="Syllabus", title=f"Syllabus ({part})" if part else "Syllabus", course_ids=[course_id],
                          reader=lambda: data)
    book_id = import_candidate(candidate)                                    # a pdf is read as it is added (syllabus.auto_build)
    if part:
        built = syllabus.load(course_id)
        if built:
            syllabus.save(course_id, built, part)
        if before:
            syllabus.save(course_id, before)
        else:
            (syllabus.DIR / f"{course_id}.json").unlink(missing_ok=True)
    return book_id, syllabus.load(course_id, part)
