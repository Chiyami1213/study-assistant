"""Keeps the study timer and the time logs in the database (tables study_timer and time_logs).

Time logged on a task is also added to the task's own total (tasks.logged_minutes), which is what the cushion uses as work done; deleting a log takes it off again.
The timer survives closing the app: it is stored with its start time. Only one timer runs at a time."""
from dataclasses import dataclass
from datetime import datetime, timezone

import database

from . import session_store, task_store, tracking
from .models import PlannerError

MAX_LOG_MINUTES = tracking.MAX_TIMER_HOURS * 60


def _now():
    return datetime.now(timezone.utc)


def _conn():
    return database.get_conn()


def _iso(moment):
    from . import timeutil
    return timeutil.utc_iso(moment)


def _parse(text):
    from . import timeutil
    return timeutil.parse_utc(text)


@dataclass(frozen=True)
class Timer:
    task_id: int
    session_id: int
    started: datetime


@dataclass(frozen=True)
class StopResult:
    log: object                 # the TimeLog that was saved, or None
    minutes: int
    capped: bool                # the timer had run longer than MAX_TIMER_HOURS and was cut there
    discarded: bool             # under half a minute: nothing to log


def _log(row):
    return tracking.TimeLog(row["id"], row["task_id"], _parse(row["start_utc"]), row["minutes"], row["session_id"], row["source"])


# ---------- the timer ----------
def running_timer():
    with _conn() as conn:
        row = conn.execute("SELECT * FROM study_timer WHERE id=1").fetchone()
    return Timer(row["task_id"], row["session_id"], _parse(row["started_utc"])) if row else None


def start_timer(task_id, session_id=None, now=None):
    """Start the study timer on a task (optionally during one of its sessions)."""
    task = task_store.get_task(task_id)
    if task.is_done:
        raise PlannerError("That task is done. Open it again before you study it.")
    if session_id is not None and session_store.get_session(session_id).task_id != task_id:
        raise PlannerError("That session belongs to another task.")
    current = running_timer()
    if current:
        other = task_store.get_task(current.task_id)
        raise PlannerError(f"A timer is already running for {other.title}. Stop it first.")
    with _conn() as conn:
        conn.execute("INSERT INTO study_timer(id, task_id, session_id, started_utc) VALUES (1, ?, ?, ?)", (task_id, session_id, _iso(now or _now())))
        conn.commit()


def stop_timer(now=None):
    """Stop the timer and log the time (rounded to the minute; cut at 12 hours; under half a minute is not logged). Returns a StopResult."""
    now = now or _now()
    timer = running_timer()
    if not timer:
        raise PlannerError("No timer is running.")
    raw = max(0.0, (now - timer.started).total_seconds())
    minutes = tracking.timer_minutes(timer.started, now)
    capped = raw > MAX_LOG_MINUTES * 60
    with _conn() as conn:
        conn.execute("DELETE FROM study_timer WHERE id=1")
        conn.commit()
    if minutes == 0:
        return StopResult(None, 0, False, True)
    log_id = _insert(timer.task_id, minutes, timer.session_id, timer.started, "timer", now)
    return StopResult(next(x for x in list_logs(timer.task_id) if x.id == log_id), minutes, capped, False)


def cancel_timer():
    """Throw the running timer away without logging anything."""
    with _conn() as conn:
        conn.execute("DELETE FROM study_timer WHERE id=1")
        conn.commit()


# ---------- logs ----------
def _insert(task_id, minutes, session_id, start, source, now):
    with _conn() as conn:
        cur = conn.execute("INSERT INTO time_logs(task_id, session_id, start_utc, minutes, source, created_utc) VALUES (?,?,?,?,?,?)",
                           (task_id, session_id, _iso(start), minutes, source, _iso(now)))
        conn.execute("UPDATE tasks SET logged_minutes = logged_minutes + ? WHERE id=?", (minutes, task_id))
        conn.commit()
        return cur.lastrowid


def log_time(task_id, minutes, session_id=None, start=None, now=None):
    """Log minutes worked on a task by hand (a whole number from 1 to 12 hours), optionally during a session. Returns the log's id."""
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 1 <= minutes <= MAX_LOG_MINUTES:
        raise PlannerError(f"The time to log is a whole number of minutes from 1 to {MAX_LOG_MINUTES}.")
    task_store.get_task(task_id)
    if session_id is not None and session_store.get_session(session_id).task_id != task_id:
        raise PlannerError("That session belongs to another task.")
    now = now or _now()
    return _insert(task_id, minutes, session_id, start or now, "manual", now)


def delete_log(log_id):
    """Remove a log and the minutes it added to its task."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM time_logs WHERE id=?", (log_id,)).fetchone()
        if not row:
            raise PlannerError("That time log does not exist.")
        conn.execute("DELETE FROM time_logs WHERE id=?", (log_id,))
        conn.execute("UPDATE tasks SET logged_minutes = MAX(0, logged_minutes - ?) WHERE id=?", (row["minutes"], row["task_id"]))
        conn.commit()


def list_logs(task_id=None, session_id=None):
    sql, params, where = "SELECT * FROM time_logs", [], []
    if task_id is not None:
        where.append("task_id=?")
        params.append(task_id)
    if session_id is not None:
        where.append("session_id=?")
        params.append(session_id)
    with _conn() as conn:
        rows = conn.execute(sql + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY start_utc, id", params).fetchall()
    return [_log(r) for r in rows]


# ---------- planned against used, and suggestions ----------
def usage(task_id, now=None):
    """The TaskUsage of one task: its estimate, what is planned in sessions, what was logged, and how each session went."""
    task = task_store.get_task(task_id)
    timer = running_timer()
    return tracking.planned_vs_used(task, session_store.list_sessions(task_id=task_id), list_logs(task_id=task_id), now or _now(),
                                    timer.session_id if timer and timer.task_id == task_id else None)


def suggestion(category, course_id=None):
    """The estimate suggested for a new task of this category from your finished tasks (None until there are enough)."""
    return tracking.suggest_estimate(task_store.list_tasks(), category, course_id)
