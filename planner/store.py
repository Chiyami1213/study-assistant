"""Keeps the planner's setup: the time zone, the awake times and the minimum block in the database (tables planner_settings and planner_awake),
the term dates in settings.json (the same dates the Calendar and Home already use) and the breaks as the rows of the `holidays` table.

Everything that comes out is a validated model from planner.models; anything invalid is refused with a PlannerError before it is saved."""
import os
from datetime import date

import crud
import database
import settings

from . import timeutil
from .models import AwakeTimes, Break, DayWindow, PlannerConfig, PlannerError, Term, check_min_block, DEFAULT_MIN_BLOCK

DEFAULT_TZ = "America/New_York"


def default_timezone():
    """The zone used until the user chooses one: the TZ variable when it names a zone, else US Eastern."""
    for name in (os.environ.get("TZ"), DEFAULT_TZ):
        try:
            if name:
                timeutil.zone(name)
                return name
        except ValueError:
            continue
    return "UTC"


def _row():
    with database.get_conn() as conn:
        return conn.execute("SELECT * FROM planner_settings WHERE id=1").fetchone()


def _save_settings(tz, min_block):
    with database.get_conn() as conn:
        conn.execute("INSERT INTO planner_settings(id, tz, min_block_minutes) VALUES (1, ?, ?) "
                     "ON CONFLICT(id) DO UPDATE SET tz=excluded.tz, min_block_minutes=excluded.min_block_minutes", (tz, min_block))
        conn.commit()


# ---------- time zone and minimum block ----------
def get_timezone():
    row = _row()
    return row["tz"] if row else default_timezone()


def set_timezone(name):
    try:
        timeutil.zone(name)
    except ValueError as e:
        raise PlannerError(str(e)) from e
    _save_settings(name, get_min_block())


def get_min_block():
    row = _row()
    return int(row["min_block_minutes"]) if row else DEFAULT_MIN_BLOCK


def set_min_block(minutes):
    _save_settings(get_timezone(), check_min_block(minutes))


# ---------- awake times ----------
def get_awake():
    with database.get_conn() as conn:
        rows = {r["weekday"]: r for r in conn.execute("SELECT * FROM planner_awake")}
    windows = []
    for weekday in range(7):
        r = rows.get(weekday)
        windows.append(DayWindow(timeutil.parse_hhmm(r["wake"]), timeutil.parse_hhmm(r["bed"])) if r else DayWindow())
    return AwakeTimes(tuple(windows))


def set_awake(awake):
    if not isinstance(awake, AwakeTimes):
        raise PlannerError("Awake times have to be an AwakeTimes value.")
    with database.get_conn() as conn:
        conn.execute("DELETE FROM planner_awake")
        conn.executemany("INSERT INTO planner_awake(weekday, wake, bed) VALUES (?, ?, ?)",
                         [(i, timeutil.fmt_hhmm(w.wake), timeutil.fmt_hhmm(w.bed)) for i, w in enumerate(awake.windows)])
        conn.commit()


# ---------- breaks (the rows of `holidays`) ----------
def list_breaks():
    """[(id, Break)] in date order."""
    return [(h["id"], Break(h["name"], date.fromisoformat(h["start_date"]), date.fromisoformat(h["end_date"]))) for h in crud.list_holidays()]


def add_break(name, start, end):
    b = Break(name.strip(), start, end)                      # validated first
    return crud.add_holiday(b.name, b.start.isoformat(), b.end.isoformat())


def remove_break(break_id):
    crud.delete_holiday(break_id)


# ---------- the term ----------
def term_configured():
    """True once the term dates were saved (Calendar > Edit Schedule, or set_term_dates). Before that the dates are the app's defaults."""
    return settings.semester_set()


def get_term():
    sem = settings.get_semester()
    return Term(date.fromisoformat(sem["start"]), date.fromisoformat(sem["end"]), date.fromisoformat(sem["exam_end"]), get_timezone(),
                tuple(b for _, b in list_breaks()))


def set_term_dates(start, classes_end, exams_end):
    """Save the first day, the last day of classes and the last day of the exam period (validated as a Term first)."""
    Term(start, classes_end, exams_end, get_timezone())
    settings.set_semester(start.isoformat(), classes_end.isoformat(), exams_end.isoformat())


def load_config():
    """The whole setup as one validated PlannerConfig."""
    return PlannerConfig(get_term(), get_awake(), get_min_block())
