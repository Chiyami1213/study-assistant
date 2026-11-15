"""Recurring commitments and one-off events of the study planner. Pure: no database, no UI.

- A Series is a course or an activity (office hours, work, gym, me-time) with weekly Meetings: weekdays, start and end on the wall clock of the term's zone,
  a location and an optional last day (end_date).
- An occurrence of a meeting can differ from the series: an Exception skips it or overrides its time and place ("this occurrence"); editing the Meeting itself
  changes the whole series.
- An Event happens once: start and end (UTC), an all-day flag, a location, commute minutes before and after (counted as busy time), and a busy flag
  (busy=False shows on the calendar but does not block study).
- blocks() turns all of it into the sorted list of Blocks of a date range: the busy time that the free-time engine of phase 4 subtracts from the awake time."""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from . import timeutil
from .models import PlannerConfig, PlannerError

COURSE, ACTIVITY = "course", "activity"
SKIP, OVERRIDE = "skip", "override"
MAX_COMMUTE = 240                      # minutes before or after an event


# ---------------------------------------------------------------- recurring meetings
@dataclass(frozen=True)
class Meeting:
    """One weekly slot: on these weekdays (Monday = 0), from start to end on the same day, until end_date (inclusive) when given."""
    id: int
    days: frozenset
    start: time
    end: time
    location: str = ""
    end_date: date = None

    def __post_init__(self):
        if not self.days:
            raise PlannerError("A weekly meeting needs at least one weekday.")
        if not all(isinstance(d, int) and 0 <= d <= 6 for d in self.days):
            raise PlannerError("Weekdays are numbers from 0 (Monday) to 6 (Sunday).")
        if self.end <= self.start:
            raise PlannerError(f"A meeting has to end ({self.end:%H:%M}) after it starts ({self.start:%H:%M}) on the same day.")


@dataclass(frozen=True)
class Series:
    """A course or an activity and its weekly meetings. Classes follow the term's class days and never meet in a break; an activity runs to the end of
    the exam period and skips the breaks unless in_breaks is set."""
    kind: str
    owner_id: int
    name: str
    meetings: tuple = ()
    color: str = ""
    busy: bool = True
    in_breaks: bool = False

    def __post_init__(self):
        if self.kind not in (COURSE, ACTIVITY):
            raise PlannerError("A series is a course or an activity.")
        if not self.name.strip():
            raise PlannerError("A course or an activity needs a name.")


@dataclass(frozen=True)
class MeetingException:
    """One occurrence that differs: skipped (SKIP), or held at another time or place (OVERRIDE)."""
    owner: str
    meeting_id: int
    day: date
    kind: str
    start: time = None
    end: time = None
    location: str = None

    def __post_init__(self):
        if self.owner not in (COURSE, ACTIVITY) or self.kind not in (SKIP, OVERRIDE):
            raise PlannerError("An exception belongs to a course or an activity and either skips or overrides one occurrence.")
        if self.kind == OVERRIDE:
            if self.start is None or self.end is None:
                raise PlannerError("A moved occurrence needs a start and an end time.")
            if self.end <= self.start:
                raise PlannerError(f"A moved occurrence has to end ({self.end:%H:%M}) after it starts ({self.start:%H:%M}).")


@dataclass(frozen=True)
class Occurrence:
    """One meeting on one day, on the wall clock of the term's zone."""
    kind: str
    owner_id: int
    meeting_id: int
    day: date
    start: time
    end: time
    location: str
    name: str
    color: str = ""
    busy: bool = True
    changed: bool = False                 # True when an exception moved it


def occurrences(series, exceptions, first, last, term):
    """Every occurrence of the series between two dates (inclusive), in time order. A class meets from the first day to the last day of classes, an
    activity to the last day of exams; breaks are left out (an activity with in_breaks stays); a meeting's end_date cuts it short; exceptions apply."""
    skips, overrides = {}, {}
    for e in exceptions:
        (skips if e.kind == SKIP else overrides)[(e.owner, e.meeting_id, e.day)] = e
    out = []
    for s in series:
        hi = term.classes_end if s.kind == COURSE else term.exams_end
        lo_day, hi_day = max(first, term.start), min(last, hi)
        for day in timeutil.daterange(lo_day, hi_day):
            if term.break_on(day) and not (s.kind == ACTIVITY and s.in_breaks):
                continue
            for m in s.meetings:
                if day.weekday() not in m.days or (m.end_date is not None and day > m.end_date):
                    continue
                key = (s.kind, m.id, day)
                if key in skips:
                    continue
                o = overrides.get(key)
                out.append(Occurrence(s.kind, s.owner_id, m.id, day, o.start if o else m.start, o.end if o else m.end,
                                      (o.location if o and o.location is not None else m.location) or "", s.name, s.color, s.busy, bool(o)))
    out.sort(key=lambda o: (o.day, o.start, o.end, o.name))
    return out


def occurrence_interval(occ, tz):
    """(start, end) in UTC of an occurrence."""
    return timeutil.to_utc(occ.day, occ.start, tz), timeutil.to_utc(occ.day, occ.end, tz)


