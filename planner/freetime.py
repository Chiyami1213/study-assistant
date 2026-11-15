"""The free-time engine and the cushion of the study planner. Pure: no database, no UI.

Free time = awake time - busy time (classes, activities, busy events and their commute) - study sessions already planned, with the pieces shorter than the minimum
study block dropped and, when a clock is given, nothing before now. Everything is a half-open UTC interval [start, end).

The cushion of a task is how much free study time is left before its deadline after the work that has to be done by then:
    cushion = free minutes in a window ending at the deadline - the remaining minutes of the work that has to fit in that window.
Without start-ahead dates the window starts now and the work is every unfinished task due on or before the deadline (earliest deadline first). A task that may only be
started on a later date (start ahead) can not use the time before that date, so the engine checks every window that opens now or on such a date and reports the tightest one,
which is the exact amount of slack the deadline has. A negative cushion means the work does not fit: the schedule is impossible. A task whose deadline has passed is
due "now": its remaining time still has to be done, so it counts against everything that comes after it."""
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import timeutil

YELLOW_BELOW_MINUTES = 120        # a positive cushion below this is "tight" (yellow); negative is red; the rest is green
GREEN, YELLOW, RED = "green", "yellow", "red"


# ---------------------------------------------------------------- intervals
def _pair(x):
    return (x.start, x.end) if hasattr(x, "start") and hasattr(x, "end") else (x[0], x[1])


def merge(intervals):
    """Sorted, non-overlapping intervals that cover the same time (touching intervals are joined; empty ones dropped)."""
    items = sorted(p for p in (_pair(x) for x in intervals) if p[1] > p[0])
    out = []
    for s, e in items:
        if out and s <= out[-1][1]:
            if e > out[-1][1]:
                out[-1] = (out[-1][0], e)
        else:
            out.append((s, e))
    return out


def subtract(base, remove):
    """The parts of the intervals in `base` that are not covered by `remove` (both may overlap internally)."""
    base, remove = merge(base), merge(remove)
    out, j = [], 0
    for s, e in base:
        cur = s
        while j < len(remove) and remove[j][1] <= cur:
            j += 1
        k = j
        while k < len(remove) and remove[k][0] < e:
            rs, re = remove[k]
            if rs > cur:
                out.append((cur, min(rs, e)))
            cur = max(cur, re)
            if cur >= e:
                break
            k += 1
        if cur < e:
            out.append((cur, e))
    return out


