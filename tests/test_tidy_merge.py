"""Library tidy (duplicates, titles), merging courses, holidays with the terms, and the syllabus homework and exams on the course pages."""
from datetime import date, time, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from library import coursemerge
from core import crud
from core import database
from library import library_tidy as T
from core import settings
from planner import store, task_store as ts, timeutil
from views import tasklist_view as TL

pytestmark = pytest.mark.usefixtures("fresh_data")
APP = str(Path(__file__).resolve().parent.parent / "app.py")
TODAY = date.today()


@pytest.fixture(autouse=True)
def clean_tables():
    with database.get_conn() as conn:
        for table in ("books", "homework_pairs", "course_outline", "notes", "quizzes", "study_log", "syllabus_topics"):
            try:
                conn.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        conn.commit()


def add_file(title, data, courses=(), kind="Textbook", lecture=None):
    database.PDF_DIR.mkdir(parents=True, exist_ok=True)
    path = database.PDF_DIR / f"book_{abs(hash((title, data))) % 10 ** 8}.pdf"
    path.write_bytes(data)
    return crud.add_book(title, "", "", database.stored_path(path), 1, list(courses), kind, None, lecture)


# ---------------------------------------------------------------- duplicates
def test_files_with_the_same_content_are_found_and_the_book_with_most_courses_stays():
    a = crud.add_course("AE 1", "A", "Fall 2026", 0, "Active")
    b = crud.add_course("AE 2", "B", "Fall 2026", 0, "Active")
    first = add_file("Same Book", b"AAAA", [a])
    second = add_file("Same Book Again", b"AAAA", [a, b])
    add_file("Different", b"BBBB", [a])
    (group,) = T.find_duplicates()
    assert [x["id"] for x in group] == [second, first]                                        # the one linked to more courses comes first
    assert T.remove_duplicates([group]) == 1
    left = {x["id"]: x for x in crud.list_books()}
    assert first not in left and second in left and sorted(left[second]["course_ids"]) == sorted([a, b])
    assert list((database.DATA_DIR / "Backups").glob("Before Tidy *"))                       # the database was copied first
    assert T.find_duplicates() == []


def test_the_stored_file_stays_when_another_book_still_uses_it():
    book = add_file("One", b"CCCC")
    path = database.data_path(crud.get_book(book)["pdf_path"])
    twin = crud.add_book("Two", "", "", crud.get_book(book)["pdf_path"], 1, [], "Textbook")      # two books, one stored file
    (group,) = T.find_duplicates()
    T.remove_duplicates([group])
    assert path.exists() and len(crud.list_books()) == 1


# ---------------------------------------------------------------- titles
def test_titles_are_suggested_in_the_librarys_form_and_good_ones_are_left_alone():
    cid = crud.add_course("AE 6765", "K", "Fall 2026", 0, "Active")
    good = add_file("HW 5 Solution", b"1", [cid], "Homework Solution", "5")
    messy = add_file("Homework 6 Solution.pdf", b"2", [cid], "Homework Solution")
    note = add_file("Ch17 - Illingworth Similarity (Lec 20)", b"3", [cid], "Notes")
    plain = add_file("Fundamentals of Aerodynamics", b"4", [cid], "Textbook")
    got = {c["id"]: c for c in T.suggest_renames()}
    assert good not in got and plain not in got
    assert (got[messy]["new"], got[messy]["new_lecture"]) == ("HW 6 Solution", "6")
    assert (got[note]["new"], got[note]["new_lecture"]) == ("Illingworth Similarity", "17")
    assert T.apply_renames([got[messy], got[note]]) == 2
    assert crud.get_book(messy)["title"] == "HW 6 Solution" and crud.get_book(messy)["lecture"] == "6" and crud.get_book(note)["lecture"] == "17"
    assert T.suggest_renames() == []


