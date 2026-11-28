"""Course Homework tab: a homework that is handed in and has no grade yet is listed under Not Graded, not under Upcoming."""
from datetime import date, timedelta

import pytest

from core import crud
from library import coursedata as cd

pytestmark = pytest.mark.usefixtures("fresh_data")
TODAY = date.today()


def _day(n):
    return (TODAY + timedelta(days=n)).isoformat()


def _setup():
    cid = crud.add_course("AE 1", "Course", "Fall 2026", 0, "Active")
    ids = {name: crud.add_homework(cid, name, due, "", "") for name, due in
           (("HW 8", _day(-10)), ("HW 9", _day(1)), ("HW 10", _day(5)), ("HW 7", _day(-20)), ("HW 6", _day(-30)))}
    crud.set_homework_status(ids["HW 9"], "verified")                         # handed in, due tomorrow
    crud.set_homework_status(ids["HW 8"], "verified")                         # handed in, due date passed, not graded yet
    crud.set_homework_status(ids["HW 7"], "verified")
    crud.set_homework_grade(ids["HW 7"], 18, 20)                              # graded
    return crud.get_course(cid), ids


def _groups(course, finished=False):
    items = cd._homework_items(course)
    up, ng, past = cd.homework_groups(items, TODAY.isoformat(), finished)
    return [h["title"] for h in up], [h["title"] for h in ng], [h["title"] for h in past]


def test_a_handed_in_homework_without_a_grade_is_under_not_graded_whatever_its_date():
    course, _ids = _setup()
    up, ng, past = _groups(course)
    assert up == ["HW 10"] and ng == ["HW 8", "HW 9"]
    assert past == ["HW 6", "HW 7"]                                           # overdue and graded ones stay in Past


def test_a_grade_moves_it_out_of_not_graded_and_a_completed_course_has_no_upcoming():
    course, ids = _setup()
    crud.set_homework_grade(ids["HW 9"], 20, 20)
    up, ng, past = _groups(crud.get_course(course["id"]))
    assert ng == ["HW 8"] and "HW 9" in up                                    # graded and still ahead: back in Upcoming's date order
    up, ng, past = _groups(course, finished=True)
    assert up == [] and ng == ["HW 8"] and "HW 9" in past and "HW 10" in past


def test_the_native_homework_tab_shows_the_section():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
    app = QApplication.instance() or QApplication([])
    assert app
    from qtui.pages.courses_page import CoursesPage
    course, _ids = _setup()
    holder = QWidget()
    lay = QVBoxLayout(holder)
    CoursesPage()._tab_homework(lay, course)
    texts = [l.text() for l in holder.findChildren(QLabel)]
    assert "Upcoming Homework (1)" in texts
    assert "Not Graded (2)" in texts and "Past Homework (2)" in texts
