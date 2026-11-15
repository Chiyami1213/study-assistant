"""Bulk import: a zip, or a folder that is read again on Update. Nothing is imported before it is confirmed; sources are only read."""
import io
import os
import time
import zipfile
from pathlib import Path

import pytest

import crud
import settings
from views import library_import as LI

pytestmark = pytest.mark.usefixtures("fresh_data", "no_books")
HTML = b"<html><head><title>Lec 3 Thermal Boundary Layer</title></head><body><p>hello</p></body></html>"
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"


@pytest.fixture
def no_books():
    import database
    with database.get_conn() as conn:
        conn.execute("DELETE FROM books")
        conn.commit()


def make_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


# ---------------------------------------------------------------- finding files
def test_a_zip_lists_only_pdf_and_html_files_inside_folders_and_ignores_the_rest():
    data = make_zip({"AE 6009/Lec 3 notes.html": HTML, "AE 6009/hw4.pdf": PDF, "readme.txt": b"x", "__MACOSX/._hw4.pdf": b"x", "AE 6009/.hidden.pdf": PDF, "~$tmp.pdf": PDF,
                     "../evil.pdf": PDF, "C:/abs.pdf": PDF, "inner.zip": b"PK", "a/b/c.HTM": HTML})
    found = [(key, name) for key, name, _size, _reader in LI.scan_zip(data)]
    assert found == [("a/b/c.HTM", "c.HTM"), ("AE 6009/hw4.pdf", "hw4.pdf"), ("AE 6009/Lec 3 notes.html", "Lec 3 notes.html")] or sorted(k for k, _ in found) == sorted(["a/b/c.HTM", "AE 6009/hw4.pdf", "AE 6009/Lec 3 notes.html"])
    with pytest.raises(ValueError, match="not a zip"):
        LI.scan_zip(b"not a zip at all")


def test_a_zip_that_unpacks_too_large_is_refused(monkeypatch):
    monkeypatch.setattr(LI, "MAX_TOTAL", 100)
    with pytest.raises(ValueError, match="too much"):
        LI.scan_zip(make_zip({"a.pdf": PDF, "b.pdf": PDF * 10}))


def test_a_folder_scan_reads_subfolders_and_skips_hidden_and_temporary_files(tmp_path):
    (tmp_path / "AE 6009").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "AE 6009" / "Lec 1.html").write_bytes(HTML)
    (tmp_path / "AE 6009" / "~$Lec 2.html").write_bytes(HTML)
    (tmp_path / "AE 6009" / "notes.docx").write_bytes(b"x")
    (tmp_path / ".git" / "x.pdf").write_bytes(PDF)
    (tmp_path / "top.pdf").write_bytes(PDF)
    names = sorted(p.name for _k, p, _s, _m in LI.scan_folder(tmp_path))
    assert names == ["Lec 1.html", "top.pdf"] and LI.scan_folder(tmp_path / "missing") == []


# ---------------------------------------------------------------- what each file probably is
def test_the_type_title_lecture_and_course_are_guessed_from_the_file_name():
    cid = crud.add_course("AE 6009", "Viscous Fluid Flow", "Fall 2026", 0, "Active")
    kind, title, lecture, ids = LI.guess_fields("AE 6009 HW4.pdf", None)
    assert kind.startswith("Homework") and title.startswith("HW 4") and lecture == "4" and ids == [cid]
    kind, title, lecture, ids = LI.guess_fields("Lec 3 Thermal Boundary Layer.html", cid)
    assert lecture in ("3", "Lec 3") and ids == [cid]                                           # no course in the name: the course the update is for
    assert LI.guess_fields("something.pdf", None)[3] == []


# ---------------------------------------------------------------- confirmation first, import second
def test_importing_a_zip_adds_books_only_for_the_checked_files_and_never_twice():
    cid = crud.add_course("AE 6009", "Viscous Fluid Flow", "Fall 2026", 0, "Active")
    data = make_zip({"AE 6009 HW4.pdf": PDF, "Lec 3 Thermal.html": HTML, "extra.pdf": PDF})
    cands = LI.zip_candidates(data, cid)
    assert len(cands) == 3 and all(c.status == "New" for c in cands) and crud.list_books() == []     # looking adds nothing
    chosen = [c for c in cands if c.name != "extra.pdf"]
    added, replaced, problems = LI.import_all(chosen, False, cid)
    assert (added, replaced, problems) == (2, 0, [])
    books = crud.list_books()
    assert len(books) == 2 and all(cid in b["course_ids"] for b in books) and {b["orig_name"] for b in books} == {"AE 6009 HW4.pdf", "Lec 3 Thermal.html"}
    assert all(data_path_exists for data_path_exists in (LI.data_path(b["pdf_path"]).exists() for b in books))
    again = LI.zip_candidates(data, cid)
    assert {c.name: c.status for c in again} == {"AE 6009 HW4.pdf": "In Library", "Lec 3 Thermal.html": "In Library", "extra.pdf": "New"}


