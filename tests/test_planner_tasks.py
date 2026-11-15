"""Phase 3: tasks, estimates and the lists (pure: no database)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from planner import tasks as T
from planner.models import PlannerError

NY = "America/New_York"
NOW = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)          # 10:00 on Monday Nov 16 in New York


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def task(id=1, title="HW 6", **kw):
    return T.Task(id, title, **kw)


# ---------- validation ----------
def test_a_valid_task_has_sensible_defaults():
    t = task()
    assert (t.category, t.estimate_minutes, t.state, t.logged_minutes, t.due, t.start_ahead_days, t.source) == ("Homework", 60, "todo", 0, None, None, None)


def test_validation_of_every_field():
    for bad in (dict(title=" "), dict(category="Party"), dict(state="paused"), dict(logged_minutes=-1), dict(logged_minutes=2.5), dict(due=datetime(2026, 1, 1)),
                dict(start_ahead_days=3), dict(due=NOW, start_ahead_days=-1), dict(due=NOW, start_ahead_days=121), dict(due=NOW, start_ahead_days=True)):
        with pytest.raises(PlannerError):
            task(**bad)
    for bad in (0, 4, 6001, 30.5, True, "60", None):
        with pytest.raises(PlannerError, match="estimate"):
            task(estimate_minutes=bad)
    task(estimate_minutes=5)
    task(estimate_minutes=6000)
    task(due=NOW, start_ahead_days=0)
    task(due=NOW, start_ahead_days=120)


def test_every_category_is_accepted():
    for c in T.CATEGORIES:
        assert task(category=c).category == c


# ---------- default estimates ----------
def test_default_estimate_chain():
    assert T.default_estimate({}, "Homework") == T.DEFAULT_ESTIMATES["Homework"] == 120
    assert T.default_estimate(None, "Exam") == 600
    assert T.default_estimate({"Homework": 180}, "Homework") == 180                     # the course's own
    assert T.default_estimate({"Homework": 180}, "Quiz") == T.DEFAULT_ESTIMATES["Quiz"]   # another category falls back
    with pytest.raises(PlannerError):
        T.default_estimate({}, "Party")


def test_every_builtin_default_is_a_valid_estimate():
    for c in T.CATEGORIES:
        T.check_estimate(T.DEFAULT_ESTIMATES[c])


# ---------- remaining time, overdue, start date ----------
def test_remaining_minutes():
    assert task(estimate_minutes=120, logged_minutes=45).remaining_minutes == 75
    assert task(estimate_minutes=60, logged_minutes=90).remaining_minutes == 0              # more time than estimated
    assert task(estimate_minutes=60, logged_minutes=10, state="done").remaining_minutes == 0


def test_overdue_edges():
    due = utc(2026, 11, 16, 15, 0)
    assert not task(due=due).is_overdue(due)                                                # due exactly now: not late yet
    assert task(due=due).is_overdue(due + timedelta(seconds=1))
    assert not task(due=due, state="done").is_overdue(due + timedelta(days=5))
    assert not task().is_overdue(NOW)                                                       # no due date


def test_start_date_is_in_the_local_zone():
    t = task(due=utc(2026, 9, 2, 3, 0), start_ahead_days=3)                                 # 23:00 on Sep 1 in New York
    assert t.due_day(NY) == date(2026, 9, 1) and t.start_date(NY) == date(2026, 8, 29)
    assert task(due=utc(2026, 9, 2, 3, 0)).start_date(NY) is None                           # no limit
    assert task().start_date(NY) is None and task().due_day(NY) is None
    assert task(due=utc(2026, 9, 2, 3, 0), start_ahead_days=0).start_date(NY) == date(2026, 9, 1)


# ---------- the lists ----------
def test_todo_is_by_due_date_with_undated_last_and_done_left_out():
    a = task(1, "B", due=utc(2026, 11, 20, 5))
    b = task(2, "A", due=utc(2026, 11, 18, 5))
    c = task(3, "Z")
    d = task(4, "A2", due=utc(2026, 11, 18, 5))
    e = task(5, "Done", due=utc(2026, 11, 17, 5), state="done")
    assert [t.id for t in T.todo([a, b, c, d, e])] == [2, 4, 1, 3]                          # ties by title


def test_overdue_lists_the_oldest_first_and_skips_done_and_undated():
    old, recent = task(1, due=utc(2026, 11, 1)), task(2, due=utc(2026, 11, 14))
    assert [t.id for t in T.overdue([recent, old, task(3), task(4, due=utc(2026, 11, 1), state="done"), task(5, due=utc(2026, 12, 1))], NOW)] == [1, 2]


def test_start_soon_window_and_exclusions():
    mk = lambda id, days_ahead_of_start, **kw: task(id, due=utc(2026, 11, 16, 15) + timedelta(days=days_ahead_of_start + 5), start_ahead_days=5, **kw)
    today = mk(1, 0)                          # starts today
    in_three = mk(2, 3)                       # starts in 3 days: inside the window
    in_four = mk(3, 4)                        # starts in 4 days: not yet
    started_no_work = mk(4, -2)               # should have started two days ago, nothing logged
    started_work = mk(5, -2, logged_minutes=30)
    done = mk(6, 0, state="done")
    no_limit = task(7, due=utc(2026, 11, 30))
    late = task(8, due=utc(2026, 11, 10), start_ahead_days=2)          # overdue tasks are in the overdue list, not here
    assert [t.id for t in T.start_soon([today, in_three, in_four, started_no_work, started_work, done, no_limit, late], NOW, NY)] == [4, 1, 2]


def test_no_due_date_by_title_and_completed_most_recent_first():
    assert [t.id for t in T.no_due_date([task(1, "b"), task(2, "A"), task(3, "c", due=NOW), task(4, "d", state="done")])] == [2, 1]
    c1 = task(1, state="done", completed=utc(2026, 11, 10))
    c2 = task(2, state="done", completed=utc(2026, 11, 14))
    c3 = task(3, state="done")
    assert [t.id for t in T.completed([c1, c3, c2, task(4)])] == [2, 1, 3]


def test_lists_bundle():
    ts = [task(1, due=utc(2026, 11, 1)), task(2, due=utc(2026, 12, 1)), task(3), task(4, state="done", completed=NOW)]
    L = T.lists(ts, NOW, NY)
    assert [t.id for t in L.todo] == [1, 2, 3] and [t.id for t in L.overdue] == [1] and [t.id for t in L.no_due_date] == [3] and [t.id for t in L.completed] == [4]
    assert L.start_soon == ()
