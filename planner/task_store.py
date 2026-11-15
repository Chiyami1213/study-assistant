"""Keeps the planner's tasks and the per-course default estimates in the database (tables tasks and task_defaults).

A task saved without an estimate inherits the default of its course and category (else the built-in one) at that moment; changing the default later does not
change tasks that already exist. Everything is validated as a planner.tasks.Task before it is saved, so a bad entry is refused with a PlannerError."""
from datetime import datetime, timezone

import database

from . import store, tasks as T, timeutil
from .models import PlannerError

_UNCHANGED = object()


def _now():
    return datetime.now(timezone.utc)


def _conn():
    return database.get_conn()


def _task(row):
    return T.Task(row["id"], row["title"], row["course_id"], row["category"], timeutil.parse_utc(row["due_utc"]) if row["due_utc"] else None,
                  row["estimate_minutes"], row["start_ahead_days"], row["state"], row["logged_minutes"], row["source"],
                  timeutil.parse_utc(row["completed_utc"]) if row["completed_utc"] else None, bool(row["personal"]))


def _course_exists(conn, course_id):
    if course_id is not None and not conn.execute("SELECT 1 FROM courses WHERE id=?", (course_id,)).fetchone():
        raise PlannerError("That course does not exist.")


# ---------- default estimates per course and category ----------
def get_defaults(course_id):
    """{category: minutes} the course has set (the built-in defaults are not included)."""
    with _conn() as conn:
        return {r["category"]: r["estimate_minutes"] for r in conn.execute("SELECT category, estimate_minutes FROM task_defaults WHERE course_id=?", (course_id,))}


def set_default(course_id, category, minutes):
    T.check_category(category)
    T.check_estimate(minutes)
    with _conn() as conn:
        _course_exists(conn, course_id)
        conn.execute("INSERT INTO task_defaults(course_id, category, estimate_minutes) VALUES (?,?,?) "
                     "ON CONFLICT(course_id, category) DO UPDATE SET estimate_minutes=excluded.estimate_minutes", (course_id, category, minutes))
        conn.commit()


def clear_default(course_id, category):
    with _conn() as conn:
        conn.execute("DELETE FROM task_defaults WHERE course_id=? AND category=?", (course_id, category))
        conn.commit()


def estimate_for(course_id, category):
    """The estimate a new task of this course and category would get."""
    return T.default_estimate(get_defaults(course_id) if course_id is not None else {}, category)


# ---------- tasks ----------
def add_task(title, course_id=None, category="Homework", due=None, estimate=None, start_ahead_days=None, source=None, now=None, personal=False):
    """Save a task (due: a UTC datetime or None). estimate=None inherits the default; a number overrides it. Returns the id."""
    now = now or _now()
    est = estimate if estimate is not None else estimate_for(course_id, category)
    T.Task(0, title, course_id, category, due, est, start_ahead_days, source=source, personal=personal)               # validated
    with _conn() as conn:
        _course_exists(conn, course_id)
        cur = conn.execute("INSERT INTO tasks(title, course_id, category, due_utc, estimate_minutes, start_ahead_days, state, logged_minutes, source, created_utc, personal) "
                           "VALUES (?,?,?,?,?,?, 'todo', 0, ?, ?, ?)",
                           (title.strip(), course_id, category, timeutil.utc_iso(due) if due else None, est, start_ahead_days, source, timeutil.utc_iso(now), int(bool(personal))))
        conn.commit()
        return cur.lastrowid


def get_task(task_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise PlannerError("That task does not exist.")
    return _task(row)


def update_task(task_id, title=_UNCHANGED, course_id=_UNCHANGED, category=_UNCHANGED, due=_UNCHANGED, estimate=_UNCHANGED, start_ahead_days=_UNCHANGED, personal=_UNCHANGED):
    """Change the fields that are given (pass due=None to remove the due date). Everything is checked before anything is saved."""
    cur = get_task(task_id)
    new = T.Task(task_id, cur.title if title is _UNCHANGED else title, cur.course_id if course_id is _UNCHANGED else course_id,
                 cur.category if category is _UNCHANGED else category, cur.due if due is _UNCHANGED else due,
                 cur.estimate_minutes if estimate is _UNCHANGED else estimate, cur.start_ahead_days if start_ahead_days is _UNCHANGED else start_ahead_days,
                 cur.state, cur.logged_minutes, cur.source, cur.completed, cur.personal if personal is _UNCHANGED else bool(personal))
    with _conn() as conn:
        _course_exists(conn, new.course_id)
        conn.execute("UPDATE tasks SET title=?, course_id=?, category=?, due_utc=?, estimate_minutes=?, start_ahead_days=?, personal=? WHERE id=?",
                     (new.title.strip(), new.course_id, new.category, timeutil.utc_iso(new.due) if new.due else None, new.estimate_minutes, new.start_ahead_days,
                      int(new.personal), task_id))
        conn.commit()


def set_done(task_id, done=True, now=None):
    """Mark a task done (remembering when) or open it again. The logged time stays."""
    get_task(task_id)
    with _conn() as conn:
        conn.execute("UPDATE tasks SET state=?, completed_utc=? WHERE id=?",
                     (T.DONE if done else T.TODO, timeutil.utc_iso(now or _now()) if done else None, task_id))
        conn.commit()


def log_time(task_id, minutes):
    """Add worked minutes to a task (a whole number above zero). Returns the new total."""
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes <= 0:
        raise PlannerError("The time to log is a whole number of minutes above zero.")
    total = get_task(task_id).logged_minutes + minutes
    with _conn() as conn:
        conn.execute("UPDATE tasks SET logged_minutes=? WHERE id=?", (total, task_id))
        conn.commit()
    return total


def set_logged(task_id, minutes):
    """Set the logged time exactly (to correct a mistake)."""
    T.Task(task_id, "x", logged_minutes=minutes)                              # the check
    get_task(task_id)
    with _conn() as conn:
        conn.execute("UPDATE tasks SET logged_minutes=? WHERE id=?", (minutes, task_id))
        conn.commit()


def delete_task(task_id):
    with _conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()


def list_tasks(course_id=None, include_done=True):
    sql, params = "SELECT * FROM tasks", []
    where = []
    if course_id is not None:
        where.append("course_id=?")
        params.append(course_id)
    if not include_done:
        where.append("state='todo'")
    with _conn() as conn:
        rows = conn.execute(sql + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id", params).fetchall()
    return [_task(r) for r in rows]


def task_lists(now=None):
    """to-do, overdue, start soon, no due date and completed, for now (a UTC datetime) in the term's time zone."""
    return T.lists(list_tasks(), now or _now(), store.get_term().zone)
