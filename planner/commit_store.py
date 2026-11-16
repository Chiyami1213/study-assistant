"""Keeps the planner's commitments in the database: activities and their weekly meetings, the exceptions of a recurring meeting, and one-off events.

Courses and their weekly meetings are the app's own (courses, class_meetings); this module reads them and adds the end date and the exceptions.
Everything that is saved is validated as a model from planner.commitments first, so a bad entry is refused with a PlannerError and nothing is half-saved.
Events are stored with UTC times (start_utc, end_utc) and, so the older parts of the app keep working, the local date and times in the old columns."""
from datetime import date, datetime, timedelta

from core import crud
from core import database

from . import store, timeutil
from .commitments import (ACTIVITY, COURSE, OVERRIDE, SKIP, Event, Meeting, MeetingException, Series, legacy_event)
from .models import PlannerError


def _conn():
    return database.get_conn()


def _owner_table(owner):
    if owner not in (COURSE, ACTIVITY):
        raise PlannerError("An owner is a course or an activity.")
    return "class_meetings" if owner == COURSE else "activity_meetings"


def _days_text(days):
    days = sorted(set(days))
    Meeting(0, frozenset(days), timeutil.parse_hhmm("00:00"), timeutil.parse_hhmm("00:01"))          # the weekday check
    return ",".join(str(d) for d in days)


def _check_meeting(days, start, end, end_date=None):
    Meeting(0, frozenset(days), start, end, "", end_date)                  # raises PlannerError when it does not make sense


# ---------- activities ----------
def add_activity(name, color=None, location="", busy=True, in_breaks=False, source=None):
    Series(ACTIVITY, 0, name)                                              # the name check
    with _conn() as conn:
        cur = conn.execute("INSERT INTO activities(name, color, location, busy, in_breaks, source) VALUES (?,?,?,?,?,?)",
                           (name.strip(), color or None, location or None, int(bool(busy)), int(bool(in_breaks)), source))
        conn.commit()
        return cur.lastrowid


def update_activity(activity_id, name, color=None, location="", busy=True, in_breaks=False):
    Series(ACTIVITY, activity_id, name)
    with _conn() as conn:
        conn.execute("UPDATE activities SET name=?, color=?, location=?, busy=?, in_breaks=? WHERE id=?",
                     (name.strip(), color or None, location or None, int(bool(busy)), int(bool(in_breaks)), activity_id))
        conn.commit()


def delete_activity(activity_id):
    """Delete an activity with its meetings and their exceptions."""
    with _conn() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM activity_meetings WHERE activity_id=?", (activity_id,))]
        for mid in ids:
            conn.execute("DELETE FROM meeting_exceptions WHERE owner='activity' AND meeting_id=?", (mid,))
        conn.execute("DELETE FROM activities WHERE id=?", (activity_id,))
        conn.commit()


def list_activities():
    with _conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM activities ORDER BY name, id")]


# ---------- weekly meetings (a course's and an activity's) ----------
def add_activity_meeting(activity_id, days, start, end, location="", end_date=None):
    _check_meeting(days, start, end, end_date)
    with _conn() as conn:
        if not conn.execute("SELECT 1 FROM activities WHERE id=?", (activity_id,)).fetchone():
            raise PlannerError("That activity does not exist.")
        cur = conn.execute("INSERT INTO activity_meetings(activity_id, days, start_time, end_time, location, end_date) VALUES (?,?,?,?,?,?)",
                           (activity_id, _days_text(days), timeutil.fmt_hhmm(start), timeutil.fmt_hhmm(end), location or None,
                            end_date.isoformat() if end_date else None))
        conn.commit()
        return cur.lastrowid


def add_course_meeting(course_id, days, start, end, location="", end_date=None):
    _check_meeting(days, start, end, end_date)
    return crud.add_meeting(course_id, sorted(set(days)), timeutil.fmt_hhmm(start), timeutil.fmt_hhmm(end), location, end_date.isoformat() if end_date else None)


def update_meeting(owner, meeting_id, days, start, end, location="", end_date=None):
    """Change the whole series (every occurrence). Exceptions on days that are no longer meeting days stay but have no effect."""
    table = _owner_table(owner)
    _check_meeting(days, start, end, end_date)
    with _conn() as conn:
        if not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (meeting_id,)).fetchone():
            raise PlannerError("That meeting does not exist.")
        conn.execute(f"UPDATE {table} SET days=?, start_time=?, end_time=?, location=?, end_date=? WHERE id=?",
                     (_days_text(days), timeutil.fmt_hhmm(start), timeutil.fmt_hhmm(end), location or None, end_date.isoformat() if end_date else None, meeting_id))
        conn.commit()


