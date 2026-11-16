"""Phase 5: sessions are saved and checked, and every change re-runs the cushion (a temporary database)."""
from datetime import date, datetime, time, timedelta, timezone

import pytest

from core import crud
from core import database
from planner import commit_store as cs
from planner import service, session_store as ss, store, task_store as ts, timeutil
from planner.models import AwakeTimes, PlannerError
from planner.sessions import AUTO, MANUAL

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
    store.add_break("Day off", date(2026, 10, 12), date(2026, 10, 13))


def at(d, hh=0, mm=0):
    return timeutil.to_utc(d, time(hh, mm), NY)


def day(n):
    return MON + timedelta(days=n)


def count():
    return database.get_conn().execute("SELECT COUNT(*) FROM study_sessions").fetchone()[0]


# ---------- adding, reading, deleting ----------
def test_add_and_read_back_a_session(setup):
    tid = ts.add_task("HW", due=at(day(2), 17), estimate=120)
    sid = ss.add_session(tid, at(MON, 10), at(MON, 11, 30), now=NOW)
    s = ss.get_session(sid)
    assert (s.task_id, s.start, s.end, s.source, s.minutes) == (tid, at(MON, 10), at(MON, 11, 30), MANUAL, 90)
    row = dict(database.get_conn().execute("SELECT * FROM study_sessions WHERE id=?", (sid,)).fetchone())
    assert row["start_utc"] == "2026-09-07T14:00:00Z" and row["created_utc"] == "2026-09-07T13:00:00Z"
    assert [x.id for x in ss.list_sessions(MON, MON)] == [sid] and ss.list_sessions(day(1), day(2)) == []
    assert [x.id for x in ss.list_sessions(task_id=tid)] == [sid]
    ss.delete_session(sid)
    assert count() == 0
    with pytest.raises(PlannerError, match="does not exist"):
        ss.get_session(sid)


def test_a_session_needs_a_task_and_valid_times(setup):
    tid = ts.add_task("HW", due=at(day(2), 17))
    with pytest.raises(PlannerError):
        ss.add_session(999, at(MON, 10), at(MON, 11))
    with pytest.raises(PlannerError):
        ss.add_session(tid, at(MON, 11), at(MON, 10))
    with pytest.raises(PlannerError):
        ss.add_session(tid, datetime(2026, 9, 7, 10), datetime(2026, 9, 7, 11))
    assert count() == 0


def test_deleting_a_task_deletes_its_sessions(setup):
    tid = ts.add_task("HW", due=at(day(2), 17))
    ss.add_session(tid, at(MON, 10), at(MON, 11))
    ts.delete_task(tid)
    assert count() == 0


# ---------- checks ----------
def test_hard_problems_always_refuse_and_soft_ones_only_without_force(setup):
    tid = ts.add_task("HW", due=at(day(2), 17))
    ss.add_session(tid, at(MON, 10), at(MON, 11))
    with pytest.raises(PlannerError, match="overlaps another"):
        ss.add_session(tid, at(MON, 10, 30), at(MON, 11, 30), force=True)           # hard: never
    with pytest.raises(PlannerError, match="break"):
        ss.add_session(tid, at(date(2026, 10, 12), 10), at(date(2026, 10, 12), 11), force=True)
    with pytest.raises(PlannerError, match="awake hours"):
        ss.add_session(tid, at(MON, 18), at(MON, 19))                              # soft: refused until forced
    ss.add_session(tid, at(MON, 18), at(MON, 19), force=True)
    assert count() == 2


def test_a_session_over_a_class_is_a_soft_problem(setup):
    cid = crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")
    cs.add_course_meeting(cid, {0}, time(12), time(13))
    tid = ts.add_task("HW", due=at(day(2), 17))
    problems = ss.check_session(at(MON, 12), at(MON, 13))
    assert [(p.kind, p.hard) for p in problems] == [("busy", False)] and "AE 6765" in problems[0].message
    with pytest.raises(PlannerError, match="AE 6765"):
        ss.add_session(tid, at(MON, 12), at(MON, 13))


