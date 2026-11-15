"""Tracking of the study planner: time logged against tasks, planned against used, and estimates suggested from finished work. Pure: no database, no UI.

- TimeLog: minutes worked on a task (from the study timer or typed in), optionally during a session.
- planned_vs_used(): for a task, what the estimate says, what is planned in sessions and what was actually used; for each session whether it was done,
  partly done, missed, is running or is still to come.
- suggest_estimate(): the time a new task of a category will probably take, from the logged time of finished tasks of that category (the same course first)."""
from dataclasses import dataclass
from datetime import datetime
from statistics import median

from . import tasks as T

MIN_SAMPLES = 2                  # finished tasks needed before an estimate is suggested
MAX_TIMER_HOURS = 12             # a timer left running longer than this is cut here when it is stopped


@dataclass(frozen=True)
class TimeLog:
    id: int
    task_id: int
    start: datetime
    minutes: int
    session_id: int = None
    source: str = "timer"                 # "timer" or "manual"


@dataclass(frozen=True)
class SessionUsage:
    session_id: int
    planned_minutes: int
    used_minutes: int
    status: str                           # "upcoming", "now" (inside its time, not done), "running" (the timer is on it), "done", "partial", "missed"

    @property
    def progress(self):
        """How much of the session was used, 0 to 1."""
        return min(1.0, self.used_minutes / self.planned_minutes) if self.planned_minutes else 0.0


@dataclass(frozen=True)
class TaskUsage:
    task_id: int
    estimate_minutes: int
    planned_minutes: int                  # minutes in the task's sessions (all of them)
    used_minutes: int                     # minutes logged
    left_minutes: int                     # estimate - used, never below zero
    unplanned_minutes: int                # left, and not yet in a session that has not started
    over_estimate: bool                   # more time logged than estimated
    sessions: tuple


def timer_minutes(start, stop):
    """Whole minutes between two moments, rounded to the nearest minute, and cut at MAX_TIMER_HOURS. (Under half a minute is 0: nothing to log.)"""
    seconds = max(0.0, (stop - start).total_seconds())
    return min(int((seconds + 30) // 60), MAX_TIMER_HOURS * 60)


def planned_vs_used(task, sessions, logs, now, running_session_id=None):
    """TaskUsage of one task. `sessions`: its sessions (anything with id, task_id, start, end); `logs`: its TimeLogs; `running_session_id`: the session the timer is on."""
    mine = sorted((s for s in sessions if s.task_id == task.id), key=lambda s: (s.start, s.id))
    used_by_session = {}
    for log in logs:
        if log.task_id == task.id and log.session_id is not None:
            used_by_session[log.session_id] = used_by_session.get(log.session_id, 0) + log.minutes
    out, ahead = [], 0
    for s in mine:
        planned = int((s.end - s.start).total_seconds() // 60)
        used = used_by_session.get(s.id, 0)
        if used >= planned:
            status = "done"
        elif s.id == running_session_id:
            status = "running"
        elif s.start > now:
            status = "upcoming"
        elif s.end > now:
            status = "now"                                  # inside its time, not finished
        else:
            status = "partial" if used else "missed"
        if s.end > now:
            ahead += max(0, planned - used)                 # time in sessions that are still to come (or going on)
        out.append(SessionUsage(s.id, planned, used, status))
    used_total = task.logged_minutes
    left = max(0, task.estimate_minutes - used_total)
    planned_total = sum(u.planned_minutes for u in out)
    return TaskUsage(task.id, task.estimate_minutes, planned_total, used_total, left, max(0, left - ahead), used_total > task.estimate_minutes, tuple(out))


@dataclass(frozen=True)
class Suggestion:
    minutes: int
    samples: int
    scope: str                            # "course" (finished tasks of the same course and category) or "category" (all courses)
    low: int
    high: int


def _round5(x):
    return int(5 * round(x / 5))


def suggest_estimate(tasks, category, course_id=None):
    """The estimate suggested for a new task of `category`: the median of the logged minutes of finished tasks of that category, from the same course when it has at
    least MIN_SAMPLES of them, else from every course. Rounded to 5 minutes and kept inside the allowed range. None when there is too little to go on."""
    T.check_category(category)
    done = [t for t in tasks if t.is_done and t.category == category and t.logged_minutes > 0]
    same = [t for t in done if course_id is not None and t.course_id == course_id]
    scope, pool = ("course", same) if len(same) >= MIN_SAMPLES else ("category", done)
    if len(pool) < MIN_SAMPLES:
        return None
    minutes = sorted(t.logged_minutes for t in pool)
    lo, hi = T.ESTIMATE_RANGE
    clamp = lambda x: max(lo, min(hi, _round5(x)))
    return Suggestion(clamp(median(minutes)), len(pool), scope, clamp(minutes[0]), clamp(minutes[-1]))