def delete_meeting(owner, meeting_id):
    table = _owner_table(owner)
    with _conn() as conn:
        conn.execute("DELETE FROM meeting_exceptions WHERE owner=? AND meeting_id=?", (owner, meeting_id))
        conn.execute(f"DELETE FROM {table} WHERE id=?", (meeting_id,))
        conn.commit()


SCOPES = ("this", "weekday", "following", "all")


def delete_occurrences(owner, meeting_id, day, scope):
    """Delete part of a repeating meeting, from the occurrence on `day`:
    "this": only that day (the rest of the series stays); "weekday": that day and every later one on the same weekday (the other days of the meeting go on);
    "following": that day and everything after it (the series ends the day before); "all": the whole series.
    A series with nothing left before `day` is deleted. Returns a short text of what was done."""
    from datetime import timedelta
    if scope not in SCOPES:
        raise PlannerError("Choose what to delete: this one, this and the following ones on this weekday, this and all following, or all.")
    row = dict(_meeting_row(owner, meeting_id))
    _check_day(owner, meeting_id, day)
    days = sorted(int(d) for d in row["days"].split(",") if d != "")
    start, end = timeutil.parse_hhmm(row["start_time"]), timeutil.parse_hhmm(row["end_time"])
    location = row.get("location") or ""
    last_kept = day - timedelta(days=1)
    term_start = store.get_term().start

    def earlier_exists(weekdays):
        """Does the meeting happen before `day` on one of these weekdays (inside the term)?"""
        for d in range(1, 8 * 7):
            before = day - timedelta(days=d)
            if before < term_start:
                return False
            if before.weekday() in weekdays and (not row.get("end_date") or before.isoformat() <= row["end_date"]):
                return True
        return False

    def drop_exceptions_from(weekdays):
        with _conn() as conn:
            for e in list_exceptions(owner):
                if e.meeting_id == meeting_id and e.day >= day and e.day.weekday() in weekdays:
                    conn.execute("DELETE FROM meeting_exceptions WHERE owner=? AND meeting_id=? AND day=?", (owner, meeting_id, e.day.isoformat()))
            conn.commit()

    if scope == "all":
        delete_meeting(owner, meeting_id)
        return "The whole series was deleted."
    if scope == "this":
        skip_occurrence(owner, meeting_id, day)
        return "That day was deleted."
    if scope == "following" or len(days) == 1:
        if not earlier_exists(set(days)):
            delete_meeting(owner, meeting_id)
            return "The series was deleted (nothing was before that day)."
        drop_exceptions_from(set(days))
        update_meeting(owner, meeting_id, days, start, end, location, last_kept)
        return "That day and the ones after it were deleted."
    weekday = day.weekday()                                                   # "weekday": the other days go on
    remaining = [d for d in days if d != weekday]
    owner_id = row["course_id"] if owner == "course" else row["activity_id"]
    if earlier_exists({weekday}):
        new_id = (add_course_meeting if owner == "course" else add_activity_meeting)(owner_id, {weekday}, start, end, location, last_kept)
        with _conn() as conn:                                                 # what was changed on the earlier days goes with them
            for e in list_exceptions(owner):
                if e.meeting_id == meeting_id and e.day < day and e.day.weekday() == weekday:
                    conn.execute("UPDATE meeting_exceptions SET meeting_id=? WHERE owner=? AND meeting_id=? AND day=?", (new_id, owner, meeting_id, e.day.isoformat()))
            conn.commit()
    drop_exceptions_from({weekday})
    end_date = date.fromisoformat(row["end_date"]) if row.get("end_date") else None
    update_meeting(owner, meeting_id, remaining, start, end, location, end_date)
    return "That day and the later ones on this weekday were deleted."


def change_occurrences(owner, meeting_id, day, scope, start, end, location=None):
    """Give a repeating meeting another time (and place when given), from the occurrence on `day`:
    "this": only that day; "weekday": that day and every later one on the same weekday; "following": that day and every later occurrence of the meeting; "all": the whole series
    (the weekly time itself changes). A day that was skipped stays skipped. Returns a short text of what was done."""
    from datetime import timedelta
    if scope not in SCOPES:
        raise PlannerError("Choose what to change: this one, this and the following ones on this weekday, this and all following, or all.")
    row = dict(_meeting_row(owner, meeting_id))
    _check_day(owner, meeting_id, day)
    days = sorted(int(d) for d in row["days"].split(",") if d != "")
    if scope == "this":
        override_occurrence(owner, meeting_id, day, start, end, location)
        return "Changed for that day only."
    if scope == "all":
        update_meeting(owner, meeting_id, days, start, end, location if location is not None else (row.get("location") or ""),
                       date.fromisoformat(row["end_date"]) if row.get("end_date") else None)
        return "Every event was changed."
    last = store.get_term().exams_end
    if row.get("end_date"):
        last = min(last, date.fromisoformat(row["end_date"]))
    weekdays = {day.weekday()} if scope == "weekday" else set(days)
    count, d = 0, day
    while d <= last:
        if d.weekday() in weekdays:
            existing = exception_on(owner, meeting_id, d)
            if not (existing and existing.kind == SKIP):
                override_occurrence(owner, meeting_id, d, start, end, location)
                count += 1
        d += timedelta(days=1)
    return f"Changed for {count} event{'s' if count != 1 else ''}."


