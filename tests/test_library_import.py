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


def pdf(n):
    """A pdf with its own content (the same bytes in two files are the same file, which the Library notices)."""
    return PDF + b"\n%" + str(n).encode()


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
    data = make_zip({"AE 6009 HW4.pdf": pdf(1), "Lec 3 Thermal.html": HTML, "extra.pdf": pdf(2)})
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
    good, bad = LI.zip_candidates(make_zip({"a.pdf": pdf(1), "b.pdf": pdf(2)}), None)
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
    (folder / "AE 6009 HW4.pdf").write_bytes(pdf(1))
    settings.set_import_folder(str(folder), cid)
    assert settings.get_import_folder(cid) == str(folder) and settings.get_import_folder(999) == "" and settings.get_own_import_folder(cid) == str(folder)
    first = LI.folder_candidates(str(folder), cid)
    assert {c.status for c in first} == {"New"} and crud.list_books() == []
    assert LI.import_all(first, True, cid)[:2] == (2, 0)
    assert {c.status for c in LI.folder_candidates(str(folder), cid)} == {"In Library"}                  # nothing to do the second time
    before = {b["orig_name"]: LI.data_path(b["pdf_path"]).read_bytes() for b in crud.list_books()}
    source.write_bytes(HTML + b"<p>newer</p>")
    os.utime(source, (time.time() + 10, time.time() + 10))
    (folder / "new.pdf").write_bytes(pdf(2))
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


# ---------------------------------------------------------------- the same file under another title; the folders a file is in
def test_a_file_that_is_already_in_the_library_under_another_name_is_not_new(tmp_path):
    from database import PDF_DIR, stored_path
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    stored = PDF_DIR / "book_old.pdf"
    stored.write_bytes(pdf(7))
    crud.add_book("Some Old Title", "", "", stored_path(stored), 1, [], "Textbook")                   # imported long ago, no file name kept
    (tmp_path / "different name.pdf").write_bytes(pdf(7))
    (tmp_path / "other.pdf").write_bytes(pdf(8))
    statuses = {c.name: c for c in LI.folder_candidates(str(tmp_path))}
    assert statuses["different name.pdf"].status == "In Library" and statuses["different name.pdf"].book_id and statuses["other.pdf"].status == "New"


def test_the_folders_a_file_is_in_tell_its_type_and_its_course():
    cid = crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")
    kind = lambda key: LI.guess_fields(key.rsplit("/", 1)[-1], None, key)[0]
    assert kind("AE 6765/Homework/Homework 5/AE6765_HW5_Prob2.pdf").startswith("Homework")
    assert kind("AE 6765/Notes/chapter one.pdf") == "Notes" and kind("AE 6765/Lecture/slides week 2.pdf") == "Lecture Notes"
    assert kind("AE 6765/Textbooks/Thermodynamics.pdf") == "Textbook" and kind("AE 6765/Midterm 1/stats.pdf") == "Exam"
    assert kind("loose/whatever.pdf") == "Textbook"                                                          # nothing says: a textbook, like the Add File window
    assert LI.guess_fields("something.pdf", None, "Fall 2026/AE 6765/Notes/something.pdf")[3] == [cid]       # the course is named by a folder
    assert LI.kind_from_folders("a/Solutions/b.pdf") is None


def test_an_imported_file_gets_the_title_forms_the_library_already_uses():
    cid = crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")
    data = make_zip({"AE6765 Homework 5 Solution.pdf": pdf(1), "AE6765 Midterm 1 Practice.pdf": pdf(2), "AE6765 Homework 5 Grades.html": HTML,
                     "AE6009 Ch17 - Illingworth-Levy Similarity (Lec 20).html": HTML + b"<!--2-->"})
    by = {c.name: c for c in LI.zip_candidates(data, cid)}
    assert (by["AE6765 Homework 5 Solution.pdf"].kind, by["AE6765 Homework 5 Solution.pdf"].title, by["AE6765 Homework 5 Solution.pdf"].lecture) == ("Homework Solution", "HW 5 Solution", "5")
    assert by["AE6765 Midterm 1 Practice.pdf"].title == "Midterm 1 Practice" and by["AE6765 Homework 5 Grades.html"].title == "HW 5 Grade Explanation"
    note = by["AE6009 Ch17 - Illingworth-Levy Similarity (Lec 20).html"]
    assert (note.title, note.lecture) == ("Illingworth-Levy Similarity", "17")
    LI.import_all([by["AE6765 Homework 5 Solution.pdf"]])                                                        # and that is how it is kept
    assert crud.list_books()[0]["title"] == "HW 5 Solution"


