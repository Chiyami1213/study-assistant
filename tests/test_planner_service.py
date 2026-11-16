"""Phase 4: the cushion report from the saved setup (a temporary database)."""
from datetime import date, datetime, time, timedelta, timezone

import pytest

from core import crud
from planner import commit_store as cs
from planner import service, store, task_store as ts, timeutil
from planner.models import AwakeTimes

pytestmark = pytest.mark.usefixtures("fresh_data")
NY = "America/New_York"
MON = date(2026, 9, 7)
NOW = timeutil.to_utc(MON, time(9), NY)


@pytest.fixture
def setup():
    store.set_timezone(NY)
    store.set_term_dates(date(2026, 9, 1), date(2026, 12, 8), date(2026, 12, 18))
    store.set_awake(AwakeTimes.uniform(time(9), time(17)))
    store.set_min_block(30)


def due(day, hh, mm=0):
    return timeutil.to_utc(day, time(hh, mm), NY)


def test_report_from_the_database_matches_the_hand_calculation(setup):
    cid = crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")
    cs.add_course_meeting(cid, {0}, time(9), time(10), "R1")                                              # Monday 09:00-10:00
    cs.add_event("Advising", due(MON + timedelta(days=1), 12), due(MON + timedelta(days=1), 13), commute_before=15, commute_after=15)
    ts.add_task("HW", cid, "Homework", due=due(MON + timedelta(days=2), 23, 59), estimate=600)
    rep = service.cushion_report(NOW)
    assert rep.items[0].free_minutes == 420 + 390 + 480 and rep.items[0].cushion_minutes == 690 and not rep.any_negative


def test_a_new_busy_event_lowers_the_cushion_by_its_length(setup):
    tid = ts.add_task("HW", due=due(MON + timedelta(days=1), 17), estimate=300)
    before = service.cushion_report(NOW).of(tid).cushion_minutes
    cs.add_event("Trip", due(MON + timedelta(days=1), 10), due(MON + timedelta(days=1), 12), commute_before=30)       # 150 busy minutes
    assert before - service.cushion_report(NOW).of(tid).cushion_minutes == 150


def test_a_finished_task_or_a_task_without_a_due_date_is_not_in_the_report(setup):
    done = ts.add_task("Old", due=due(MON + timedelta(days=1), 17), estimate=300)
    ts.set_done(done)
    ts.add_task("Someday")
    assert service.cushion_report(NOW).items == ()
    open_one = ts.add_task("Open", due=due(MON + timedelta(days=1), 17), estimate=300)
    assert [i.task_id for i in service.cushion_report(NOW).items] == [open_one]


def test_logged_time_raises_the_cushion(setup):
    tid = ts.add_task("HW", due=due(MON + timedelta(days=1), 17), estimate=300)
    before = service.cushion_report(NOW).of(tid).cushion_minutes
    ts.log_time(tid, 120)
    assert service.cushion_report(NOW).of(tid).cushion_minutes == before + 120


def test_breaks_and_the_awake_hours_change_the_free_time(setup):
    tid = ts.add_task("HW", due=due(MON + timedelta(days=3), 17), estimate=100)               # Thursday 17:00
    assert service.cushion_report(NOW).of(tid).free_minutes == 4 * 480
    store.add_break("Day off", MON + timedelta(days=1), MON + timedelta(days=2))
    assert service.cushion_report(NOW).of(tid).free_minutes == 2 * 480
    store.set_awake(AwakeTimes.uniform(time(10), time(14)))
    assert service.cushion_report(NOW).of(tid).free_minutes == 240 + 240                      # Monday 10:00-14:00 and Thursday 10:00-14:00; the break days give nothing


def test_free_time_for_a_range(setup):
    pieces = service.free_time(MON, MON + timedelta(days=1), NOW)
    assert pieces[0] == (NOW, due(MON, 17)) and pieces[1] == (due(MON + timedelta(days=1), 9), due(MON + timedelta(days=1), 17))
    cid = crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")
    cs.add_course_meeting(cid, {0}, time(9), time(10))
    assert service.free_time(MON, MON, NOW)[0] == (due(MON, 10), due(MON, 17))
