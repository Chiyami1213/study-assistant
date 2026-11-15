"""Study sessions of the study planner: the blocks of time set aside for a task, placed by the auto-planner or by hand. Pure: no database, no UI.

- Session: a task, a start and an end (UTC) and where it came from ("auto" or "manual").
- placement_problems(): what is wrong with putting a session somewhere (outside the term or in a break, over another session, outside the awake hours,
  over a class or event, shorter than the minimum block). Some problems are hard (never allowed), some soft (allowed when the user insists).
- autoplan(): fills the free time earliest-deadline-first, from the start-ahead date, in pieces no shorter than the minimum block, splitting a task across
  sessions when it has to. The same input always gives the same plan."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import freetime, timeutil
from .models import PlannerError

AUTO, MANUAL = "auto", "manual"


@dataclass(frozen=True)
class Session:
    id: int
    task_id: int
    start: datetime
    end: datetime
    source: str = MANUAL

    def __post_init__(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise PlannerError("A session's times have to be UTC moments.")
        if self.end <= self.start:
            raise PlannerError("A study session has to end after it starts.")
        if self.source not in (AUTO, MANUAL):
            raise PlannerError("A session is placed automatically or by hand.")

    @property
    def minutes(self):
        return int((self.end - self.start).total_seconds() // 60)

    def overlaps(self, start, end):
        return self.start < end and start < self.end


@dataclass(frozen=True)
class Problem:
    kind: str                # "term", "break", "session", "awake", "busy", "short"
    message: str
    hard: bool               # a hard problem can not be overridden


def placement_problems(config, start, end, blocks, other_sessions):
    """Everything that is wrong with a session from start to end (UTC): a list of Problems, hard ones first; empty when it fits.
    `blocks`: the commitments around it; `other_sessions`: the sessions it must not overlap (leave the session being moved out of it)."""
    tz = config.term.zone
    out = []
    if end <= start:
        return [Problem("time", "A study session has to end after it starts.", True)]
    day = timeutil.local_day(start, tz)
    end_day = timeutil.local_day(end - timedelta(seconds=1), tz)
    if not config.term.in_term(day):
        out.append(Problem("term", "That day is outside the term.", True))
    elif config.term.break_on(day):
        out.append(Problem("break", f"That day is in {config.term.break_on(day).name}: nothing is planned in a break.", True))
    for s in other_sessions:
        if s.overlaps(start, end):
            out.append(Problem("session", "It overlaps another study session.", True))
            break
    window = config.awake_interval(day) if config.term.is_planning_day(day) else None
    if window is not None and (day != end_day or start < window[0] or end > window[1]):
        out.append(Problem("awake", "Part of it is outside your awake hours.", False))
    for b in blocks:
        if b.busy and b.start < end and start < b.end:
            out.append(Problem("busy", f"It overlaps {b.label}.", False))
    if int((end - start).total_seconds() // 60) < config.min_block_minutes:
        out.append(Problem("short", f"It is shorter than the minimum block of {config.min_block_minutes} minutes.", False))
    out.sort(key=lambda p: not p.hard)
    return out


# ---------------------------------------------------------------- the auto-planner
@dataclass(frozen=True)
class Chunk:
    task_id: int
    start: datetime
    end: datetime

    @property
    def minutes(self):
        return int((self.end - self.start).total_seconds() // 60)


@dataclass(frozen=True)
class PlanResult:
    add: tuple                   # Chunks to create, in time order
    remove: tuple                # ids of the automatic sessions that are replaced
    unplaced: tuple              # (task id, minutes that did not fit), by task id
    late: tuple                  # ids of overdue tasks (placed as soon as there is room)

    def unplaced_of(self, task_id):
        return dict(self.unplaced).get(task_id, 0)

    @property
    def complete(self):
        return not self.unplaced


def _place(candidates, remaining, minimum):
    """Fit `remaining` minutes into the free pieces (earliest first). Every session is at least `minimum` minutes, except for a task that needs less than that in
    all. A piece that is too short for the rest is used whole when the rest is still at least the minimum, else only as much as leaves a minimum-sized rest;
    when the task cannot be split into two sessions of at least the minimum, the piece is skipped. Returns (chunks as (start, minutes), minutes left)."""
    chunks = []
    for s, e in candidates:
        if remaining <= 0:
            break
        piece = int((e - s).total_seconds() // 60)
        if remaining < minimum:
            take = remaining
        elif piece >= remaining:
            take = remaining
        elif remaining - piece >= minimum:
            take = piece
        elif remaining >= 2 * minimum:
            take = remaining - minimum
        else:
            continue
        chunks.append((s, take))
        remaining -= take
    return chunks, remaining


def autoplan(config, tasks, blocks, sessions, now, include_undated=False):
    """Plan study sessions for the unfinished tasks with a due date (earliest deadline first, ties by id).
    - The automatic sessions that have not started are replaced; manual sessions, and any session already begun, stay and count as planned time.
    - A task is planned from its start-ahead date (or now) to its deadline; an overdue task is placed as soon as there is room (reported in `late`).
    - What a task still needs is its remaining time minus what its kept sessions already cover before its deadline.
    - With include_undated, tasks without a due date are planned after all the others, anywhere before the term ends."""
    tz = config.term.zone
    minimum = config.min_block_minutes
    remove = tuple(sorted(s.id for s in sessions if s.source == AUTO and s.start >= now))
    kept = [s for s in sessions if s.id not in set(remove)]
    work = [t for t in tasks if not t.is_done and (t.due is not None or include_undated)]
    work.sort(key=lambda t: (t.due is None, t.due or now, t.id))
    if not work:
        return PlanResult((), remove, (), ())
    first = timeutil.local_day(now, tz)
    term_end = config.term.exams_end
    dated_days = [timeutil.local_day(t.due, tz) for t in work if t.due is not None and not t.is_overdue(now)]
    needs_term_end = any(t.due is None or t.is_overdue(now) for t in work)
    last = term_end if needs_term_end or not dated_days else min(max(dated_days), term_end)
    pool = freetime.free_intervals(config, blocks, kept, first, max(first, last), now)
    horizon = timeutil.day_bounds_utc(term_end, tz)[1]
    add, unplaced, late = [], [], []
    for t in work:
        overdue = t.is_overdue(now)
        lo = freetime._release(t, now, tz)
        hi = horizon if (t.due is None or overdue) else t.due
        if overdue:
            late.append(t.id)
        need = max(0, t.remaining_minutes - freetime.planned_minutes(kept, t.id, lo, hi))
        if need == 0:
            continue
        candidates = [(max(s, lo), min(e, hi)) for s, e in pool]
        candidates = [(s, e) for s, e in candidates if e - s >= timedelta(minutes=minimum)]
        chunks, left = _place(candidates, need, minimum)
        placed = [(s, s + timedelta(minutes=m)) for s, m in chunks]
        add.extend(Chunk(t.id, s, e) for s, e in placed)
        if placed:
            pool = [(s, e) for s, e in freetime.subtract(pool, placed) if e - s >= timedelta(minutes=minimum)]
        if left > 0:
            unplaced.append((t.id, left))
    add.sort(key=lambda c: (c.start, c.task_id))
    return PlanResult(tuple(add), remove, tuple(sorted(unplaced)), tuple(sorted(late)))