def test_homework_and_exam_documents_are_listed_first():
    names = ["Textbook chapter.pdf", "AE6765 Ch3 - Notes on Entropy.html", "AE6765 Homework 2.pdf", "AE6765 Midterm 1.pdf", "AE6765 Syllabus.pdf", "AE6765 Homework 10.pdf", "AE6765 Homework 2 Solution.pdf"]
    data = make_zip({n: HTML + str(i).encode() for i, n in enumerate(names)})
    order = [c.title for c in LI.zip_candidates(data)]
    assert [c.kind for c in LI.zip_candidates(data)][:5] == ["Homework", "Homework", "Homework Solution", "Exam", "Syllabus"] or order[:3] == ["HW 2", "HW 10", "HW 2 Solution"]
    kinds = [c.kind for c in LI.zip_candidates(data)]
    assert max(kinds.index(k) for k in ("Homework", "Homework Solution", "Exam")) < kinds.index("Syllabus") < min(i for i, k in enumerate(kinds) if k in ("Notes", "Lecture Notes"))
    assert order.index("HW 2") < order.index("HW 10")                                                           # the numbers are in order


# ---------------------------------------------------------------- a syllabus added on the course page
def syllabus_pdf():
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Course Syllabus\nProfessor: Dr. Ada Lovelace\nGrading\nHomework 30%\nMidterm 1 30%\nFinal Exam 40%\nA 90-100\nB 80-89\nC 70-79", fontsize=11)
    return doc.tobytes()


def test_a_syllabus_added_on_the_course_page_is_a_library_file_and_is_read(tmp_path):
    import syllabus
    cid = crud.add_course("AE 6009", "Viscous Fluid Flow", "Fall 2026", 0, "Active")
    book_id, data = LI.add_syllabus(cid, "AE6009 Syllabus.pdf", syllabus_pdf())
    book = crud.get_book(book_id)
    assert book["kind"] == "Syllabus" and book["title"] == "Syllabus" and cid in book["course_ids"]
    assert [(r["item"], r["percent"]) for r in data["rows"]] == [("Homework", 30), ("Midterm 1", 30), ("Final Exam", 40)]
    assert [r["grade"] for r in data["scale"]] == ["A", "B", "C"] and data["book"] == book_id
    assert data["rows"][1]["kind"] == "event:Midterm 1"


def test_a_syllabus_for_one_part_of_a_merged_course_leaves_the_other_parts_alone():
    import syllabus
    cid = crud.add_course("MA 266 / 303", "Differential Equations", "Fall 2026", 0, "Active")
    syllabus.save(cid, {"book": 0, "rows": [{"item": "Old", "percent": 100, "kind": None}], "scale": []})
    book_id, data = LI.add_syllabus(cid, "syl.pdf", syllabus_pdf(), "MA303")
    assert [r["item"] for r in data["rows"]] == ["Homework", "Midterm 1", "Final Exam"] and crud.get_book(book_id)["title"] == "Syllabus (MA 303)"
    assert syllabus.load(cid)["rows"][0]["item"] == "Old"                                                          # the course's own file is as it was


def test_the_overview_has_add_and_edit_syllabus_and_an_edit_keeps_the_students_changes():
    import syllabus
    from pathlib import Path as P
    from streamlit.testing.v1 import AppTest
    app = str(P(__file__).resolve().parent.parent / "app.py")
    cid = crud.add_course("AE 6009", "Viscous Fluid Flow", "Fall 2026", 0, "Active")
    at = AppTest.from_file(app, default_timeout=90)
    at.session_state["page"] = "Courses"
    at.session_state["open_course"] = cid
    at.run()
    assert not at.exception and at.button(key=f"syl_add_{cid}") is not None and at.button(key=f"syl_edit_{cid}").disabled        # nothing to edit yet
    LI.add_syllabus(cid, "syl.pdf", syllabus_pdf())
    at = AppTest.from_file(app, default_timeout=90)
    at.session_state["page"] = "Courses"
    at.session_state["open_course"] = cid
    at.run()
    assert not at.exception and not at.button(key=f"syl_edit_{cid}").disabled
    data = syllabus.load(cid)
    data["rows"][0]["percent"] = 35
    data["manual"] = True
    syllabus.save(cid, data)                                                                                          # what the edit dialog saves
    assert syllabus.load(cid)["rows"][0]["percent"] == 35 and syllabus.load(cid)["manual"] is True
