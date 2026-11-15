"""Phase 4: the cushion (how much free study time is left before each deadline). Pure: no database."""
import random
from datetime import date, datetime, time, timedelta, timezone

import pytest

from planner import commitments as c
from planner import freetime as F
from planner import tasks as T
from planner import timeutil
from planner.models import AwakeTimes, Break, PlannerConfig, Term

NY = "America/New_York"
TERM = Term(date(2026, 9, 1), date(2026, 12, 8), date(2026, 12, 18), NY, (Break("Break", date(2026, 10, 12), date(2026, 10, 13)),))
CFG = PlannerConfig(TERM, AwakeTimes.uniform(time(9), time(17)), 30)          # 480 free minutes a day
MON = date(2026, 9, 7)
NOW = timeutil.to_utc(MON, time(9), NY)                                        # Monday 09:00 local: the day has just begun


def at(day, hh=0, mm=0):
    return timeutil.to_utc(day, time(hh, mm), NY)


def day(n):
    return MON + timedelta(days=n)


def task(id, due, minutes, logged=0, start_ahead=None, state="todo", title=None):
    return T.Task(id, title or f"T{id}", None, "Homework", due, minutes, start_ahead, state, logged)


def free_days(first=0, last=4):
    """The free time of the days MON+first .. MON+last (all awake time: 480 minutes each)."""
    return F.free_intervals(CFG, [], [], day(first), day(last), NOW)


def cush(tasks, free=None, now=NOW):
    free = free if free is not None else free_days()
    return {x.task_id: x for x in F.cushions(tasks, free, now, TERM.zone)}


# ---------- one task ----------
def test_one_task_cushion_is_the_free_time_before_the_deadline_minus_its_work():
    t = task(1, at(day(1), 17), 300)                   # due Tuesday 17:00: two free days (Mon + Tue) = 960 minutes
    x = cush([t])[1]
    assert (x.cushion_minutes, x.free_minutes, x.demand_minutes, x.window_start, x.level) == (660, 960, 300, NOW, F.GREEN)


def test_a_task_partly_done_only_counts_what_is_left():
    assert cush([task(1, at(day(1), 17), 300, logged=120)])[1].cushion_minutes == 960 - 180
    assert cush([task(1, at(day(1), 17), 300, logged=900)])[1].cushion_minutes == 960                # logged more than the estimate: nothing left


def test_free_time_that_has_passed_does_not_count():
    later = timeutil.to_utc(MON, time(13), NY)                                   # four hours of Monday are gone
    free = F.free_intervals(CFG, [], [], MON, day(1), later)
    assert cush([task(1, at(day(1), 17), 100)], free, later)[1].free_minutes == 240 + 480


def test_the_deadline_cuts_the_free_time():
    x = cush([task(1, at(day(0), 12), 60)])[1]                                     # due Monday noon: only 09:00-12:00
    assert (x.free_minutes, x.cushion_minutes) == (180, 120)
    assert cush([task(1, at(day(0), 8), 60)])[1].free_minutes == 0                # due before the free time starts


# ---------- earliest deadline first ----------
def test_cushions_accumulate_in_deadline_order():
    a, b, d = task(1, at(day(0), 17), 200), task(2, at(day(1), 17), 400), task(3, at(day(2), 17), 500)
    r = cush([d, b, a])                                                            # given out of order on purpose
    assert [r[1].cushion_minutes, r[2].cushion_minutes, r[3].cushion_minutes] == [480 - 200, 960 - 600, 1440 - 1100]
    assert [x.task_id for x in F.cushions([d, b, a], free_days(), NOW, TERM.zone)] == [1, 2, 3]


def test_tasks_due_at_the_same_moment_share_the_cushion():
    a, b = task(1, at(day(1), 17), 300), task(2, at(day(1), 17), 200)
    r = cush([a, b])
    assert r[1].cushion_minutes == r[2].cushion_minutes == 960 - 500


def test_done_and_undated_tasks_are_ignored():
    a = task(1, at(day(1), 17), 300)
    r = cush([a, task(2, at(day(0), 17), 400, state="done"), T.Task(3, "Someday", None, "Other", None, 200)])
    assert list(r) == [1] and r[1].cushion_minutes == 960 - 300


