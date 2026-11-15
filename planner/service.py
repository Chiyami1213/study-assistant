"""The planner as the app uses it: reads the saved setup, commitments, tasks and sessions, and returns the cushion report. The logic itself is in
planner.freetime and planner.sessions (pure). Every change to the sessions returns the new cushion report, so a screen always shows the right numbers."""
from datetime import datetime, timezone

from . import commit_store, freetime, session_store, sessions as S, store, task_store, timeutil, track_store


def _now(now):
    return now or datetime.now(timezone.utc)


def cushion_report(now=None, planned=None):
    """The CushionReport for `now` (a UTC datetime; the clock when omitted): free time from today to the last deadline of the unfinished tasks (study
    sessions already planned are taken out of it and count as work for their task), the cushion of each task, and the timeline."""
    now = _now(now)
    config = store.load_config()
    tasks = task_store.list_tasks(include_done=False)
    dated = [t for t in tasks if t.due is not None]
    if not dated:
        return freetime.CushionReport((), (), False)
    tz = config.term.zone
    first = timeutil.local_day(now, tz)
    last = max(first, min(max(timeutil.local_day(t.due, tz) for t in dated), config.term.exams_end))
    blocks = commit_store.commitments(first, last)
    return freetime.report(config, tasks, blocks, session_store.list_sessions() if planned is None else planned, now)


def free_time(first, last, now=None, planned=None):
    """The free study intervals (UTC pairs) of the local days first..last from the saved setup (planned sessions are taken out)."""
    config = store.load_config()
    return freetime.free_intervals(config, commit_store.commitments(first, last), session_store.list_sessions() if planned is None else planned, first, last, now)


def auto_plan(now=None, include_undated=False):
    """Plan study sessions for the unfinished tasks (see planner.sessions.autoplan) and save the plan. Returns (PlanResult, CushionReport)."""
    now = _now(now)
    config = store.load_config()
    tasks = task_store.list_tasks(include_done=False)
    tz = config.term.zone
    first = timeutil.local_day(now, tz)
    open_tasks = [t for t in tasks if t.due is not None or include_undated]
    wide = include_undated or any(t.due is None or t.is_overdue(now) for t in open_tasks)
    last = config.term.exams_end if wide or not open_tasks else min(max(timeutil.local_day(t.due, tz) for t in open_tasks), config.term.exams_end)
    blocks = commit_store.commitments(first, max(first, last))
    result = S.autoplan(config, tasks, blocks, session_store.list_sessions(), now, include_undated)
    session_store.apply_plan(result, now)
    return result, cushion_report(now)


def add_session(task_id, start, end, force=False, now=None):
    """A manual session. Returns (session id, new CushionReport)."""
    sid = session_store.add_session(task_id, start, end, S.MANUAL, force, now)
    return sid, cushion_report(now)


def move_session(session_id, new_start, force=False, now=None):
    session_store.move_session(session_id, new_start, force)
    return cushion_report(now)


def resize_session(session_id, minutes=None, new_end=None, force=False, now=None):
    session_store.resize_session(session_id, minutes, new_end, force)
    return cushion_report(now)


def delete_session(session_id, now=None):
    session_store.delete_session(session_id)
    return cushion_report(now)


def unplan_task(task_id, now=None, include_past=False):
    """Remove a task's sessions that have not started. Returns (how many, new CushionReport)."""
    removed = session_store.unplan_task(task_id, _now(now), include_past)
    return removed, cushion_report(now)


# ---------- tracking: the study timer and the time logs (each returns the new cushion, because logged time is work done) ----------
def start_timer(task_id, session_id=None, now=None):
    track_store.start_timer(task_id, session_id, now)


def stop_timer(now=None):
    """Stop the timer and log the time. Returns (StopResult, CushionReport)."""
    result = track_store.stop_timer(now)
    return result, cushion_report(now)


def cancel_timer():
    track_store.cancel_timer()


def log_time(task_id, minutes, session_id=None, now=None):
    """Log time by hand. Returns (log id, CushionReport)."""
    log_id = track_store.log_time(task_id, minutes, session_id, None, now)
    return log_id, cushion_report(now)


def delete_log(log_id, now=None):
    track_store.delete_log(log_id)
    return cushion_report(now)