def test_the_edited_type_title_and_course_are_what_is_imported():
    cid = crud.add_course("AE 6009", "Viscous Fluid Flow", "Fall 2026", 0, "Active")
    (c,) = LI.zip_candidates(make_zip({"whatever.pdf": PDF}), None)
    c.kind, c.title, c.lecture, c.course_ids = "Textbook", "My Own Title", "", [cid]
    LI.import_all([c])
    (book,) = crud.list_books()
    assert (book["title"], book["kind"], book["course_ids"]) == ("My Own Title", "Textbook", [cid])


def test_a_bad_file_is_reported_and_the_others_still_import():
    good, bad = LI.zip_candidates(make_zip({"a.pdf": PDF, "b.pdf": PDF}), None)
    bad.reader = lambda: (_ for _ in ()).throw(OSError("disk error"))
    added, replaced, problems = LI.import_all([good, bad])
    assert added == 1 and len(problems) == 1 and "b.pdf" in problems[0]


# ---------------------------------------------------------------- Update From Folder
def test_an_update_lists_new_files_then_only_changed_ones_and_replaces_the_stored_copy(tmp_path):
    cid = crud.add_course("AE 6009", "Viscous Fluid Flow", "Fall 2026", 0, "Active")
    folder = tmp_path / "files"
    folder.mkdir()
    source = folder / "Lec 3 Thermal.html"
    source.write_bytes(HTML)
    (folder / "AE 6009 HW4.pdf").write_bytes(PDF)
    settings.set_import_folder(str(folder), cid)
    assert settings.get_import_folder(cid) == str(folder) and settings.get_import_folder(999) == "" and settings.get_own_import_folder(cid) == str(folder)
    first = LI.folder_candidates(str(folder), cid)
    assert {c.status for c in first} == {"New"} and crud.list_books() == []
    assert LI.import_all(first, True, cid)[:2] == (2, 0)
    assert {c.status for c in LI.folder_candidates(str(folder), cid)} == {"In Library"}                  # nothing to do the second time
    before = {b["orig_name"]: LI.data_path(b["pdf_path"]).read_bytes() for b in crud.list_books()}
    source.write_bytes(HTML + b"<p>newer</p>")
    os.utime(source, (time.time() + 10, time.time() + 10))
    (folder / "new.pdf").write_bytes(PDF)
    statuses = {c.name: c.status for c in LI.folder_candidates(str(folder), cid)}
    assert statuses == {"Lec 3 Thermal.html": "Changed", "AE 6009 HW4.pdf": "In Library", "new.pdf": "New"}
    cands = [c for c in LI.folder_candidates(str(folder), cid) if c.status != "In Library"]
    assert LI.import_all(cands, True, cid)[:2] == (1, 1)
    books = {b["orig_name"]: b for b in crud.list_books()}
    assert len(books) == 3 and LI.data_path(books["Lec 3 Thermal.html"]["pdf_path"]).read_bytes().endswith(b"<p>newer</p>")
    assert source.read_bytes().endswith(b"<p>newer</p>") and before["Lec 3 Thermal.html"] != LI.data_path(books["Lec 3 Thermal.html"]["pdf_path"]).read_bytes()
    assert {c.status for c in LI.folder_candidates(str(folder), cid)} == {"In Library"}


def test_a_file_whose_book_was_deleted_is_new_again_and_a_course_folder_beats_the_general_one(tmp_path):
    folder = tmp_path / "f"
    folder.mkdir()
    (folder / "a.pdf").write_bytes(PDF)
    LI.import_all(LI.folder_candidates(str(folder)), True)
    (book,) = crud.list_books()
    crud.delete_book(book["id"])
    assert [c.status for c in LI.folder_candidates(str(folder))] == ["New"]
    settings.set_import_folder("C:/general")
    cid = crud.add_course("AE 1", "x", "Fall 2026", 0, "Active")
    assert settings.get_import_folder(cid) == "C:/general"
    settings.set_import_folder(str(folder), cid)
    assert settings.get_import_folder(cid) == str(folder) and settings.get_import_folder() == "C:/general"
    settings.set_import_folder("", cid)
    assert settings.get_import_folder(cid) == "C:/general"


def test_the_buttons_are_on_the_library_and_the_course_page():
    from pathlib import Path as P
    from streamlit.testing.v1 import AppTest
    app = str(P(__file__).resolve().parent.parent / "app.py")
    cid = crud.add_course("AE 6009", "Viscous Fluid Flow", "Fall 2026", 0, "Active")
    at = AppTest.from_file(app, default_timeout=90)
    at.session_state["page"] = "Library"
    at.run()
    assert not at.exception and at.button(key="imp_menu_folder") is not None and at.button(key="imp_menu_zip") is not None
    at = AppTest.from_file(app, default_timeout=90)
    at.session_state["page"] = "Courses"
    at.session_state["open_course"] = cid
    at.run()
    assert not at.exception and at.button(key="course_update_files") is not None