# ---------- negative cushions ----------
def test_a_task_that_does_not_fit_has_a_negative_cushion_and_is_red():
    r = cush([task(1, at(day(0), 17), 600)])                                       # 480 free, 600 needed
    assert r[1].cushion_minutes == -120 and r[1].negative and r[1].level == F.RED


def test_an_overloaded_deadline_makes_every_later_cushion_smaller_and_can_make_them_negative():
    a, b = task(1, at(day(0), 17), 700), task(2, at(day(1), 17), 200)             # Monday is 220 minutes short; Tuesday only needs 200 more
    r = cush([a, b])
    assert r[1].cushion_minutes == 480 - 700 and r[2].cushion_minutes == 960 - 900 and r[2].level == F.YELLOW
    c3 = task(3, at(day(1), 17), 400)
    assert cush([a, c3])[3].cushion_minutes == 960 - 1100


def test_negative_cushions_are_marked():
    items = F.cushions([task(1, at(day(0), 17), 600), task(2, at(day(4), 17), 60)], F.FreeTime(free_days()), NOW, TERM.zone)
    assert [x.negative for x in items] == [True, False]


# ---------- overdue ----------
def test_an_overdue_task_is_due_now_and_its_work_still_counts_against_later_deadlines():
    late = task(1, at(day(0), 6), 90)                                              # due 06:00 today, now is 09:00
    r = cush([late, task(2, at(day(1), 17), 200)])
    assert r[1].cushion_minutes == -90 and r[1].free_minutes == 0
    assert r[2].cushion_minutes == 960 - 290


# ---------- start ahead (a task that may only be started later) ----------
def test_a_task_that_starts_later_cannot_use_the_earlier_free_time():
    # A is due on day 4 and may only start on day 4 (start ahead 0); B is due on day 4 too and may start now.
    a = task(1, at(day(4), 17), 400, start_ahead=0)
    b = task(2, at(day(4), 17), 1000)
    r = cush([a, b])
    assert r[1].cushion_minutes == 80 and r[1].window_start == at(day(4))           # day 4 alone: 480 - 400
    assert r[1].free_minutes == 480 and r[1].demand_minutes == 400
    assert r[2].cushion_minutes == 80                                              # the same deadline shares the tightest window
    # without the start limit all of the work spreads over five days: 2400 - 1400
    assert cush([task(1, at(day(4), 17), 400), b])[1].cushion_minutes == 1000


def test_start_ahead_makes_the_start_date_the_window_when_nothing_else_is_due_before():
    t = task(1, at(day(4), 17), 100, start_ahead=1)                                # may start on day 3: two days of free time
    x = cush([t])[1]
    assert x.window_start == at(day(3)) and x.free_minutes == 960 and x.cushion_minutes == 860 and x.demand_minutes == 100


def test_a_start_date_in_the_past_is_the_same_as_starting_now():
    far = task(1, at(day(2), 17), 100, start_ahead=30)
    near = task(1, at(day(2), 17), 100)
    assert cush([far])[1].cushion_minutes == cush([near])[1].cushion_minutes


# ---------- the term and the breaks ----------
def test_free_time_skips_breaks_and_ends_with_the_term():
    first = date(2026, 10, 9)                                                      # Friday; Mon-Tue Oct 12-13 is a break
    now = timeutil.to_utc(first, time(9), NY)
    free = F.free_intervals(CFG, [], [], first, date(2026, 10, 14), now)
    (x,) = F.cushions([task(1, at(date(2026, 10, 14), 17), 100)], free, now, TERM.zone)
    assert x.free_minutes == 480 * 4 and x.cushion_minutes == 480 * 4 - 100          # Fri, Sat, Sun and Wed: the two break days give nothing
    last = TERM.exams_end                                                           # a deadline after the exam period has nothing to add
    now2 = timeutil.to_utc(last, time(9), NY)
    free2 = F.free_intervals(CFG, [], [], last, last + timedelta(days=10), now2)
    (y,) = F.cushions([task(1, at(last + timedelta(days=5), 17), 100)], free2, now2, TERM.zone)
    assert y.free_minutes == 480


