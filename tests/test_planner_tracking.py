"""Phase 7: time logs, the study timer, planned against used, and suggested estimates."""
from datetime import date, datetime, time, timedelta, timezone

import pytest

import crud
import database
from planner import service, session_store as ss, store, task_store as ts, timeutil, track_store as tr, tracking as K
from planner import sessions as S
from planner import tasks as T
from planner.models import AwakeTimes, PlannerError

NY = "America/New_York"
BASE = datetime(2026, 9, 7, 14, 0, tzinfo=timezone.utc)


def at_min(m):
    return BASE + timedelta(minutes=m)


def task(id, minutes=120, logged=0, category="Homework", course=None, state="todo", due=None):
    return T.Task(id, f"T{id}", course, category, due, minutes, None, state, logged)


def sess(id, task_id, start_min, end_min):
    return S.Session(id, task_id, at_min(start_min), at_min(end_min), S.AUTO)


# ---------- the clock ----------
def test_timer_minutes_round_to_the_nearest_minute_and_are_cut_at_twelve_hours():
    s = BASE
    cases = [(0, 0), (29, 0), (30, 1), (89, 1), (90, 2), (3600, 60), (7200 + 20, 120), (12 * 3600, 720), (20 * 3600, 720)]
    for seconds, expected in cases:
        assert K.timer_minutes(s, s + timedelta(seconds=seconds)) == expected, seconds
    assert K.timer_minutes(s, s - timedelta(minutes=5)) == 0                                  # a clock that went backwards logs nothing


# ---------- planned against used ----------
def test_usage_adds_up_the_estimate_the_plan_and_the_time_used():
    t = task(1, minutes=120, logged=50)
    sessions = [sess(1, 1, -120, -60), sess(2, 1, 60, 120), sess(3, 1, 300, 360), sess(9, 2, 0, 600)]
    logs = [K.TimeLog(1, 1, at_min(-120), 50, 1), K.TimeLog(2, 2, at_min(0), 99, 9)]
    u = K.planned_vs_used(t, sessions, logs, BASE)
    assert (u.estimate_minutes, u.planned_minutes, u.used_minutes, u.left_minutes, u.over_estimate) == (120, 180, 50, 70, False)
    assert u.unplanned_minutes == 0                                                          # 70 left, 120 minutes still planned ahead
    assert [(x.session_id, x.planned_minutes, x.used_minutes) for x in u.sessions] == [(1, 60, 50), (2, 60, 0), (3, 60, 0)]


def test_session_statuses():
    t = task(1)
    now = BASE
    sessions = [sess(1, 1, -120, -60), sess(2, 1, -240, -180), sess(3, 1, -360, -300), sess(4, 1, 30, 90), sess(5, 1, -10, 50), sess(6, 1, -10, 50), sess(7, 1, -600, -540)]
    logs = [K.TimeLog(1, 1, at_min(-120), 60, 1), K.TimeLog(2, 1, at_min(-240), 20, 2), K.TimeLog(3, 1, at_min(-10), 60, 6)]
    by = {x.session_id: x.status for x in K.planned_vs_used(t, sessions, logs, now, running_session_id=5).sessions}
    assert by == {1: "done", 2: "partial", 3: "missed", 4: "upcoming", 5: "running", 6: "done", 7: "missed"}
    inside = {x.session_id: x.status for x in K.planned_vs_used(t, [sess(5, 1, -10, 50)], [], now).sessions}
    assert inside == {5: "now"}


def test_progress_of_a_session_is_between_zero_and_one():
    assert K.SessionUsage(1, 60, 30, "partial").progress == 0.5 and K.SessionUsage(1, 60, 90, "done").progress == 1.0 and K.SessionUsage(1, 0, 5, "done").progress == 0.0


def test_over_the_estimate_and_unplanned_time():
    t = task(1, minutes=60, logged=90)
    u = K.planned_vs_used(t, [], [], BASE)
    assert u.over_estimate and u.left_minutes == 0 and u.unplanned_minutes == 0
    t2 = task(2, minutes=300, logged=60)
    u2 = K.planned_vs_used(t2, [sess(1, 2, 30, 90)], [], BASE)
    assert u2.left_minutes == 240 and u2.unplanned_minutes == 180


# ---------- suggested estimates ----------
def done(id, minutes, category="Homework", course=1, logged=None):
    return task(id, 100, minutes if logged is None else logged, category, course, "done")


def test_nothing_is_suggested_without_enough_finished_work():
    assert K.suggest_estimate([], "Homework") is None
    assert K.suggest_estimate([done(1, 90)], "Homework") is None
    assert K.suggest_estimate([done(1, 90), task(2, logged=50), done(3, 0), done(4, 60, "Quiz")], "Homework") is None      # open, unlogged and other categories do not count
    with pytest.raises(PlannerError):
        K.suggest_estimate([], "Party")