# ---------------------------------------------------------------- one-off events
@dataclass(frozen=True)
class Event:
    """A one-off event. start and end are UTC moments; an all-day event covers whole local days (start = midnight of the first, end = midnight after the
    last). busy=False: shown on the calendar, but study may be planned over it. Commute minutes are busy time before and after (when the event is busy)."""
    id: int
    title: str
    start: datetime
    end: datetime
    all_day: bool = False
    location: str = ""
    commute_before: int = 0
    commute_after: int = 0
    busy: bool = True
    course_id: int = None
    source: str = None

    def __post_init__(self):
        if not self.title.strip():
            raise PlannerError("An event needs a title.")
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise PlannerError("An event's times have to be UTC moments.")
        if self.end <= self.start and not (self.all_day and self.end == self.start):
            raise PlannerError("An event has to end after it starts.")
        for minutes in (self.commute_before, self.commute_after):
            if not isinstance(minutes, int) or isinstance(minutes, bool) or not 0 <= minutes <= MAX_COMMUTE:
                raise PlannerError(f"Commute time is a whole number of minutes from 0 to {MAX_COMMUTE}.")

    @property
    def busy_start(self):
        return self.start - timedelta(minutes=self.commute_before)

    @property
    def busy_end(self):
        return self.end + timedelta(minutes=self.commute_after)


def timed_event(id, title, day, start, end, tz, **kw):
    """An Event from a local day and wall-clock times (end on the same day, or later when end_day is given)."""
    end_day = kw.pop("end_day", day)
    return Event(id, title, timeutil.to_utc(day, start, tz), timeutil.to_utc(end_day, end, tz), **kw)


def all_day_event(id, title, first_day, last_day, tz, **kw):
    """An all-day Event from the first to the last local day (both included)."""
    if last_day < first_day:
        raise PlannerError("An all-day event cannot end before it starts.")
    start, _ = timeutil.day_bounds_utc(first_day, tz)
    _, end = timeutil.day_bounds_utc(last_day, tz)
    return Event(id, title, start, end, all_day=True, **kw)


def legacy_event(row, term):
    """An Event from an old row of the events table (a date and optional local HH:MM times, as exams and deadlines were saved before the planner).
    With a start time it is a timed event (end = the end time, else two hours after the start: the length the Calendar draws for an exam) and busy;
    without a time it is an all-day marker that does not block study."""
    row = dict(row)
    day = date.fromisoformat(row["date"])
    title = row["title"] or "Event"
    if row.get("time"):
        start = timeutil.parse_hhmm(row["time"])
        end_text = row.get("end_time")
        end = timeutil.parse_hhmm(end_text) if end_text else None
        start_utc = timeutil.to_utc(day, start, term.zone)
        end_utc = timeutil.to_utc(day, end, term.zone) if end and end > start else start_utc + timedelta(hours=2)
        return Event(row["id"], title, start_utc, end_utc, location=row.get("location") or "", busy=True, course_id=row.get("course_id"), source="legacy")
    return all_day_event(row["id"], title, day, day, term.zone, busy=False, course_id=row.get("course_id"), source="legacy")


# ---------------------------------------------------------------- everything as time blocks
@dataclass(frozen=True)
class Block:
    """A stretch of time on the calendar. busy blocks are what the free-time engine subtracts from the awake time."""
    start: datetime
    end: datetime
    kind: str                       # "class", "activity", "event" or "commute"
    label: str
    busy: bool
    owner_id: int = None
    ref_id: int = None              # the meeting or event it comes from
    color: str = ""
    location: str = ""
    changed: bool = False
    all_day: bool = False           # an all-day event (the calendar shows it in the all-day strip, not on the time grid)
    source: str = None              # "legacy" for the older dated events (exams); None for the rest


def blocks(config, series, exceptions, events, first, last):
    """All Blocks that touch the local days first..last, sorted by start. Classes, activities and events (with their commute blocks). A block is kept
    when any part of it falls inside the range."""
    tz = config.term.zone
    lo, _ = timeutil.day_bounds_utc(first, tz)
    _, hi = timeutil.day_bounds_utc(last, tz)
    found = []
    for o in occurrences(series, exceptions, first, last, config.term):
        s, e = occurrence_interval(o, tz)
        found.append(Block(s, e, "class" if o.kind == COURSE else "activity", o.name, o.busy, o.owner_id, o.meeting_id, o.color, o.location, o.changed))
    for ev in events:
        found.append(Block(ev.start, ev.end, "event", ev.title, ev.busy, ev.course_id, ev.id, "", ev.location, all_day=ev.all_day, source=ev.source))
        if ev.busy and not ev.all_day:                                  # traveling takes time too
            if ev.commute_before:
                found.append(Block(ev.busy_start, ev.start, "commute", f"Travel to {ev.title}", True, ev.course_id, ev.id))
            if ev.commute_after:
                found.append(Block(ev.end, ev.busy_end, "commute", f"Travel from {ev.title}", True, ev.course_id, ev.id))
    found = [b for b in found if b.end > lo and b.start < hi]
    found.sort(key=lambda b: (b.start, b.end, b.kind, b.label))
    return found
