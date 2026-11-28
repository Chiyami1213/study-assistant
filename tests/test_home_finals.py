"""Home: from 3 weeks before the first final exam, each final exam of an active course gets a countdown tile."""
from datetime import date, timedelta

import pytest

from core import crud
from library import homedata

pytestmark = pytest.mark.usefixtures("fresh_data")
TODAY = date(2026, 11, 27)


def _course(code, status="Active"):
    return crud.add_course(code, "Course " + code, "Fall 2026", 0, status)


def _tiles(today=TODAY):
    return homedata.final_countdowns(crud.list_courses(active_only=True), today)


def test_no_tile_until_three_weeks_before_the_first_final_then_one_for_each_final():
    a, b = _course("AE 1"), _course("AE 2")
    crud.add_event("Final Exam", (TODAY + timedelta(days=22)).isoformat(), a, "10:00")
    crud.add_event("AE 2 Final", (TODAY + timedelta(days=25)).isoformat(), b, "14:00")
    assert _tiles() == []                                                      # 22 days before the first final: not yet
    tiles = _tiles(TODAY + timedelta(days=1))                                  # 21 days before it: both tiles show
    assert [(t["course"]["code"], t["big"]) for t in tiles] == [("AE 1", "21 Days"), ("AE 2", "24 Days")]
    assert tiles[0]["small"] == "AE 1 · Final Exam" and "10:00" in tiles[0]["when"]


def test_the_words_today_and_tomorrow_and_a_final_that_has_passed_has_no_tile():
    a, b = _course("AE 1"), _course("AE 2")
    crud.add_event("Final Exam", (TODAY - timedelta(days=1)).isoformat(), a)             # yesterday
    crud.add_event("Final Exam", TODAY.isoformat(), b)
    tiles = _tiles()
    assert [(t["course"]["code"], t["big"]) for t in tiles] == [("AE 2", "Today")]
    crud.add_event("Final Exam", (TODAY + timedelta(days=1)).isoformat(), a)
    assert [t["big"] for t in _tiles()] == ["Today", "Tomorrow"]


def test_midterms_other_courses_and_finals_marked_done_get_no_tile():
    a, b, old = _course("AE 1"), _course("AE 2"), _course("AE 3", "Completed")
    soon = (TODAY + timedelta(days=5)).isoformat()
    crud.add_event("Midterm 2", soon, a)
    crud.add_event("Final Exam", soon, old)                                    # a course that is not active
    done = crud.add_event("Final Exam", soon, b)
    assert [t["small"] for t in _tiles()] == ["AE 2 · Final Exam"]
    crud.set_event_done(done, True)
    assert _tiles() == []


def test_the_native_home_page_draws_the_tiles():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel
    app = QApplication.instance() or QApplication([])
    assert app
    from qtui.pages.home_page import HomePage
    a = _course("AE 7")
    crud.add_event("Final Exam", (date.today() + timedelta(days=9)).isoformat(), a, "08:00")
    texts = [l.text() for l in HomePage().findChildren(QLabel)]
    assert "Final Exams" in texts and "9 Days" in texts and "AE 7 · Final Exam" in texts
