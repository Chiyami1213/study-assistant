"""Time helpers of the study planner. Pure: no database, no UI.

Rule of the planner: every moment is STORED in UTC (an ISO text "2026-11-16T14:30:00Z") and SHOWN in the term's time zone. A day is a local calendar day of
that zone; "08:00" on a day means 08:00 on the wall clock of the zone, whatever the daylight-saving offset of that day is."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc


def zone(name):
    """The ZoneInfo of an IANA name ("America/New_York"); ValueError when there is no such zone."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError) as e:
        raise ValueError(f"Unknown time zone: {name!r}") from e


def to_utc(day, at, tz):
    """The UTC moment of the wall-clock time `at` (a datetime.time) on the local `day` in zone `tz` (a name or a ZoneInfo).
    A wall-clock time that does not exist (the hour skipped when the clocks go forward) is read with the offset before the change; one that happens
    twice (when the clocks go back) is read as its first occurrence."""
    z = tz if isinstance(tz, ZoneInfo) else zone(tz)
    local = datetime(day.year, day.month, day.day, at.hour, at.minute, at.second, tzinfo=z, fold=0)
    return local.astimezone(UTC)


def to_local(moment, tz):
    """A UTC datetime as a datetime in the zone `tz`."""
    z = tz if isinstance(tz, ZoneInfo) else zone(tz)
    if moment.tzinfo is None:
        raise ValueError("A moment needs a time zone (UTC).")
    return moment.astimezone(z)


def local_day(moment, tz):
    """The local calendar day of a UTC moment."""
    return to_local(moment, tz).date()


def day_bounds_utc(day, tz):
    """(start, end) in UTC of the local calendar day: midnight to the next midnight (23 or 25 hours long on a daylight-saving change)."""
    z = tz if isinstance(tz, ZoneInfo) else zone(tz)
    start = datetime(day.year, day.month, day.day, tzinfo=z).astimezone(UTC)
    nxt = day + timedelta(days=1)
    return start, datetime(nxt.year, nxt.month, nxt.day, tzinfo=z).astimezone(UTC)


def utc_iso(moment):
    """The storage text of a UTC moment: '2026-11-16T14:30:00Z' (seconds, no fractions)."""
    if moment.tzinfo is None:
        raise ValueError("A moment needs a time zone (UTC).")
    return moment.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text):
    """The UTC datetime of a stored text ('2026-11-16T14:30:00Z')."""
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def parse_hhmm(text):
    """'08:30' -> time(8, 30); ValueError for anything else."""
    try:
        h, m = text.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Not a time (expected HH:MM): {text!r}") from e


def fmt_hhmm(at):
    return f"{at.hour:02d}:{at.minute:02d}"


def minutes_between(a, b):
    """Whole minutes from the earlier to the later of two datetimes (b - a)."""
    return int((b - a).total_seconds() // 60)


def daterange(first, last):
    """Every date from `first` to `last`, both included (nothing when last is before first)."""
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)