# ---------- levels and the timeline ----------
def test_levels():
    assert [F.level_of(m) for m in (-1, 0, 119, 120, 5000)] == [F.RED, F.YELLOW, F.YELLOW, F.GREEN, F.GREEN]
    assert F.level_of(-100000) == F.RED


def test_timeline_has_one_point_per_deadline_day_with_the_tightest_cushion():
    ts = [task(1, at(day(1), 10), 100), task(2, at(day(1), 17), 800), task(3, at(day(3), 12), 50)]
    items = F.cushions(ts, free_days(), NOW, TERM.zone)
    points = F.timeline(items, TERM.zone)
    assert [p.day for p in points] == [day(1), day(3)]
    assert points[0].task_ids == (1, 2) and points[0].cushion_minutes == min(i.cushion_minutes for i in items if i.task_id in (1, 2))
    assert points[1].task_ids == (3,)
    assert F.timeline([], TERM.zone) == ()


def test_timeline_days_are_local_days():
    due = timeutil.to_utc(day(1), time(23, 30), NY)                                  # 03:30 UTC the next day, still Tuesday in New York
    (x,) = F.cushions([task(1, due, 60)], free_days(), NOW, TERM.zone)
    assert F.timeline([x], TERM.zone)[0].day == day(1)


# ---------- the whole report from commitments ----------
def test_report_matches_a_hand_calculation_with_a_class_an_event_and_its_commute():
    wed_end = timeutil.to_utc(day(2), time(23, 59), NY)
    hw = task(1, wed_end, 600)
    cls = c.Series(c.COURSE, 1, "AE 6765", (c.Meeting(1, frozenset({0}), time(9), time(10), "R1"),))                 # Monday 09:00-10:00
    ev = c.timed_event(1, "Advising", day(1), time(12), time(13), NY, commute_before=15, commute_after=15)          # Tuesday 11:45-13:15 busy
    blocks = c.blocks(CFG, [cls], [], [ev], MON, day(2))
    rep = F.report(CFG, [hw], blocks, [], NOW)
    # Mon 10:00-17:00 = 420, Tue 480 - 90 = 390, Wed 480: 1290 free; 600 needed
    assert rep.items[0].free_minutes == 1290 and rep.items[0].cushion_minutes == 690 and not rep.any_negative
    assert rep.of(1).level == F.GREEN and rep.of(99) is None
    assert [p.day for p in rep.timeline] == [day(2)]


def test_report_with_planned_sessions_loses_that_free_time():
    hw = task(1, timeutil.to_utc(day(1), time(17), NY), 300)
    base = F.report(CFG, [hw], [], [], NOW).items[0]
    planned = [(at(MON, 10), at(MON, 12)), (at(day(1), 9), at(day(1), 10))]          # 180 minutes already used
    after = F.report(CFG, [hw], [], planned, NOW).items[0]
    assert base.cushion_minutes - after.cushion_minutes == 180


def test_report_negative_when_the_week_is_full():
    hw = task(1, timeutil.to_utc(day(1), time(17), NY), 300)
    blocks = [c.Block(at(MON, 9), at(MON, 17), "event", "Exam day", True), c.Block(at(day(1), 9), at(day(1), 16), "event", "Trip", True)]
    rep = F.report(CFG, [hw], blocks, [], NOW)
    assert rep.items[0].free_minutes == 60 and rep.items[0].cushion_minutes == -240 and rep.any_negative and rep.negative_items[0].task_id == 1


def test_report_with_no_dated_work_is_empty_and_the_output_is_deterministic():
    assert F.report(CFG, [], [], [], NOW) == F.CushionReport((), (), False)
    assert F.report(CFG, [T.Task(1, "x", None, "Other", None, 60)], [], [], NOW).items == ()
    ts = [task(1, timeutil.to_utc(day(2), time(12), NY), 200), task(2, timeutil.to_utc(day(1), time(12), NY), 100)]
    assert F.report(CFG, ts, [], [], NOW) == F.report(CFG, list(reversed(ts)), [], [], NOW)