# ---------------------------------------------------------------- merging courses
def make_pair():
    a = crud.add_course("MA 266", "Differential Equations", "Fall 2026", 10, "Active")
    b = crud.add_course("MA 303", "Differential Equations", "Fall 2026", 10, "Active")
    crud.add_homework(a, "HW 1", "2026-09-10", "", "")
    crud.add_homework(b, "HW 1", "2026-09-11", "", "")
    crud.add_event("Midterm 1", "2026-10-05", a, "10:00")
    crud.add_event("Midterm 1", "2026-10-06", b, "10:00")
    text = add_file("Textbook", b"T", [a, b], "Textbook")
    notes = add_file("Lec 3 Notes", b"N", [b], "Lecture Notes", "3")
    crud.add_meeting(b, [0, 2], "09:00", "09:50", "Room 1")
    ts.add_task("Reading", b, "Reading", estimate=30)
    crud.replace_outline(b, [{"level": "L", "marker": "Lec 1", "title": "Intro", "hours": "", "url": ""}])
    return a, b, text, notes


def test_a_merge_moves_everything_tags_the_titles_and_deletes_the_other_course():
    a, b, text, notes = make_pair()
    moved = coursemerge.preview(a, [b])
    assert moved["homework_pairs"] == 1 and moved["class_meetings"] == 1 and moved["tasks"] == 1
    result = coursemerge.merge(a, [b], {a: "MA 266", b: "MA 303"}, code="MA 266 / 303")
    assert [c["id"] for c in crud.list_courses(section=None) if c["id"] in (a, b)] == [a]
    assert crud.get_course(a)["code"] == "MA 266 / 303" and crud.get_course(b) is None
    assert sorted(h["title"] for h in crud.list_homework(a)) == ["HW 1 (MA 266)", "HW 1 (MA 303)"]
    assert sorted(e["title"] for e in crud.list_events("2026-01-01", "2026-12-31") if e["course_id"] == a) == ["Midterm 1 (MA 266)", "Midterm 1 (MA 303)"]
    assert crud.get_book(text)["title"] == "Textbook" and a in crud.get_book(text)["course_ids"]                      # the shared textbook is untagged and stays with the merged course
    assert crud.get_book(notes)["title"] == "Lec 3 Notes (MA 303)" and crud.get_book(notes)["course_ids"] == [a]
    assert len(crud.list_meetings(a)) == 1 and [t.title for t in ts.list_tasks(course_id=a)] == ["Reading"]
    assert crud.list_outline(a, "MA303")[0]["title"] == "Intro"                                                       # the outline is kept for that part
    assert crud.course_parts(a) == ["MA266", "MA303"] and result["tagged"] == 5 and list((database.DATA_DIR / "Backups").glob("Before Merge *"))


def test_a_merge_needs_different_tags_and_at_least_two_courses():
    a, b, *_ = make_pair()
    with pytest.raises(ValueError, match="different"):
        coursemerge.merge(a, [b], {a: "MA 266", b: "MA266"})
    with pytest.raises(ValueError, match="tag"):
        coursemerge.merge(a, [b], {a: "MA 266", b: ""})
    with pytest.raises(ValueError, match="two"):
        coursemerge.merge(a, [], {a: "MA 266"})
    assert crud.get_course(b) is not None                                                                            # nothing was changed


def test_the_merged_number_and_the_default_tags():
    cs = [{"code": "MA 266"}, {"code": "MA 303"}]
    assert coursemerge.merged_code(cs) == "MA 266 / 303" and coursemerge.merged_code([{"code": "MA 161"}, {"code": "MA 162"}, {"code": "MA 261"}]) == "MA 161 / 162 / 261"
    assert coursemerge.merged_code([{"code": "AE 100"}, {"code": "ME 200"}]) == "AE 100 / ME 200"
    assert coursemerge.default_tag({"code": "MA 266", "name": "x"}) == "MA 266"