# ---------- move and resize ----------
def test_move_keeps_the_length_and_makes_the_session_manual(setup):
    tid = ts.add_task("HW", due=at(day(2), 17))
    sid = ss.add_session(tid, at(MON, 10), at(MON, 11, 30), source=AUTO)
    ss.move_session(sid, at(day(1), 14))
    s = ss.get_session(sid)
    assert (s.start, s.end, s.source) == (at(day(1), 14), at(day(1), 15, 30), MANUAL)


def test_move_may_overlap_its_own_old_place_but_not_another_session(setup):
    tid = ts.add_task("HW", due=at(day(2), 17))
    a = ss.add_session(tid, at(MON, 10), at(MON, 11))
    ss.add_session(tid, at(MON, 13), at(MON, 14))
    ss.move_session(a, at(MON, 10, 30))                                            # over its own old time: fine
    with pytest.raises(PlannerError, match="overlaps another"):
        ss.move_session(a, at(MON, 13, 30))
    assert ss.get_session(a).start == at(MON, 10, 30)                              # the refused move changed nothing


def test_resize_by_minutes_or_end_and_its_validation(setup):
    tid = ts.add_task("HW", due=at(day(2), 17))
    sid = ss.add_session(tid, at(MON, 10), at(MON, 11))
    ss.resize_session(sid, minutes=90)
    assert ss.get_session(sid).end == at(MON, 11, 30)
    ss.resize_session(sid, new_end=at(MON, 12))
    assert ss.get_session(sid).end == at(MON, 12)
    for kw in (dict(), dict(minutes=30, new_end=at(MON, 11)), dict(minutes=0), dict(minutes=-5), dict(minutes=2.5), dict(new_end=at(MON, 9, 30))):
        with pytest.raises(PlannerError):
            ss.resize_session(sid, **kw)
    ss.add_session(tid, at(MON, 13), at(MON, 14))
    with pytest.raises(PlannerError, match="overlaps another"):
        ss.resize_session(sid, minutes=240)
    assert ss.get_session(sid).end == at(MON, 12)
    ss.resize_session(sid, minutes=20, force=True)                                  # shorter than the minimum: soft
    assert ss.get_session(sid).minutes == 20
    with pytest.raises(PlannerError, match="minimum"):
        ss.resize_session(sid, minutes=10)


# ---------- unplan ----------
def test_unplan_removes_only_sessions_that_have_not_started(setup):
    tid, other = ts.add_task("A", due=at(day(3), 17)), ts.add_task("B", due=at(day(3), 17))
    past = ss.add_session(tid, at(date(2026, 9, 4), 10), at(date(2026, 9, 4), 11), force=True)
    running = ss.add_session(tid, at(MON, 8, 30), at(MON, 9, 30), force=True)
    future = [ss.add_session(tid, at(day(i), 10), at(day(i), 11)) for i in (1, 2)]
    keep = ss.add_session(other, at(day(1), 12), at(day(1), 13))
    assert ss.unplan_task(tid, NOW) == 2
    assert [s.id for s in ss.list_sessions()] == [past, running, keep]
    assert ss.unplan_task(tid, NOW, include_past=True) == 2
    assert [s.id for s in ss.list_sessions()] == [keep]


# ---------- the auto-plan, stored ----------
def test_auto_plan_is_stored_and_replanned_without_duplicates(setup):
    a, b = ts.add_task("A", due=at(day(1), 17), estimate=120), ts.add_task("B", due=at(day(2), 17), estimate=60)
    result, report = service.auto_plan(NOW)
    assert result.complete and count() == 2
    first = [(s.task_id, s.start, s.end, s.source) for s in ss.list_sessions()]
    assert first == [(a, at(MON, 9), at(MON, 11), AUTO), (b, at(MON, 11), at(MON, 12), AUTO)]
    result2, _ = service.auto_plan(NOW)                                             # again: the automatic sessions are replaced, not added to
    assert count() == 2 and [(s.task_id, s.start, s.end, s.source) for s in ss.list_sessions()] == first
    assert set(result2.remove) and not report.any_negative


