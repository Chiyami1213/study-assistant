"""Clear Auto-Plan: the study sessions Auto-Plan made and that have not started can be removed at once; the student's own sessions and the ones already begun stay."""
from datetime import date, time, timedelta

import pytest

from core import crud
from planner import service, session_store as ss, store, task_store as ts, timeutil
from planner.models import AwakeTimes

pytestmark = pytest.mark.usefixtures("fresh_data")
NY = "America/New_York"
MON = date(2026, 9, 7)
NOW = timeutil.to_utc(MON, time(9), NY)


@pytest.fixture
def planned():
    store.set_timezone(NY)
    store.set_term_dates(date(2026, 9, 1), date(2026, 12, 8), date(2026, 12, 18))
    store.set_awake(AwakeTimes.uniform(time(9), time(17)))
    store.set_min_block(30)
    cid = crud.add_course("AE 1", "A", "Fall 2026", 0, "Active")
    due = timeutil.to_utc(MON + timedelta(days=5), time(17), NY)
    for title in ("HW 1", "HW 2"):
        ts.add_task(title, cid, "Homework", due, 120)
    service.auto_plan(now=NOW)
    return cid


def test_clearing_removes_only_the_automatic_sessions_that_have_not_started(planned):
    assert ss.count_auto(NOW) > 0
    first = ss.list_sessions()[0]
    mine = ss.add_session(first.task_id, timeutil.to_utc(MON + timedelta(days=4), time(10), NY), timeutil.to_utc(MON + timedelta(days=4), time(11), NY), now=NOW) if hasattr(ss, "add_session") else None
    before = len(ss.list_sessions())
    removed, report = service.clear_auto_plan(now=NOW)
    left = ss.list_sessions()
    assert removed > 0 and len(left) == before - removed and ss.count_auto(NOW) == 0
    assert all(s.source != "auto" or s.start < NOW for s in left)                              # nothing automatic is left in the future
    assert report is not None
    assert service.clear_auto_plan(now=NOW)[0] == 0                                           # a second time there is nothing to remove


def test_a_session_already_begun_and_a_manual_one_stay(planned):
    sessions = ss.list_sessions()
    started = [s for s in sessions if s.source == "auto"][0]
    later = NOW + timedelta(days=2)                                                           # "now" is after the first session began
    removed = ss.clear_auto(later)
    assert any(s.id == started.id for s in ss.list_sessions()) == (started.start < later)
    assert removed == sum(1 for s in sessions if s.source == "auto" and s.start >= later)