def get_meeting(owner, meeting_id):
    """One weekly meeting as a dict (days, start_time, end_time, location, end_date ...), or a PlannerError."""
    return dict(_meeting_row(owner, meeting_id))


def exception_on(owner, meeting_id, day):
    """The exception of one occurrence (a MeetingException), or None."""
    return next((e for e in list_exceptions(owner) if e.meeting_id == meeting_id and e.day == day), None)


def _meeting_row(owner, meeting_id):
    with _conn() as conn:
        row = conn.execute(f"SELECT * FROM {_owner_table(owner)} WHERE id=?", (meeting_id,)).fetchone()
    if not row:
        raise PlannerError("That meeting does not exist.")
    return row


# ---------- exceptions: "this occurrence" ----------
def _check_day(owner, meeting_id, day):
    row = _meeting_row(owner, meeting_id)
    if str(day.weekday()) not in row["days"].split(","):
        raise PlannerError("That meeting does not happen on that day.")


def _put_exception(owner, meeting_id, day, kind, start=None, end=None, location=None):
    MeetingException(owner, meeting_id, day, kind, start, end, location)           # validated
    _check_day(owner, meeting_id, day)
    with _conn() as conn:
        conn.execute("INSERT INTO meeting_exceptions(owner, meeting_id, day, kind, start_time, end_time, location) VALUES (?,?,?,?,?,?,?) "
                     "ON CONFLICT(owner, meeting_id, day) DO UPDATE SET kind=excluded.kind, start_time=excluded.start_time, "
                     "end_time=excluded.end_time, location=excluded.location",
                     (owner, meeting_id, day.isoformat(), kind, timeutil.fmt_hhmm(start) if start else None, timeutil.fmt_hhmm(end) if end else None, location))
        conn.commit()


def skip_occurrence(owner, meeting_id, day):
    """This occurrence does not happen (the rest of the series does)."""
    _put_exception(owner, meeting_id, day, SKIP)


def override_occurrence(owner, meeting_id, day, start, end, location=None):
    """This occurrence happens at another time (and place when given); the rest of the series does not change."""
    _put_exception(owner, meeting_id, day, OVERRIDE, start, end, location)


def restore_occurrence(owner, meeting_id, day):
    """Back to the series: drop the exception of that day."""
    with _conn() as conn:
        conn.execute("DELETE FROM meeting_exceptions WHERE owner=? AND meeting_id=? AND day=?", (owner, meeting_id, day.isoformat()))
        conn.commit()


def list_exceptions(owner=None):
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM meeting_exceptions" + (" WHERE owner=?" if owner else "") + " ORDER BY day, id", (owner,) if owner else ()).fetchall()
    return [MeetingException(r["owner"], r["meeting_id"], date.fromisoformat(r["day"]), r["kind"],
                             timeutil.parse_hhmm(r["start_time"]) if r["start_time"] else None,
                             timeutil.parse_hhmm(r["end_time"]) if r["end_time"] else None, r["location"]) for r in rows]


# ---------- one-off events ----------
def _legacy_columns(start, end, all_day, tz):
    """The local date and times the older parts of the app read (date, time, end_time)."""
    s, e = timeutil.to_local(start, tz), timeutil.to_local(end, tz)
    if all_day:
        return s.date().isoformat(), None, None
    return s.date().isoformat(), timeutil.fmt_hhmm(s.time()), timeutil.fmt_hhmm(e.time()) if e.date() == s.date() else None


