"""Home: a countdown tile for each exam (midterms from 2 weeks before, finals from 3 weeks before the first final; both set in Settings > Home), in the course's color, and the days to the last lecture."""
from datetime import date, timedelta

import pytest

from core import crud, settings
from library import homedata

pytestmark = pytest.mark.usefixtures("fresh_data")
TODAY = date(2026, 11, 27)


def _course(code, status="Active", color=None):
    cid = crud.add_course(code, "Course " + code, "Fall 2026", 0, status)
    if color:
        crud._exec("UPDATE courses SET color=? WHERE id=?", (color, cid))
    return cid


def _tiles(today=TODAY):
    return homedata.exam_countdowns(crud.list_courses(active_only=True), today)


def _in(days):
    return (TODAY + timedelta(days=days)).isoformat()


def test_no_final_tile_until_three_weeks_before_the_first_final_then_one_for_each_final():
    a, b = _course("AE 1"), _course("AE 2")
    crud.add_event("Final Exam", _in(22), a, "10:00")
    crud.add_event("AE 2 Final", _in(25), b, "14:00")
    assert _tiles() == []                                                      # 22 days before the first final: not yet
    tiles = _tiles(TODAY + timedelta(days=1))                                  # 21 days before it: both tiles show
    assert [(t["course"]["code"], t["big"], t["kind"]) for t in tiles] == [("AE 1", "21 Days", "Final"), ("AE 2", "24 Days", "Final")]
    assert tiles[0]["small"] == "AE 1 · Final Exam" and "10:00" in tiles[0]["when"]


def test_a_midterm_shows_from_two_weeks_before_its_own_day():
    a = _course("AE 1")
    crud.add_event("Midterm 2", _in(15), a)
    assert _tiles() == []
    crud.add_event("Midterm 3", _in(14), a)
    assert [(t["title"], t["big"], t["kind"]) for t in _tiles()] == [("Midterm 3", "14 Days", "Midterm")]
    assert [t["title"] for t in _tiles(TODAY + timedelta(days=1))] == ["Midterm 3", "Midterm 2"]
    crud.add_event("Exam 1", _in(3), a)                                        # any other exam counts like a midterm
    assert [t["title"] for t in _tiles()] == ["Exam 1", "Midterm 3"]


def test_the_words_today_and_tomorrow_and_what_is_over_done_or_not_active_has_no_tile():
    a, b, old = _course("AE 1"), _course("AE 2"), _course("AE 3", "Completed")
    crud.add_event("Final Exam", _in(-1), a)                                   # yesterday
    crud.add_event("Final Exam", _in(0), b)
    crud.add_event("Final Exam", _in(1), old)                                  # a course that is not active
    done = crud.add_event("Midterm 1", _in(1), a)
    assert [(t["course"]["code"], t["big"]) for t in _tiles()] == [("AE 2", "Today"), ("AE 1", "Tomorrow")]
    crud.set_event_done(done, True)
    assert [t["big"] for t in _tiles()] == ["Today"]


def test_the_tile_has_the_color_of_its_course():
    a, b = _course("AE 1", color="#aa3300"), _course("AE 2")
    crud.add_event("Midterm 1", _in(2), a)
    crud.add_event("Midterm 1", _in(3), b)
    tiles = _tiles()
    assert tiles[0]["color"] == "#aa3300" and tiles[1]["color"] == crud.course_color(crud.get_course(b))


def test_settings_home_says_how_early_the_tiles_start():
    assert settings.get_home() == {"midterm_days": 14, "final_days": 21}
    a = _course("AE 1")
    crud.add_event("Midterm 1", _in(20), a)
    crud.add_event("Final Exam", _in(30), a)
    assert _tiles() == []
    settings.set_home(midterm_days=30, final_days=40)
    assert [t["kind"] for t in _tiles()] == ["Midterm", "Final"]
    settings.set_home(midterm_days=0, final_days=0)                            # 0 hides them
    assert _tiles() == []
    settings.set_home(midterm_days=999, bogus=1)                               # kept in range, an unknown key is ignored
    assert settings.get_home() == {"midterm_days": 120, "final_days": 0}


def test_the_term_tiles_count_the_days_to_the_last_lecture():
    settings.set_semester("2026-08-24", "2026-12-08", "2026-12-18")
    stats = dict((small.split(" · ")[0], big) for big, small in homedata._term_stats(TODAY))
    assert stats["Until Last Day of Lectures"] == "11 Days" and stats["Until Winter Break"] == "22 Days"
    assert dict((s.split(" · ")[0], b) for b, s in homedata._term_stats(date(2026, 12, 8)))["Last Day of Lectures"] == "Today"
    assert not any("Lectures" in s for _b, s in homedata._term_stats(date(2026, 12, 9)))                 # the exam period: no lecture tile any more


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
    assert "Exam Countdown" in texts and "9 Days" in texts and "AE 7 · Final Exam" in texts
