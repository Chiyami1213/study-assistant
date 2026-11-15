"""Terms: a name and dates each, one active; the dates the rest of the app reads are the active term's."""
import json
from datetime import date

import pytest

import settings

pytestmark = pytest.mark.usefixtures("fresh_data")
FALL = ("Fall 2026", "2026-08-24", "2026-12-08", "2026-12-18")
SPRING = ("Spring 2027", "2027-01-11", "2027-04-28", "2027-05-07")


def test_a_clean_install_has_no_terms_and_the_default_dates():
    assert settings.list_terms() == [] and settings.get_active_term() is None and not settings.semester_set()
    assert settings.get_semester() == settings.DEFAULT_SEMESTER


def test_names_are_guessed_from_the_first_day():
    guess = settings.guess_term_name
    assert guess("2026-08-24") == "Fall 2026" and guess(date(2026, 9, 1)) == "Fall 2026" and guess("2027-01-11") == "Spring 2027"
    assert guess("2027-06-01") == "Summer 2027" and guess("2027-05-20") == "Spring 2027" and guess("2026-12-30") == "Fall 2026"


def test_an_older_settings_file_becomes_the_first_term():
    data = {"semester": {"start": "2026-08-24", "end": "2026-12-08", "exam_end": "2026-12-18"}}
    settings.SETTINGS_FILE.write_text(json.dumps(data), encoding="utf-8")
    (term,) = settings.list_terms()
    assert (term["id"], term["name"], term["start"]) == (1, "Fall 2026", "2026-08-24")
    assert settings.get_active_term()["id"] == 1 and settings.semester_set() and settings.get_semester()["end"] == "2026-12-08"
    new = settings.add_term(*SPRING)                                    # the first save writes the new layout
    assert [t["name"] for t in settings.list_terms()] == ["Fall 2026", "Spring 2027"] and settings.get_active_term()["id"] == 1 and new == 2


def test_the_first_term_is_active_and_later_ones_only_when_asked():
    a = settings.add_term(*FALL)
    b = settings.add_term(*SPRING)
    assert settings.get_active_term()["id"] == a
    settings.set_active_term(b)
    assert settings.get_active_term()["name"] == "Spring 2027"
    c = settings.add_term("Summer 2027", "2027-06-01", "2027-07-30", "2027-08-06", make_active=True)
    assert settings.get_active_term()["id"] == c


def test_the_dates_everything_reads_follow_the_active_term():
    a, b = settings.add_term(*FALL), settings.add_term(*SPRING)
    assert settings.get_semester() == {"start": "2026-08-24", "end": "2026-12-08", "exam_end": "2026-12-18"}
    settings.set_active_term(b)
    assert settings.get_semester() == {"start": "2027-01-11", "end": "2027-04-28", "exam_end": "2027-05-07"}
    assert json.loads(settings.SETTINGS_FILE.read_text(encoding="utf-8"))["semester"]["start"] == "2027-01-11"     # what older code reads


def test_set_semester_changes_the_active_term_or_makes_the_first_one():
    settings.set_semester("2026-09-01", "2026-12-10", "2026-12-20")
    (term,) = settings.list_terms()
    assert (term["name"], term["start"], term["exam_end"]) == ("Fall 2026", "2026-09-01", "2026-12-20")
    b = settings.add_term(*SPRING)
    settings.set_semester("2026-09-02", "2026-12-11", "2026-12-21")                     # the active one (Fall) changes, Spring does not
    by = {t["name"]: t for t in settings.list_terms()}
    assert by["Fall 2026"]["start"] == "2026-09-02" and by["Spring 2027"]["start"] == "2027-01-11"


def test_update_and_delete():
    a, b = settings.add_term(*FALL), settings.add_term(*SPRING)
    settings.update_term(b, "Spring 2027 (revised)", "2027-01-12", "2027-04-29", "2027-05-08")
    assert next(t for t in settings.list_terms() if t["id"] == b)["name"] == "Spring 2027 (revised)"
    with pytest.raises(ValueError, match="active term"):
        settings.delete_term(a)
    settings.delete_term(b)
    assert [t["id"] for t in settings.list_terms()] == [a]
    for call in (lambda: settings.delete_term(99), lambda: settings.update_term(99, *FALL), lambda: settings.set_active_term(99)):
        with pytest.raises(ValueError, match="does not exist"):
            call()


def test_invalid_terms_are_refused_and_nothing_is_saved():
    settings.add_term(*FALL)
    bad = [("", "2027-01-11", "2027-04-28", "2027-05-07"), ("X", "not-a-date", "2027-04-28", "2027-05-07"), ("X", "2027-05-01", "2027-04-28", "2027-05-07"),
           ("X", "2027-01-11", "2027-04-28", "2027-04-01"), ("fall 2026", "2027-01-11", "2027-04-28", "2027-05-07")]
    for args in bad:
        with pytest.raises(ValueError):
            settings.add_term(*args)
    assert [t["name"] for t in settings.list_terms()] == ["Fall 2026"]


def test_terms_are_listed_by_start_date_whatever_the_order_added():
    settings.add_term(*SPRING)
    settings.add_term(*FALL)
    assert [t["name"] for t in settings.list_terms()] == ["Fall 2026", "Spring 2027"]


def test_the_planner_reads_the_active_terms_dates():
    from planner import store
    a, b = settings.add_term(*FALL), settings.add_term(*SPRING)
    assert store.get_term().start == date(2026, 8, 24)
    settings.set_active_term(b)
    assert store.get_term().start == date(2027, 1, 11) and store.get_term().exams_end == date(2027, 5, 7)
    store.set_term_dates(date(2027, 1, 12), date(2027, 4, 29), date(2027, 5, 8))             # the planner's setup changes the active term too
    assert next(t for t in settings.list_terms() if t["id"] == b)["start"] == "2027-01-12"


def test_the_calendar_panel_state_is_remembered():
    assert settings.get_calendar_panel_open() is True
    settings.set_calendar_panel_open(False)
    assert settings.get_calendar_panel_open() is False
