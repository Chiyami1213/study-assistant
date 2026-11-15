"""Keeps the study sessions in the database (table study_sessions) and checks every change before it is saved.

A hard problem (outside the term, in a break, over another session) always refuses the change with a PlannerError; a soft one (outside the awake hours, over a class
or event, shorter than the minimum block) refuses it unless force=True, so a screen can ask the student whether to go ahead. check_session() lists the problems."""
from datetime import datetime, timedelta, timezone

import database

from . import commit_store, sessions as S, store, task_store, timeutil
from .models import PlannerError

_UNSET = object()


def _now():
    return datetime.now(timezone.utc)


def _conn():
    return database.get_conn()


def _session(row):
    return S.Session(row["id"], row["task_id"], timeutil.parse_utc(row["start_utc"]), timeutil.parse_utc(row["end_utc"]), row["source"])


def get_session(session_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM study_sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise PlannerError("That study session does not exist.")
    return _session(row)


def list_sessions(first=None, last=None, task_id=None):
    """The sessions that touch the local days first..last (all when omitted), optionally of one task, in time order."""
    sql, params, where = "SELECT * FROM study_sessions", [], []
    if task_id is not None:
        where.append("task_id=?")
        params.append(task_id)
    if first is not None and last is not None:
        tz = store.get_term().zone
        lo, _ = timeutil.day_bounds_utc(first, tz)
        _, hi = timeutil.day_bounds_utc(last, tz)
        where += ["end_utc > ?", "start_utc < ?"]
        params += [timeutil.utc_iso(lo), timeutil.utc_iso(hi)]
    with _conn() as conn:
        rows = conn.execute(sql + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY start_utc, id", params).fetchall()
    return [_session(r) for r in rows]


def check_session(start, end, ignore_id=None, personal=False):
    """The Problems of a session from start to end (UTC), judged against the saved setup, commitments and the other sessions. `personal`: the task is not for school."""
    config = store.load_config()
    tz = config.term.zone
    first, last = timeutil.local_day(start, tz), timeutil.local_day(max(end - timedelta(seconds=1), start), tz)
    blocks = commit_store.commitments(first, last)
    others = [s for s in list_sessions(first, last) if s.id != ignore_id]
    return S.placement_problems(config, start, end, blocks, others, personal)


def _refuse(problems, force):
    blocking = [p for p in problems if p.hard or not force]
    if blocking:
        raise PlannerError(" ".join(p.message for p in blocking))


def add_session(task_id, start, end, source=S.MANUAL, force=False, now=None):
    """Save a study session for a task (UTC start and end). Returns its id."""
    task_store.get_task(task_id)
    S.Session(0, task_id, start, end, source)                                  # validated
    _refuse(check_session(start, end, personal=task_store.get_task(task_id).personal), force)
    with _conn() as conn:
        cur = conn.execute("INSERT INTO study_sessions(task_id, start_utc, end_utc, source, created_utc) VALUES (?,?,?,?,?)",
                           (task_id, timeutil.utc_iso(start), timeutil.utc_iso(end), source, timeutil.utc_iso(now or _now())))
        conn.commit()
        return cur.lastrowid


def _rewrite(session_id, start, end, force):
    cur = get_session(session_id)
    S.Session(session_id, cur.task_id, start, end, S.MANUAL)                   # validated; a session the student changed is theirs now
    _refuse(check_session(start, end, ignore_id=session_id, personal=task_store.get_task(cur.task_id).personal), force)
    with _conn() as conn:
        conn.execute("UPDATE study_sessions SET start_utc=?, end_utc=?, source='manual' WHERE id=?", (timeutil.utc_iso(start), timeutil.utc_iso(end), session_id))
        conn.commit()


def update_session(session_id, start, end, force=False):
    """Change the start and the end of a session together. It becomes a manual session."""
    get_session(session_id)
    _rewrite(session_id, start, end, force)


def move_session(session_id, new_start, force=False):
    """Move a session to start at new_start; its length stays. It becomes a manual session (the auto-planner will not move it)."""
    cur = get_session(session_id)
    _rewrite(session_id, new_start, new_start + (cur.end - cur.start), force)


def resize_session(session_id, minutes=None, new_end=None, force=False):
    """Change the length of a session (give the new length in minutes, or the new end). The start stays. It becomes a manual session."""
    cur = get_session(session_id)
    if (minutes is None) == (new_end is None):
        raise PlannerError("Give either the new length or the new end.")
    if minutes is not None and (not isinstance(minutes, int) or isinstance(minutes, bool) or minutes <= 0):
        raise PlannerError("The length is a whole number of minutes above zero.")
    _rewrite(session_id, cur.start, new_end if new_end is not None else cur.start + timedelta(minutes=minutes), force)


def delete_session(session_id):
    with _conn() as conn:
        conn.execute("DELETE FROM study_sessions WHERE id=?", (session_id,))
        conn.commit()


def unplan_task(task_id, now=None, include_past=False):
    """Remove the sessions of a task that have not started (all of them with include_past). Returns how many were removed."""
    now = now or _now()
    with _conn() as conn:
        if include_past:
            cur = conn.execute("DELETE FROM study_sessions WHERE task_id=?", (task_id,))
        else:
            cur = conn.execute("DELETE FROM study_sessions WHERE task_id=? AND start_utc >= ?", (task_id, timeutil.utc_iso(now)))
        conn.commit()
        return cur.rowcount


def apply_plan(result, now=None):
    """Store an auto-plan in one step: the replaced automatic sessions go, the new ones come."""
    now = now or _now()
    with _conn() as conn:
        for sid in result.remove:
            conn.execute("DELETE FROM study_sessions WHERE id=?", (sid,))
        conn.executemany("INSERT INTO study_sessions(task_id, start_utc, end_utc, source, created_utc) VALUES (?,?,?, 'auto', ?)",
                         [(c.task_id, timeutil.utc_iso(c.start), timeutil.utc_iso(c.end), timeutil.utc_iso(now)) for c in result.add])
        conn.commit()