def total_minutes(intervals):
    return sum(int((e - s).total_seconds() // 60) for s, e in merge(intervals))


class FreeTime:
    """Free intervals with fast 'how many free minutes between two moments' queries."""

    def __init__(self, intervals):
        self.intervals = merge(intervals)
        self._starts = [s for s, _ in self.intervals]
        self._ends = [e for _, e in self.intervals]
        self._prefix = [0.0]
        for s, e in self.intervals:
            self._prefix.append(self._prefix[-1] + (e - s).total_seconds())

    def seconds_before(self, moment):
        """Free seconds that end at or before `moment` (a piece that is cut by it counts up to it)."""
        i = bisect_left(self._ends, moment)              # intervals i.. end after the moment
        total = self._prefix[i]
        if i < len(self.intervals) and self._starts[i] < moment:
            total += (moment - self._starts[i]).total_seconds()
        return total

    def minutes_between(self, lo, hi):
        """Whole free minutes inside [lo, hi)."""
        if hi <= lo:
            return 0
        return int((self.seconds_before(hi) - self.seconds_before(lo)) // 60)


# ---------------------------------------------------------------- free time
def awake_intervals(config, first, last):
    """The awake time of the local days first..last (inclusive) as UTC intervals: none on a day outside the term or in a break."""
    out = []
    for day in config.term.planning_days(first, last):
        interval = config.awake_interval(day)
        if interval:
            out.append(interval)
    return out


def busy_intervals(blocks):
    """Merged intervals of the busy blocks (classes, activities, busy events and their commute)."""
    return merge((b.start, b.end) for b in blocks if b.busy)


def free_intervals(config, blocks, planned, first, last, now=None):
    """The free study time of the local days first..last: awake time minus busy blocks minus planned sessions, nothing before `now` (when given), and no piece shorter
    than the minimum study block. `planned`: anything with start and end (or (start, end) pairs)."""
    free = subtract(awake_intervals(config, first, last), list(busy_intervals(blocks)) + merge(planned))
    if now is not None:
        free = [(max(s, now), e) for s, e in free if e > now]
    minimum = timedelta(minutes=config.min_block_minutes)
    return [(s, e) for s, e in free if e - s >= minimum]


# ---------------------------------------------------------------- the cushion
@dataclass(frozen=True)
class Cushion:
    task_id: int
    due: datetime
    cushion_minutes: int
    free_minutes: int                # free time in the tightest window
    demand_minutes: int              # work that has to fit in that window
    window_start: datetime
    level: str

    @property
    def negative(self):
        return self.cushion_minutes < 0


@dataclass(frozen=True)
class TimelinePoint:
    day: object                      # the local date of the deadline(s)
    cushion_minutes: int             # the smallest cushion among the tasks due that day
    task_ids: tuple


@dataclass(frozen=True)
class CushionReport:
    items: tuple                     # one Cushion per task with a due date, soonest deadline first
    timeline: tuple                  # one TimelinePoint per deadline day across the term
    any_negative: bool

    def of(self, task_id):
        return next((c for c in self.items if c.task_id == task_id), None)

    @property
    def negative_items(self):
        return tuple(c for c in self.items if c.negative)


def level_of(cushion_minutes):
    if cushion_minutes < 0:
        return RED
    return YELLOW if cushion_minutes < YELLOW_BELOW_MINUTES else GREEN


def _release(task, now, tz):
    """When work on the task may start: now, or the start of the start-ahead day when that is later."""
    start = task.start_date(tz)
    if start is None:
        return now
    return max(now, timeutil.day_bounds_utc(start, tz)[0])


@dataclass(frozen=True)
class Job:
    """Work seen by the engine: `minutes` of work that may start at `release` and has to be done by `deadline` (both UTC)."""
    id: int
    release: datetime
    deadline: datetime
    minutes: int


def slacks(jobs, free, now):
    """{job id: (slack, free minutes, demand, window start)} of every job: the tightest window [r, deadline] with r = now or the release of a job that is due
    on or before this one, where slack = free minutes in the window - the minutes of all the jobs due on or before it that cannot start before r."""
    if not isinstance(free, FreeTime):
        free = FreeTime(free)
    jobs = sorted(jobs, key=lambda j: (j.deadline, j.id))
    out = {}
    for j in jobs:
        earlier = [u for u in jobs if u.deadline <= j.deadline]            # due on or before: jobs due at the same moment count each other
        best = None
        for r in sorted({now} | {u.release for u in earlier}):
            if r > j.deadline:
                continue
            demand = sum(u.minutes for u in earlier if u.release >= r)
            capacity = free.minutes_between(r, j.deadline)
            slack = capacity - demand
            if best is None or slack < best[0]:
                best = (slack, capacity, demand, r)
        if best is None:                                                    # released after its own deadline: it can not be done at all
            demand = sum(u.minutes for u in earlier)
            best = (-demand, 0, demand, now)
        out[j.id] = best
    return out


def planned_minutes(sessions, task_id, lo, hi):
    """Minutes of the sessions of one task (anything with task_id, start and end) that lie inside [lo, hi): the work already placed before its deadline."""
    total = 0.0
    for s in sessions:
        if getattr(s, "task_id", None) == task_id:
            a, b = max(s.start, lo), min(s.end, hi)
            if b > a:
                total += (b - a).total_seconds()
    return int(total // 60)


def cushions(tasks, free, now, tz, planned=()):
    """The Cushion of every unfinished task with a due date, earliest deadline first (ties by id). `free`: a FreeTime (or a list of intervals) that covers
    the time up to the last deadline; time outside what it holds counts as not free. `planned`: study sessions already placed. The free time must already leave
    their time out; a session that belongs to a task (it has a task_id) also counts as work done, so it lowers the work that task still needs before its deadline."""
    work = sorted((t for t in tasks if not t.is_done and t.due is not None), key=lambda t: (t.due, t.id))
    planned = list(planned)
    jobs = []
    for t in work:
        release, deadline = _release(t, now, tz), max(t.due, now)                       # a deadline that has passed is now
        jobs.append(Job(t.id, release, deadline, max(0, t.remaining_minutes - planned_minutes(planned, t.id, release, deadline))))
    found = slacks(jobs, free, now)
    return [Cushion(t.id, t.due, found[t.id][0], found[t.id][1], found[t.id][2], found[t.id][3], level_of(found[t.id][0])) for t in work]


def timeline(items, tz):
    """One point per deadline day, in date order: the smallest cushion among the tasks due that day."""
    days = {}
    for c in items:
        days.setdefault(timeutil.local_day(c.due, tz), []).append(c)
    return tuple(TimelinePoint(day, min(c.cushion_minutes for c in cs), tuple(c.task_id for c in cs)) for day, cs in sorted(days.items()))


def report(config, tasks, blocks, planned, now):
    """The whole picture for a clock `now` (UTC): free time from today to the last deadline (inside the term), the cushion of each task and the timeline.
    `blocks`: the commitments (classes, activities, events) that cover that range; `planned`: study sessions already placed."""
    tz = config.term.zone
    dated = [t for t in tasks if not t.is_done and t.due is not None]
    if not dated:
        return CushionReport((), (), False)
    first = timeutil.local_day(now, tz)
    last = min(max(timeutil.local_day(t.due, tz) for t in dated), config.term.exams_end)
    free = FreeTime(free_intervals(config, blocks, planned, first, max(first, last), now))
    items = tuple(cushions(tasks, free, now, tz, planned))
    return CushionReport(items, timeline(items, tz), any(c.negative for c in items))