# ---------------------------------------------------------------- holidays with the terms; class times ask first
def test_holidays_are_managed_in_manage_terms_and_not_in_edit_schedule():
    start = TODAY - timedelta(days=10)
    settings.add_term("Fall 2026", start.isoformat(), (TODAY + timedelta(days=60)).isoformat(), (TODAY + timedelta(days=70)).isoformat())
    crud.add_holiday("Fall Break", (TODAY + timedelta(days=5)).isoformat(), (TODAY + timedelta(days=8)).isoformat())
    crud.add_holiday("Far Away", "2030-01-01", "2030-01-02")
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Calendar"
    at.run()
    at.selectbox(key="cal_term").select(0); at.run()                                                                  # Manage Terms
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Holidays and Breaks" in text and "Fall Break" in text and "Far Away" not in text                          # only the holidays of that term
    assert at.button(key="hol_add") is not None
    at2 = AppTest.from_file(APP, default_timeout=90)
    at2.session_state["page"] = "Calendar"
    at2.run()
    at2.button(key="edit_schedule_open").click(); at2.run()
    assert not at2.exception and not any("Holiday" in s.value for s in at2.subheader) and not any(getattr(b, "key", "") == "hol_add" for b in at2.button)


# ---------------------------------------------------------------- the syllabus on the course pages
def test_the_syllabus_homework_and_exams_are_also_written_on_the_course_page_once():
    store.set_timezone("America/New_York")
    cid = crud.add_course("AE 6009", "Viscous", "Fall 2026", 0, "Active")
    crud.add_homework(cid, "HW 1", (TODAY + timedelta(days=3)).isoformat(), "", "")                              # the page has it already
    rows = [{"Add": True, "Title": "HW 1", "Category": "Homework", "Due Date": TODAY + timedelta(days=3), "Due Time": time(23, 59), "Estimate (Minutes)": None, "On Calendar": False},
            {"Add": True, "Title": "HW 2", "Category": "Homework", "Due Date": TODAY + timedelta(days=10), "Due Time": time(23, 59), "Estimate (Minutes)": None, "On Calendar": False},
            {"Add": True, "Title": "Midterm 1", "Category": "Exam", "Due Date": TODAY + timedelta(days=20), "Due Time": time(9, 0), "Estimate (Minutes)": None, "On Calendar": False},
            {"Add": True, "Title": "Quiz 1", "Category": "Quiz", "Due Date": TODAY + timedelta(days=5), "Due Time": time(9, 0), "Estimate (Minutes)": None, "On Calendar": False}]
    n, ev, _m, problems = TL.apply_import(cid, rows, [], store.get_term().zone, course_page=True)
    assert n == 4 and problems == []
    assert sorted(h["title"] for h in crud.list_homework(cid)) == ["HW 1", "HW 2"]                                    # HW 1 was there: not twice
    events = [e["title"] for e in crud.list_events("2020-01-01", "2100-01-01") if e["course_id"] == cid]
    assert events == ["AE 6009 Midterm 1"] and ev == 1                                                                 # an exam is an event on the page and the Calendar
    again = TL.apply_import(cid, rows, [], store.get_term().zone, course_page=True)
    assert len(crud.list_homework(cid)) == 2 and len([e for e in crud.list_events("2020-01-01", "2100-01-01") if e["course_id"] == cid]) == 1
    only_tasks = crud.add_course("AE 2", "B", "Fall 2026", 0, "Active")
    TL.apply_import(only_tasks, rows[1:2], [], store.get_term().zone)                                                  # the old behavior is still there
    assert crud.list_homework(only_tasks) == []


def test_the_buttons_are_on_the_pages():
    crud.add_course("AE 6009", "Viscous", "Fall 2026", 0, "Active")
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Courses"
    at.run()
    assert not at.exception and at.button(key="merge_courses_open") is not None
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Library"
    at.run()
    assert not at.exception and at.button(key="imp_menu_tidy") is not None