def test_auto_plan_leaves_manual_sessions_and_plans_around_them(setup):
    a = ts.add_task("A", due=at(day(1), 17), estimate=120)
    manual = ss.add_session(a, at(MON, 9), at(MON, 10))
    service.auto_plan(NOW)
    sessions = ss.list_sessions()
    assert (sessions[0].id, sessions[0].source) == (manual, MANUAL) and (sessions[1].start, sessions[1].end, sessions[1].source) == (at(MON, 10), at(MON, 11), AUTO)


def test_auto_plan_plans_around_classes_events_and_breaks(setup):
    cid = crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")
    cs.add_course_meeting(cid, {0}, time(9), time(11))
    cs.add_event("Advising", at(MON, 11), at(MON, 12), commute_after=30)
    a = ts.add_task("A", due=at(day(1), 17), estimate=90, course_id=cid)
    service.auto_plan(NOW)
    (s,) = ss.list_sessions()
    assert (s.start, s.end) == (at(MON, 12, 30), at(MON, 14))


# ---------- the cushion is re-run after every change ----------
def test_every_change_returns_the_new_cushion(setup):
    tid = ts.add_task("HW", due=at(day(1), 17), estimate=300)
    base = service.cushion_report(NOW).of(tid)
    assert base.cushion_minutes == 960 - 300
    sid, rep = service.add_session(tid, at(MON, 10), at(MON, 12), now=NOW)
    assert rep.of(tid).cushion_minutes == base.cushion_minutes                      # planning its own work does not change its cushion
    assert rep.of(tid).demand_minutes == 180 and rep.of(tid).free_minutes == 960 - 120
    other = ts.add_task("Other", due=at(day(1), 17), estimate=100)
    rep = service.cushion_report(NOW)
    assert rep.of(other).cushion_minutes == 960 - 120 - 180 - 100                    # the planned hours leave the free time
    rep = service.resize_session(sid, minutes=60, now=NOW)                            # 60 minutes planned for the task; the other task still needs 100
    assert rep.of(tid).demand_minutes == 240 + 100 and rep.of(tid).free_minutes == 960 - 60 and rep.of(tid).cushion_minutes == 560
    rep = service.move_session(sid, at(day(1), 9), now=NOW)
    assert rep.of(tid).cushion_minutes == 560                                        # moving work inside the deadline does not change the cushion
    removed, rep = service.unplan_task(tid, NOW)
    assert removed == 1 and rep.of(tid).demand_minutes == 300 + 100 and rep.of(tid).free_minutes == 960
    sid2, _ = service.add_session(tid, at(MON, 10), at(MON, 11), now=NOW)
    rep = service.delete_session(sid2, NOW)
    assert rep.of(tid).free_minutes == 960 and rep.of(tid).cushion_minutes == 560


def test_a_session_after_the_deadline_does_not_count_as_work_for_it(setup):
    tid = ts.add_task("HW", due=at(MON, 12), estimate=120)                           # due Monday noon
    service.add_session(tid, at(day(1), 10), at(day(1), 12), now=NOW)                # planned the day after
    x = service.cushion_report(NOW).of(tid)
    assert x.demand_minutes == 120 and x.free_minutes == 180


def test_a_full_plan_can_still_show_a_negative_cushion(setup):
    tid = ts.add_task("HW", due=at(MON, 12), estimate=400)
    result, rep = service.auto_plan(NOW)
    assert not result.complete and result.unplaced_of(tid) == 220 and rep.any_negative and rep.of(tid).cushion_minutes == -220