def test_the_suggestion_is_the_median_rounded_to_five_minutes():
    s = K.suggest_estimate([done(1, 90), done(2, 120), done(3, 180)], "Homework")
    assert (s.minutes, s.samples, s.scope, s.low, s.high) == (120, 3, "category", 90, 180)
    assert K.suggest_estimate([done(1, 90), done(2, 121)], "Homework").minutes == 105                # median 105.5 -> 105
    assert K.suggest_estimate([done(1, 61), done(2, 62), done(3, 63)], "Homework").minutes == 60


def test_the_same_course_is_preferred_when_it_has_enough_samples():
    tasks = [done(1, 60, course=1), done(2, 80, course=1), done(3, 300, course=2), done(4, 320, course=2), done(5, 340, course=2)]
    mine = K.suggest_estimate(tasks, "Homework", course_id=1)
    assert (mine.minutes, mine.samples, mine.scope) == (70, 2, "course")
    other = K.suggest_estimate(tasks, "Homework", course_id=3)                                        # a course with no history: everyone's
    assert (other.scope, other.samples) == ("category", 5)
    one_only = K.suggest_estimate([done(1, 60, course=1), done(2, 300, course=2), done(3, 320, course=2)], "Homework", course_id=1)
    assert one_only.scope == "category"                                                                 # one finished task is too little for its own course


def test_the_suggestion_stays_inside_the_allowed_range():
    tiny = K.suggest_estimate([done(1, 1), done(2, 2)], "Homework")
    assert tiny.minutes == 5 and tiny.low == 5
    huge = K.suggest_estimate([done(1, 9000), done(2, 9500)], "Homework")
    assert huge.minutes == 6000 and huge.high == 6000


# ---------- the timer and the logs, in the database ----------
pytestmark_db = pytest.mark.usefixtures("fresh_data")


@pytest.fixture
def setup(fresh_data):
    store.set_timezone(NY)
    store.set_term_dates(date(2026, 9, 1), date(2026, 12, 8), date(2026, 12, 18))
    store.set_awake(AwakeTimes.uniform(time(9), time(17)))
    store.set_min_block(30)


def count(table):
    return database.get_conn().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_the_timer_logs_the_minutes_to_the_task(setup):
    tid = ts.add_task("HW", estimate=120)
    tr.start_timer(tid, now=BASE)
    assert tr.running_timer().task_id == tid and tr.running_timer().started == BASE
    r = tr.stop_timer(BASE + timedelta(minutes=47, seconds=20))
    assert (r.minutes, r.capped, r.discarded) == (47, False, False) and r.log.task_id == tid and r.log.source == "timer" and r.log.start == BASE
    assert tr.running_timer() is None and ts.get_task(tid).logged_minutes == 47 and count("time_logs") == 1


def test_the_timer_survives_a_restart_and_only_one_runs_at_a_time(setup):
    a, b = ts.add_task("A", estimate=60), ts.add_task("B", estimate=60)
    tr.start_timer(a, now=BASE)
    import importlib
    importlib.reload(tr)                                                                            # nothing is kept in memory
    assert tr.running_timer().task_id == a
    with pytest.raises(PlannerError, match="already running"):
        tr.start_timer(b)
    assert tr.running_timer().task_id == a


def test_start_is_refused_for_a_done_task_a_missing_task_or_another_tasks_session(setup):
    a, b = ts.add_task("A", due=BASE + timedelta(days=3), estimate=60), ts.add_task("B", due=BASE + timedelta(days=3), estimate=60)
    ts.set_done(b)
    with pytest.raises(PlannerError, match="done"):
        tr.start_timer(b)
    with pytest.raises(PlannerError, match="does not exist"):
        tr.start_timer(999)
    sid = ss.add_session(a, timeutil.to_utc(date(2026, 9, 8), time(10), NY), timeutil.to_utc(date(2026, 9, 8), time(11), NY))
    other = ts.add_task("C", due=BASE + timedelta(days=3), estimate=60)
    with pytest.raises(PlannerError, match="another task"):
        tr.start_timer(other, sid)
    assert tr.running_timer() is None


def test_a_very_short_timer_is_discarded_and_a_forgotten_one_is_cut(setup):
    tid = ts.add_task("HW", estimate=60)
    tr.start_timer(tid, now=BASE)
    r = tr.stop_timer(BASE + timedelta(seconds=20))
    assert r.discarded and r.log is None and ts.get_task(tid).logged_minutes == 0 and count("time_logs") == 0 and tr.running_timer() is None
    tr.start_timer(tid, now=BASE)
    r = tr.stop_timer(BASE + timedelta(hours=30))
    assert r.capped and r.minutes == 720 and ts.get_task(tid).logged_minutes == 720
    with pytest.raises(PlannerError, match="No timer"):
        tr.stop_timer()


