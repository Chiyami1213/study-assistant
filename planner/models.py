"""The study planner's setup: the term, its breaks, the awake window of every weekday and the minimum study block.

Pure data and rules: no database, no UI. A model that is not valid cannot be built (PlannerError), so everything that reaches the scheduling code is sound:
- Term: first day, last day of classes, last day of the exam period, an IANA time zone, and named breaks (date ranges that are left out of planning).
- AwakeTimes: a wake and a bed time for each weekday (Monday = 0 ... Sunday = 6); study is only ever planned between them, on the same calendar day.
- PlannerConfig: both, plus the minimum length of a study block (minutes)."""
from dataclasses import dataclass, field, replace
from datetime import date, time

from . import timeutil

DEFAULT_MIN_BLOCK = 30
MIN_BLOCK_RANGE = (5, 240)
DEFAULT_WAKE, DEFAULT_BED = time(8, 0), time(23, 0)
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class PlannerError(ValueError):
    """A setup that does not make sense (the message says why, in words a student can act on)."""


def check_min_block(minutes):
    """The minimum study block (whole minutes, MIN_BLOCK_RANGE); PlannerError otherwise. Returns the value."""
    lo, hi = MIN_BLOCK_RANGE
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not lo <= minutes <= hi:
        raise PlannerError(f"The minimum study block has to be a whole number of minutes from {lo} to {hi}.")
    return minutes


@dataclass(frozen=True)
class Break:
    """A named range of days (both ends included) that is left out of planning: a holiday, spring break, reading days."""
    name: str
    start: date
    end: date

    def __post_init__(self):
        if not self.name.strip():
            raise PlannerError("A break needs a name.")
        if self.end < self.start:
            raise PlannerError(f"The break {self.name!r} ends ({self.end}) before it starts ({self.start}).")

    def contains(self, day):
        return self.start <= day <= self.end

    @property
    def days(self):
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class DayWindow:
    """When one weekday's study may happen: from wake to bed, on that calendar day (so the bed time is later than the wake time)."""
    wake: time = DEFAULT_WAKE
    bed: time = DEFAULT_BED

    def __post_init__(self):
        if self.bed <= self.wake:
            raise PlannerError(f"The bed time ({self.bed:%H:%M}) has to be later than the wake time ({self.wake:%H:%M}).")

    @property
    def minutes(self):
        return (self.bed.hour * 60 + self.bed.minute) - (self.wake.hour * 60 + self.wake.minute)


@dataclass(frozen=True)
class AwakeTimes:
    """The window of each weekday, Monday first. Build one with AwakeTimes.uniform(), change a day with with_day()."""
    windows: tuple = field(default_factory=lambda: (DayWindow(),) * 7)

    def __post_init__(self):
        if len(self.windows) != 7 or not all(isinstance(w, DayWindow) for w in self.windows):
            raise PlannerError("Awake times need one wake and bed time for each of the seven weekdays.")

    @classmethod
    def uniform(cls, wake=DEFAULT_WAKE, bed=DEFAULT_BED):
        return cls((DayWindow(wake, bed),) * 7)

    def with_day(self, weekday, window):
        if not 0 <= weekday <= 6:
            raise PlannerError("A weekday is a number from 0 (Monday) to 6 (Sunday).")
        items = list(self.windows)
        items[weekday] = window
        return AwakeTimes(tuple(items))

    def for_weekday(self, weekday):
        return self.windows[weekday]

    def for_date(self, day):
        return self.windows[day.weekday()]


@dataclass(frozen=True)
class Term:
    """One term: planning runs from `start` to `exams_end` (classes end on `classes_end`), in the time zone `tz`, except on the days of the breaks."""
    start: date
    classes_end: date
    exams_end: date
    tz: str = "UTC"
    breaks: tuple = ()

    def __post_init__(self):
        if self.classes_end < self.start:
            raise PlannerError(f"The last day of classes ({self.classes_end}) is before the first day ({self.start}).")
        if self.exams_end < self.classes_end:
            raise PlannerError(f"The last day of exams ({self.exams_end}) is before the last day of classes ({self.classes_end}).")
        try:
            timeutil.zone(self.tz)
        except ValueError as e:
            raise PlannerError(str(e)) from e
        if not all(isinstance(b, Break) for b in self.breaks):
            raise PlannerError("The breaks of a term have to be Break values.")

    @property
    def zone(self):
        return timeutil.zone(self.tz)

    def in_term(self, day):
        """Is the day inside the term (first day to last exam day)?"""
        return self.start <= day <= self.exams_end

    def break_on(self, day):
        """The break that covers the day (the first one when several do), or None."""
        return next((b for b in self.breaks if b.contains(day)), None)

    def is_planning_day(self, day):
        """Study is planned on a day that is in the term and not in a break."""
        return self.in_term(day) and self.break_on(day) is None

    def planning_days(self, first, last):
        """The planning days between two dates (inclusive), in order."""
        lo, hi = max(first, self.start), min(last, self.exams_end)
        return [d for d in timeutil.daterange(lo, hi) if self.break_on(d) is None]


@dataclass(frozen=True)
class PlannerConfig:
    term: Term
    awake: AwakeTimes = field(default_factory=AwakeTimes)
    min_block_minutes: int = DEFAULT_MIN_BLOCK

    def __post_init__(self):
        check_min_block(self.min_block_minutes)

    def awake_interval(self, day):
        """(start, end) in UTC of the time study may be planned on a local day, or None when the day is outside the term or in a break."""
        if not self.term.is_planning_day(day):
            return None
        window = self.awake.for_date(day)
        return timeutil.to_utc(day, window.wake, self.term.zone), timeutil.to_utc(day, window.bed, self.term.zone)

    def awake_window(self, day):
        """(start, end) in UTC of the awake time of a local day, whatever the day is (a break, outside the term): where personal work may go."""
        window = self.awake.for_date(day)
        return timeutil.to_utc(day, window.wake, self.term.zone), timeutil.to_utc(day, window.bed, self.term.zone)

    def awake_minutes(self, day):
        """How many minutes of the day are awake time (0 on a day without planning)."""
        interval = self.awake_interval(day)
        return timeutil.minutes_between(*interval) if interval else 0

    def with_term(self, term):
        return replace(self, term=term)
