"""Phase 3: tasks and default estimates are saved, validated and read back (a temporary database)."""
from datetime import datetime, timezone

import pytest

import crud
import database
from planner import store, task_store as ts, tasks as T
from planner.models import PlannerError

pytestmark = pytest.mark.usefixtures("fresh_data")
NOW = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def course(code="AE 6765"):
    return crud.add_course(code, "Kinetics", "Fall 2026", 0, "Active")


def count(table):
    return database.get_conn().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ---------- default estimates ----------
def test_a_new_task_inherits_the_course_default_then_the_builtin_one():
    c = course()
    other = course("PHYS 6105")
    ts.set_default(c, "Homework", 180)
    a = ts.add_task("HW 6", c, "Homework")
    b = ts.add_task("HW 6", other, "Homework")
    d = ts.add_task("Reading", c, "Reading")
    e = ts.add_task("No course", None, "Exam")
    assert [ts.get_task(i).estimate_minutes for i in (a, b, d, e)] == [180, 120, 60, 600]


def test_an_explicit_estimate_overrides_and_later_default_changes_do_not_touch_existing_tasks():
    c = course()
    ts.set_default(c, "Homework", 180)
    kept = ts.add_task("HW 1", c, "Homework")
    mine = ts.add_task("HW 2", c, "Homework", estimate=45)
    ts.set_default(c, "Homework", 240)
    assert ts.get_task(kept).estimate_minutes == 180 and ts.get_task(mine).estimate_minutes == 45
    assert ts.get_task(ts.add_task("HW 3", c, "Homework")).estimate_minutes == 240


def test_default_estimate_crud_and_validation():
    c = course()
    ts.set_default(c, "Quiz", 30)
    ts.set_default(c, "Quiz", 50)                                            # replaces
    ts.set_default(c, "Project", 900)
    assert ts.get_defaults(c) == {"Quiz": 50, "Project": 900}
    ts.clear_default(c, "Quiz")
    assert ts.get_defaults(c) == {"Project": 900} and ts.estimate_for(c, "Quiz") == 45
    for args in ((c, "Party", 30), (c, "Quiz", 3), (c, "Quiz", 7000), (999, "Quiz", 30)):
        with pytest.raises(PlannerError):
            ts.set_default(*args)
    assert ts.get_defaults(c) == {"Project": 900}


# ---------- tasks ----------
def test_task_round_trip_in_utc():
    c = course()
    tid = ts.add_task("  HW 6  ", c, "Homework", due=utc(2026, 11, 20, 4, 59), estimate=150, start_ahead_days=4, source="manual", now=NOW)
    t = ts.get_task(tid)
    assert (t.title, t.course_id, t.category, t.due, t.estimate_minutes, t.start_ahead_days, t.state, t.logged_minutes, t.source, t.completed) == (
        "HW 6", c, "Homework", utc(2026, 11, 20, 4, 59), 150, 4, "todo", 0, "manual", None)
    row = dict(database.get_conn().execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())
    assert row["due_utc"] == "2026-11-20T04:59:00Z" and row["created_utc"] == "2026-11-16T15:00:00Z"


def test_invalid_tasks_are_refused_and_nothing_is_saved():
    for kw in (dict(title="  "), dict(category="Party"), dict(estimate=2), dict(due=datetime(2026, 1, 1)), dict(start_ahead_days=3), dict(course_id=999)):
        with pytest.raises(PlannerError):
            ts.add_task(**{"title": "x", **kw})
    assert count("tasks") == 0


def test_update_changes_only_what_is_given_and_checks_everything_first():
    c = course()
    tid = ts.add_task("HW 6", c, "Homework", due=utc(2026, 11, 20, 5), estimate=120, start_ahead_days=3)
    ts.update_task(tid, title="HW 6 (revised)", estimate=90)
    t = ts.get_task(tid)
    assert (t.title, t.estimate_minutes, t.due, t.course_id, t.start_ahead_days) == ("HW 6 (revised)", 90, utc(2026, 11, 20, 5), c, 3)
    with pytest.raises(PlannerError):
        ts.update_task(tid, title="Fine", estimate=1)                         # one bad field: nothing is saved
    assert ts.get_task(tid).title == "HW 6 (revised)"
    with pytest.raises(PlannerError):
        ts.update_task(tid, due=None)                                         # start-ahead needs a due date
    ts.update_task(tid, due=None, start_ahead_days=None)
    assert ts.get_task(tid).due is None
    with pytest.raises(PlannerError, match="does not exist"):
        ts.update_task(999, title="x")
    ts.update_task(tid, course_id=None)
    assert ts.get_task(tid).course_id is None


def test_done_and_reopen_keep_the_logged_time():
    tid = ts.add_task("HW", estimate=60)
    ts.log_time(tid, 20)
    ts.set_done(tid, True, now=NOW)
    t = ts.get_task(tid)
    assert t.is_done and t.completed == NOW and t.logged_minutes == 20 and t.remaining_minutes == 0
    ts.set_done(tid, False)
    t = ts.get_task(tid)
    assert not t.is_done and t.completed is None and t.logged_minutes == 20 and t.remaining_minutes == 40


def test_logging_time_adds_up_and_is_validated():
    tid = ts.add_task("HW", estimate=100)
    assert ts.log_time(tid, 30) == 30 and ts.log_time(tid, 45) == 75
    for bad in (0, -5, 2.5, True):
        with pytest.raises(PlannerError):
            ts.log_time(tid, bad)
    assert ts.get_task(tid).logged_minutes == 75
    ts.set_logged(tid, 10)
    assert ts.get_task(tid).logged_minutes == 10
    with pytest.raises(PlannerError):
        ts.set_logged(tid, -1)
    with pytest.raises(PlannerError, match="does not exist"):
        ts.log_time(999, 5)


def test_delete_and_filters():
    a, b = course("A 1"), course("B 2")
    t1 = ts.add_task("one", a, due=utc(2026, 11, 20))
    t2 = ts.add_task("two", b)
    t3 = ts.add_task("three", a)
    ts.set_done(t3)
    assert [t.id for t in ts.list_tasks()] == [t1, t2, t3]
    assert [t.id for t in ts.list_tasks(course_id=a)] == [t1, t3]
    assert [t.id for t in ts.list_tasks(course_id=a, include_done=False)] == [t1]
    ts.delete_task(t2)
    assert [t.id for t in ts.list_tasks()] == [t1, t3]


def test_deleting_a_course_keeps_its_tasks_and_drops_its_defaults():
    c = course()
    ts.set_default(c, "Homework", 180)
    tid = ts.add_task("HW", c)
    crud.delete_course(c)
    assert ts.get_task(tid).course_id is None and count("task_defaults") == 0


# ---------- the lists from the database ----------
def test_task_lists_from_saved_tasks():
    store.set_timezone("America/New_York")
    late = ts.add_task("Late", due=utc(2026, 11, 10, 5))
    soon = ts.add_task("Soon", due=utc(2026, 11, 22, 5), start_ahead_days=5)             # starts Nov 16 (local), today
    later = ts.add_task("Later", due=utc(2026, 12, 20, 5), start_ahead_days=5)
    free = ts.add_task("Anytime")
    done = ts.add_task("Done", due=utc(2026, 11, 12))
    ts.set_done(done, now=NOW)
    L = ts.task_lists(NOW)
    assert [t.id for t in L.todo] == [late, soon, later, free]
    assert [t.id for t in L.overdue] == [late] and [t.id for t in L.start_soon] == [soon]
    assert [t.id for t in L.no_due_date] == [free] and [t.id for t in L.completed] == [done]