def test_cancel_throws_the_timer_away(setup):
    tid = ts.add_task("HW", estimate=60)
    tr.start_timer(tid, now=BASE)
    tr.cancel_timer()
    tr.cancel_timer()                                                                               # nothing to cancel is fine
    assert tr.running_timer() is None and ts.get_task(tid).logged_minutes == 0


def test_manual_logs_add_up_and_are_validated(setup):
    tid = ts.add_task("HW", estimate=120)
    a = tr.log_time(tid, 30, now=BASE)
    b = tr.log_time(tid, 45, now=BASE)
    assert ts.get_task(tid).logged_minutes == 75 and [x.minutes for x in tr.list_logs(tid)] == [30, 45] and all(x.source == "manual" for x in tr.list_logs(tid))
    for bad in (0, -5, 721, 2.5, True, "30"):
        with pytest.raises(PlannerError):
            tr.log_time(tid, bad)
    with pytest.raises(PlannerError, match="does not exist"):
        tr.log_time(999, 10)
    assert ts.get_task(tid).logged_minutes == 75
    tr.delete_log(a)
    assert ts.get_task(tid).logged_minutes == 45 and [x.id for x in tr.list_logs(tid)] == [b]
    with pytest.raises(PlannerError, match="does not exist"):
        tr.delete_log(a)


def test_logs_follow_their_task_and_session(setup):
    tid = ts.add_task("HW", due=BASE + timedelta(days=3), estimate=120)
    sid = ss.add_session(tid, timeutil.to_utc(date(2026, 9, 8), time(10), NY), timeutil.to_utc(date(2026, 9, 8), time(11), NY))
    tr.log_time(tid, 40, session_id=sid, now=BASE)
    assert [x.session_id for x in tr.list_logs(session_id=sid)] == [sid]
    ss.delete_session(sid)                                                                          # the session goes, the time stays on the task
    assert [x.session_id for x in tr.list_logs(tid)] == [None] and ts.get_task(tid).logged_minutes == 40
    ts.delete_task(tid)
    assert count("time_logs") == 0


def test_deleting_the_task_of_a_running_timer_stops_it(setup):
    tid = ts.add_task("HW", estimate=60)
    tr.start_timer(tid, now=BASE)
    ts.delete_task(tid)
    assert tr.running_timer() is None


def test_usage_from_the_database(setup):
    tid = ts.add_task("HW", due=BASE + timedelta(days=3), estimate=120)
    s1 = ss.add_session(tid, timeutil.to_utc(date(2026, 9, 8), time(10), NY), timeutil.to_utc(date(2026, 9, 8), time(11), NY))
    tr.log_time(tid, 25, session_id=s1, now=BASE)
    tr.start_timer(tid, s1, now=BASE)
    u = tr.usage(tid, BASE)
    assert (u.estimate_minutes, u.used_minutes, u.left_minutes, u.planned_minutes) == (120, 25, 95, 60)
    assert [(x.session_id, x.planned_minutes, x.used_minutes, x.status) for x in u.sessions] == [(s1, 60, 25, "running")]


def test_a_suggestion_from_finished_tasks_in_the_database(setup):
    for minutes in (60, 90, 120):
        tid = ts.add_task(f"HW {minutes}", None, "Homework", estimate=200)
        tr.log_time(tid, minutes)
        ts.set_done(tid)
    s = tr.suggestion("Homework")
    assert (s.minutes, s.samples, s.scope) == (90, 3, "category") and tr.suggestion("Quiz") is None


# ---------- logging changes the cushion ----------
def test_logged_time_raises_the_cushion_and_the_timer_returns_the_new_report(setup):
    now = timeutil.to_utc(date(2026, 9, 7), time(9), NY)
    tid = ts.add_task("HW", due=timeutil.to_utc(date(2026, 9, 8), time(17), NY), estimate=300)
    before = service.cushion_report(now).of(tid).cushion_minutes
    log_id, rep = service.log_time(tid, 60, now=now)
    assert rep.of(tid).cushion_minutes == before + 60
    service.start_timer(tid, now=now)
    result, rep = service.stop_timer(now + timedelta(minutes=30))
    assert result.minutes == 30 and rep.of(tid).cushion_minutes == (960 - 30) - (300 - 90)                  # half an hour of the day has gone, 90 minutes of work are done
    rep = service.delete_log(log_id, now)
    assert rep.of(tid).cushion_minutes == before + 30
    ts.log_time(tid, 400)                                                                           # more than was estimated: nothing is left to do
    assert service.cushion_report(now).of(tid).demand_minutes == 0