def test_report_after_the_term_has_ended_is_negative_not_a_crash():
    now = timeutil.to_utc(date(2026, 12, 30), time(9), NY)
    rep = F.report(CFG, [task(1, timeutil.to_utc(date(2027, 1, 5), time(12), NY), 100)], [], [], now)
    assert rep.items[0].free_minutes == 0 and rep.items[0].cushion_minutes == -100 and rep.any_negative


# ---------- the engine against an independent model: preemptive earliest-deadline-first on a minute grid ----------
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def minute(m):
    return BASE + timedelta(minutes=m)


def edf_feasible(jobs, free_minutes):
    """Run earliest-deadline-first one minute at a time: does every job finish by its deadline? jobs: [(release, deadline, work)] in minutes."""
    left = [w for _, _, w in jobs]
    horizon = max(d for _, d, _ in jobs) + 1
    for m in range(horizon):
        if m in free_minutes:
            ready = [i for i, (r, d, _) in enumerate(jobs) if r <= m and left[i] > 0 and d > m]
            if ready:
                left[min(ready, key=lambda i: jobs[i][1])] -= 1
    return all(left[i] == 0 for i in range(len(jobs)))


def _grid_free(intervals):
    return {m for s, e in intervals for m in range(int((s - BASE).total_seconds() // 60), int((e - BASE).total_seconds() // 60))}


def _random_free(rng):
    starts = sorted(rng.sample(range(0, 280, 5), rng.randrange(2, 12)))
    return F.merge((minute(s), minute(s + rng.randrange(10, 80))) for s in starts)


@pytest.mark.parametrize("seed", range(60))
def test_engine_agrees_with_an_earliest_deadline_first_simulation(seed):
    rng = random.Random(seed)
    free_pieces = _random_free(rng)
    grid = _grid_free(free_pieces)
    jobs = []
    for i in range(rng.randrange(1, 6)):
        deadline = rng.randrange(20, 320)
        release = rng.choice([0, 0, 0, rng.randrange(0, deadline)])                 # most start now, some start later
        jobs.append(F.Job(i, minute(release), minute(deadline), rng.randrange(1, 90)))
    found = F.slacks(jobs, F.FreeTime(free_pieces), minute(0))
    all_ok = all(found[j.id][0] >= 0 for j in jobs)
    sim = [(int((j.release - BASE).total_seconds() // 60), int((j.deadline - BASE).total_seconds() // 60), j.minutes) for j in jobs]
    assert edf_feasible(sim, grid) == all_ok                                       # slack >= 0 everywhere <=> a schedule exists
    for j in jobs:                                                                  # the slack is exact: the window is what the grid says
        slack, capacity, demand, start = found[j.id]
        lo, hi = int((start - BASE).total_seconds() // 60), int((j.deadline - BASE).total_seconds() // 60)
        assert capacity == sum(1 for m in range(lo, hi) if m in grid) and slack == capacity - demand


@pytest.mark.parametrize("seed", range(40))
def test_without_start_dates_the_cushion_is_the_extra_work_that_still_fits(seed):
    rng = random.Random(500 + seed)
    free_pieces = _random_free(rng)
    grid = _grid_free(free_pieces)
    jobs = [F.Job(i, minute(0), minute(rng.randrange(20, 320)), rng.randrange(1, 90)) for i in range(rng.randrange(1, 6))]
    found = F.slacks(jobs, F.FreeTime(free_pieces), minute(0))
    for j in jobs:
        due_by_then = [k for k in jobs if k.deadline <= j.deadline]
        if any(found[k.id][0] < 0 for k in due_by_then):
            continue                                                                # something due earlier is already impossible: not this deadline's cushion
        cushion = found[j.id][0]

        def feasible(extra):
            sim = [(0, int((k.deadline - BASE).total_seconds() // 60), k.minutes + (extra if k.id == j.id else 0)) for k in due_by_then]
            return edf_feasible(sim, grid)

        assert feasible(cushion) and not feasible(cushion + 1)
