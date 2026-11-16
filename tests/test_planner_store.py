"""Phase 1: the planner's setup is saved and comes back the same (a temporary database and settings file)."""
from datetime import date, time

import pytest

from core import settings
from planner import store
from planner.models import AwakeTimes, Break, DayWindow, PlannerError

pytestmark = pytest.mark.usefixtures("fresh_data")


def test_defaults_before_anything_is_saved():
    assert store.get_min_block() == 30
    assert store.get_awake() == AwakeTimes()
    assert store.list_breaks() == []
    assert not store.term_configured()
    cfg = store.load_config()
    assert cfg.min_block_minutes == 30 and cfg.term.tz == store.default_timezone()


def test_timezone_and_min_block_persist_and_are_validated():
    store.set_timezone("America/Los_Angeles")
    store.set_min_block(45)
    assert store.get_timezone() == "America/Los_Angeles" and store.get_min_block() == 45
    store.set_timezone("Europe/Paris")
    assert store.get_min_block() == 45                                   # changing one keeps the other
    with pytest.raises(PlannerError):
        store.set_timezone("Not/AZone")
    with pytest.raises(PlannerError):
        store.set_min_block(3)
    assert store.get_timezone() == "Europe/Paris" and store.get_min_block() == 45     # a refused change saves nothing


def test_awake_times_round_trip_per_weekday():
    awake = AwakeTimes.uniform(time(7, 30), time(22, 45)).with_day(5, DayWindow(time(10), time(23, 30)))
    store.set_awake(awake)
    assert store.get_awake() == awake
    store.set_awake(AwakeTimes())
    assert store.get_awake() == AwakeTimes()
    with pytest.raises(PlannerError):
        store.set_awake([DayWindow()] * 7)                              # not an AwakeTimes


def test_term_dates_are_saved_where_the_calendar_reads_them():
    store.set_term_dates(date(2027, 1, 11), date(2027, 4, 28), date(2027, 5, 7))
    assert store.term_configured()
    assert settings.get_semester() == {"start": "2027-01-11", "end": "2027-04-28", "exam_end": "2027-05-07"}
    t = store.get_term()
    assert (t.start, t.classes_end, t.exams_end) == (date(2027, 1, 11), date(2027, 4, 28), date(2027, 5, 7))


def test_invalid_term_dates_are_refused_and_nothing_changes():
    store.set_term_dates(date(2027, 1, 11), date(2027, 4, 28), date(2027, 5, 7))
    with pytest.raises(PlannerError):
        store.set_term_dates(date(2027, 5, 1), date(2027, 4, 28), date(2027, 5, 7))
    with pytest.raises(PlannerError):
        store.set_term_dates(date(2027, 1, 11), date(2027, 4, 28), date(2027, 4, 1))
    assert store.get_term().start == date(2027, 1, 11)


def test_breaks_are_the_holidays_table_and_validated():
    first = store.add_break("Spring Break", date(2027, 3, 15), date(2027, 3, 19))
    store.add_break("Reading Day", date(2027, 5, 3), date(2027, 5, 3))
    listed = store.list_breaks()
    assert [b.name for _, b in listed] == ["Spring Break", "Reading Day"]
    assert listed[0][1] == Break("Spring Break", date(2027, 3, 15), date(2027, 3, 19))
    from core import crud
    assert [h["name"] for h in crud.list_holidays()] == ["Spring Break", "Reading Day"]      # the Calendar sees the same rows
    with pytest.raises(PlannerError):
        store.add_break("Backwards", date(2027, 3, 19), date(2027, 3, 15))
    with pytest.raises(PlannerError):
        store.add_break("   ", date(2027, 3, 1), date(2027, 3, 2))
    assert len(store.list_breaks()) == 2                                 # nothing half-saved
    store.remove_break(first)
    assert [b.name for _, b in store.list_breaks()] == ["Reading Day"]


def test_load_config_ties_it_all_together():
    store.set_timezone("America/Chicago")
    store.set_term_dates(date(2027, 1, 11), date(2027, 4, 28), date(2027, 5, 7))
    store.set_min_block(20)
    store.add_break("Spring Break", date(2027, 3, 15), date(2027, 3, 19))
    store.set_awake(AwakeTimes.uniform(time(9), time(21)))
    cfg = store.load_config()
    assert cfg.term.tz == "America/Chicago" and cfg.min_block_minutes == 20
    assert cfg.awake_minutes(date(2027, 2, 2)) == 12 * 60
    assert cfg.awake_minutes(date(2027, 3, 16)) == 0                     # in the break
    assert cfg.awake_minutes(date(2027, 5, 8)) == 0                      # after the exams


def test_settings_survive_reloading_the_module():
    store.set_timezone("Asia/Tokyo")
    store.set_min_block(60)
    store.set_awake(AwakeTimes.uniform(time(6), time(22)))
    import importlib
    importlib.reload(store)                                              # nothing is cached in memory
    assert store.get_timezone() == "Asia/Tokyo" and store.get_min_block() == 60 and store.get_awake().for_weekday(0).wake == time(6)