def add_event(title, start, end, all_day=False, location="", commute_before=0, commute_after=0, busy=True, course_id=None, source=None):
    """Save a one-off event (start and end are UTC datetimes). Returns its id."""
    Event(0, title, start, end, all_day, location, commute_before, commute_after, busy, course_id, source)       # validated
    date_text, t, et = _legacy_columns(start, end, all_day, store.get_term().zone)
    with _conn() as conn:
        cur = conn.execute("INSERT INTO events(title, date, course_id, time, end_time, all_day, location, commute_before, commute_after, busy, start_utc, end_utc, source) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (title.strip(), date_text, course_id, t, et, int(all_day), location or None, commute_before, commute_after, int(bool(busy)),
                            timeutil.utc_iso(start), timeutil.utc_iso(end), source))
        conn.commit()
        return cur.lastrowid


def update_event(event_id, title, start, end, all_day=False, location="", commute_before=0, commute_after=0, busy=True, course_id=None):
    Event(event_id, title, start, end, all_day, location, commute_before, commute_after, busy, course_id)
    date_text, t, et = _legacy_columns(start, end, all_day, store.get_term().zone)
    with _conn() as conn:
        conn.execute("UPDATE events SET title=?, date=?, course_id=?, time=?, end_time=?, all_day=?, location=?, commute_before=?, commute_after=?, busy=?, "
                     "start_utc=?, end_utc=? WHERE id=?",
                     (title.strip(), date_text, course_id, t, et, int(all_day), location or None, commute_before, commute_after, int(bool(busy)),
                      timeutil.utc_iso(start), timeutil.utc_iso(end), event_id))
        conn.commit()


def events_by_source(prefix):
    """{source: event} for the events whose source starts with `prefix` (what a calendar import brought in)."""
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM events WHERE source LIKE ?", (prefix + "%",)).fetchall()
    term = store.get_term()
    return {r["source"]: _event_from_row(r, term) for r in rows}


def delete_event(event_id):
    with _conn() as conn:
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        conn.commit()


def _event_from_row(row, term):
    row = dict(row)
    if row.get("start_utc") and row.get("end_utc"):
        return Event(row["id"], row["title"], timeutil.parse_utc(row["start_utc"]), timeutil.parse_utc(row["end_utc"]), bool(row["all_day"]), row.get("location") or "",
                     row["commute_before"], row["commute_after"], bool(row["busy"]), row.get("course_id"), row.get("source"))
    return legacy_event(row, term)


def list_events(first, last):
    """The events that touch the local days first..last (one-off events of the planner, and the older dated events as legacy_event reads them)."""
    term = store.get_term()
    lo, _ = timeutil.day_bounds_utc(first, term.zone)
    _, hi = timeutil.day_bounds_utc(last, term.zone)
    wide_lo, wide_hi = timeutil.utc_iso(lo - timedelta(hours=5)), timeutil.utc_iso(hi + timedelta(hours=5))     # room for the commute (4 hours at most)
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM events WHERE (start_utc IS NOT NULL AND start_utc <= ? AND end_utc >= ?) OR (start_utc IS NULL AND date BETWEEN ? AND ?) "
                            "ORDER BY COALESCE(start_utc, date), id", (wide_hi, wide_lo, (first - timedelta(days=1)).isoformat(), last.isoformat())).fetchall()
    return [_event_from_row(r, term) for r in rows]


# ---------- what the planner reads ----------
def load_series():
    """The courses (with weekly meetings, not the finished ones) and the activities as Series."""
    out = []
    by_course = {}
    for m in crud.list_meetings():
        by_course.setdefault(m["course_id"], []).append(m)
    for c in crud.list_courses(section=None):
        meetings = by_course.get(c["id"])
        if not meetings or crud.course_status(c) == "Completed":
            continue
        out.append(Series(COURSE, c["id"], crud.show_code(c["code"]) or c["name"], tuple(_meeting(m) for m in meetings), crud.course_color(c), True, False))
    with _conn() as conn:
        for a in conn.execute("SELECT * FROM activities ORDER BY id").fetchall():
            ms = conn.execute("SELECT * FROM activity_meetings WHERE activity_id=? ORDER BY id", (a["id"],)).fetchall()
            out.append(Series(ACTIVITY, a["id"], a["name"], tuple(_meeting(m, a["location"]) for m in ms), a["color"] or "", bool(a["busy"]), bool(a["in_breaks"])))
    return out


def _meeting(row, default_location=None):
    return Meeting(row["id"], frozenset(int(d) for d in row["days"].split(",") if d != ""), timeutil.parse_hhmm(row["start_time"]), timeutil.parse_hhmm(row["end_time"]),
                   row["location"] or default_location or "", date.fromisoformat(row["end_date"]) if row["end_date"] else None)


def commitments(first, last):
    """All the Blocks (classes, activities, events with their commute) of the local days first..last, from the saved setup."""
    from .commitments import blocks
    return blocks(store.load_config(), load_series(), list_exceptions(), list_events(first, last), first, last)
