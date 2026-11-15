"""Phase 5: study sessions, placement checks and the auto-planner. Pure: no database."""
import random
from datetime import date, datetime, time, timedelta, timezone

import pytest

from planner import commitments as c
from planner import freetime as F
from planner import sessions as S
from planner import tasks as T
from planner import timeutil
from planner.models import AwakeTimes, Break, PlannerConfig, PlannerError, Term

NY = "America/New_York"
TERM = Term(date(2026, 9, 1), date(2026, 12, 8), date(2026, 12, 18), NY, (Break("Fall Break", date(2026, 10, 12), date(2026, 10, 13)),))
CFG = PlannerConfig(TERM, AwakeTimes.uniform(time(9), time(17)), 30)
MON = date(2026, 9, 7)
NOW = timeutil.to_utc(MON, time(9), NY)


def at(day, hh=0, mm=0):
    return timeutil.to_utc(day, time(hh, mm), NY)


def day(n):
    return MON + timedelta(days=n)


def task(id, due, minutes, logged=0, start_ahead=None, state="todo"):
    return T.Task(id, f"T{id}", None, "Homework", due, minutes, start_ahead, state, logged)


def busy(d, h1, m1, h2, m2, label="Class"):
    return c.Block(at(d, h1, m1), at(d, h2, m2), "class", label, True)


def sess(id, task_id, d, h1, m1, h2, m2, source=S.MANUAL):
    return S.Session(id, task_id, at(d, h1, m1), at(d, h2, m2), source)


def plan(tasks, blocks=(), sessions=(), now=NOW, **kw):
    return S.autoplan(CFG, tasks, list(blocks), list(sessions), now, **kw)


def spans(result):
    return [(ch.task_id, timeutil.to_local(ch.start, NY).strftime("%a %H:%M"), ch.minutes) for ch in result.add]


# ---------- the Session model ----------
def test_session_validation_and_minutes():
    s = sess(1, 5, MON, 9, 0, 10, 30)
    assert s.minutes == 90 and s.source == S.MANUAL
    assert s.overlaps(at(MON, 10), at(MON, 11)) and not s.overlaps(at(MON, 10, 30), at(MON, 11))
    with pytest.raises(PlannerError):
        S.Session(1, 5, at(MON, 10), at(MON, 10))
    with pytest.raises(PlannerError):
        S.Session(1, 5, datetime(2026, 9, 7, 10), datetime(2026, 9, 7, 11))
    with pytest.raises(PlannerError):
        S.Session(1, 5, at(MON, 9), at(MON, 10), "robot")


# ---------- placement problems ----------
def problems(start, end, blocks=(), others=()):
    return [(p.kind, p.hard) for p in S.placement_problems(CFG, start, end, list(blocks), list(others))]


def test_a_session_inside_free_time_has_no_problems():
    assert problems(at(MON, 10), at(MON, 11)) == []


def test_each_kind_of_problem():
    assert problems(at(MON, 11), at(MON, 10)) == [("time", True)]
    assert problems(at(date(2026, 8, 20), 10), at(date(2026, 8, 20), 11)) == [("term", True)]
    assert problems(at(date(2026, 10, 12), 10), at(date(2026, 10, 12), 11)) == [("break", True)]
    assert problems(at(MON, 10), at(MON, 11), others=[sess(9, 1, MON, 10, 30, 11, 30)]) == [("session", True)]
    assert problems(at(MON, 7), at(MON, 8)) == [("awake", False)]
    assert problems(at(MON, 16, 30), at(MON, 17, 30)) == [("awake", False)]
    assert problems(at(MON, 10), at(MON, 11), blocks=[busy(MON, 10, 30, 12, 0, "AE 6765")]) == [("busy", False)]
    assert problems(at(MON, 10), at(MON, 10, 20)) == [("short", False)]


def test_a_session_across_midnight_and_a_free_block_and_session_edges():
    assert ("awake", False) in problems(at(MON, 16), at(day(1), 10))
    assert problems(at(MON, 10), at(MON, 11), blocks=[c.Block(at(MON, 10), at(MON, 11), "event", "Optional", False)]) == []        # not busy
    assert problems(at(MON, 10), at(MON, 11), others=[sess(9, 1, MON, 11, 0, 12, 0)]) == []                                       # touching is not overlapping
    assert problems(at(MON, 10), at(MON, 11), blocks=[busy(MON, 11, 0, 12, 0)]) == []


def test_hard_problems_come_first():
    kinds = [(p.kind, p.hard) for p in S.placement_problems(CFG, at(MON, 8), at(MON, 8, 20), [busy(MON, 8, 0, 9, 0)], [sess(9, 1, MON, 8, 10, 8, 30)])]
    assert kinds[0] == ("session", True) and {k for k, _ in kinds} == {"session", "awake", "busy", "short"}


# ---------- one task ----------
def test_a_task_goes_into_the_earliest_free_time():
    r = plan([task(1, at(day(1), 17), 120)])
    assert spans(r) == [(1, "Mon 09:00", 120)] and r.complete and r.remove == () and r.late == ()


def test_a_task_is_split_around_a_class_and_every_piece_keeps_the_minimum():
    r = plan([task(1, at(day(1), 17), 90)], [busy(MON, 10, 0, 11, 0)])
    assert spans(r) == [(1, "Mon 09:00", 60), (1, "Mon 11:00", 30)]


def test_the_rest_of_a_split_task_is_never_shorter_than_the_minimum():
    # free pieces: 09:00-09:45 (45) and 11:00-17:00; the task needs 70: using all 45 would leave 25 (< 30), so only 40 go into the first piece
    r = plan([task(1, at(day(1), 17), 70)], [busy(MON, 9, 45, 11, 0)])
    assert spans(r) == [(1, "Mon 09:00", 40), (1, "Mon 11:00", 30)]


def test_a_task_that_cannot_be_split_into_two_proper_sessions_waits_for_a_big_enough_piece():
    # needs 50 (< 2 x 30): the 40-minute piece is skipped, the whole task goes into the next piece
    r = plan([task(1, at(day(1), 17), 50)], [busy(MON, 9, 40, 11, 0)])
    assert spans(r) == [(1, "Mon 11:00", 50)]


def test_a_task_shorter_than_the_minimum_gets_one_short_session():
    assert spans(plan([task(1, at(day(1), 17), 20)])) == [(1, "Mon 09:00", 20)]


def test_what_does_not_fit_is_reported_and_nothing_goes_past_the_deadline():
    r = plan([task(1, at(MON, 12), 300)])                                              # due Monday noon: 180 minutes of room
    assert spans(r) == [(1, "Mon 09:00", 180)] and r.unplaced == ((1, 120),) and not r.complete and r.unplaced_of(1) == 120 and r.unplaced_of(9) == 0


def test_a_task_logged_past_its_estimate_or_done_needs_nothing():
    assert plan([task(1, at(day(1), 17), 60, logged=60), task(2, at(day(1), 17), 60, state="done")]).add == ()


# ---------- earliest deadline first ----------
def test_the_earlier_deadline_gets_the_earlier_time_whatever_the_input_order():
    a, b = task(1, at(MON, 12), 120), task(2, at(day(4), 17), 120)
    r1, r2 = plan([a, b]), plan([b, a])
    assert spans(r1) == [(1, "Mon 09:00", 120), (2, "Mon 11:00", 120)] and r1 == r2


def test_tasks_due_at_the_same_moment_are_planned_by_id():
    r = plan([task(2, at(day(2), 17), 60), task(1, at(day(2), 17), 60)])
    assert spans(r) == [(1, "Mon 09:00", 60), (2, "Mon 10:00", 60)]


def test_start_ahead_keeps_a_task_out_of_the_earlier_days():
    r = plan([task(1, at(day(2), 17), 90, start_ahead=1)])                             # due Wednesday; may start on Tuesday
    assert spans(r) == [(1, "Tue 09:00", 90)]


def test_undated_tasks_are_left_alone_unless_asked_for_and_then_come_last():
    undated = T.Task(9, "Someday", None, "Other", None, 60)
    dated = task(1, at(day(1), 17), 60)
    assert spans(plan([undated, dated])) == [(1, "Mon 09:00", 60)]
    assert spans(plan([undated, dated], include_undated=True)) == [(1, "Mon 09:00", 60), (9, "Mon 10:00", 60)]


# ---------- what is kept and what is replaced ----------
def test_manual_sessions_stay_and_count_as_planned_work_and_busy_time():
    manual = sess(5, 1, MON, 9, 0, 10, 0)                                              # one hour is already set aside for task 1
    r = plan([task(1, at(day(1), 17), 120), task(2, at(day(1), 17), 60)], sessions=[manual])
    assert spans(r) == [(1, "Mon 10:00", 60), (2, "Mon 11:00", 60)] and r.remove == ()


def test_future_automatic_sessions_are_replaced_but_started_and_past_ones_stay():
    future = sess(1, 1, day(1), 9, 0, 10, 0, S.AUTO)
    running = S.Session(2, 1, at(MON, 8, 30), at(MON, 9, 30), S.AUTO)                  # began before now
    past = sess(3, 1, date(2026, 9, 4), 9, 0, 10, 0, S.AUTO)
    r = plan([task(1, at(day(2), 17), 120)], sessions=[future, running, past])
    assert r.remove == (1,)
    assert spans(r) == [(1, "Mon 09:30", 90)]                          # 120 needed - the 30 minutes of the running session that lie after now (09:00-09:30)


def test_overdue_work_is_placed_as_soon_as_possible_and_reported_late():
    r = plan([task(1, at(date(2026, 9, 4), 17), 90), task(2, at(day(1), 17), 60)])
    assert r.late == (1,) and spans(r) == [(1, "Mon 09:00", 90), (2, "Mon 10:30", 60)]


def test_breaks_and_the_term_end_are_respected():
    now = timeutil.to_utc(date(2026, 10, 9), time(9), NY)                                # Friday before the break
    r = S.autoplan(CFG, [task(1, at(date(2026, 10, 14), 17), 1800)], [], [], now)          # 30 hours: Fri, Sat, Sun, Wed = 32 hours of room
    days = {timeutil.to_local(ch.start, NY).date() for ch in r.add}
    assert date(2026, 10, 12) not in days and date(2026, 10, 13) not in days and r.complete
    assert max(days) == date(2026, 10, 14)


# ---------- the plan and the cushion agree ----------
def test_planning_a_task_does_not_change_its_own_cushion():
    t = task(1, at(day(1), 17), 200)
    before = F.report(CFG, [t], [], [], NOW).items[0]
    r = plan([t])
    sessions = [S.Session(i + 1, ch.task_id, ch.start, ch.end, S.AUTO) for i, ch in enumerate(r.add)]
    after = F.report(CFG, [t], [], sessions, NOW).items[0]
    assert after.cushion_minutes == before.cushion_minutes == 960 - 200
    assert after.demand_minutes == 0 and after.free_minutes == 960 - 200


# ---------- invariants on random weeks ----------
@pytest.mark.parametrize("seed", range(60))
def test_random_plans_keep_every_promise(seed):
    rng = random.Random(seed)
    blocks = []
    for _ in range(rng.randrange(0, 8)):
        d = day(rng.randrange(0, 7))
        h = rng.randrange(8, 17)
        blocks.append(busy(d, h, rng.choice([0, 15, 30, 45]), min(h + rng.randrange(1, 4), 18), 0))
    manual = [sess(100 + i, 1, day(rng.randrange(0, 6)), 11 + i, 0, 12 + i, 0) for i in range(rng.randrange(0, 2))]
    tasks = [task(i + 1, at(day(rng.randrange(0, 7)), rng.randrange(9, 22), rng.choice([0, 30])), rng.choice([20, 30, 45, 60, 100, 150, 240]),
                  start_ahead=rng.choice([None, None, 0, 1, 3])) for i in range(rng.randrange(1, 7))]
    r = plan(tasks, blocks, manual)
    assert r == plan(list(reversed(tasks)), list(reversed(blocks)), list(reversed(manual)))                      # deterministic
    by_task = {}
    for ch in r.add:
        by_task.setdefault(ch.task_id, []).append(ch)
    kept_or_busy = [(b.start, b.end) for b in blocks] + [(s.start, s.end) for s in manual]
    free = F.FreeTime(F.free_intervals(CFG, blocks, manual, MON, day(8), NOW))
    spans_sorted = sorted((ch.start, ch.end) for ch in r.add)
    assert all(a[1] <= b[0] for a, b in zip(spans_sorted, spans_sorted[1:]))                                     # no two sessions overlap
    for ch in r.add:
        assert ch.end > ch.start and ch.start >= NOW
        assert F.FreeTime([(ch.start, ch.end)]).minutes_between(ch.start, ch.end) == ch.minutes
        assert free.minutes_between(ch.start, ch.end) == ch.minutes                                                # entirely free time: awake, not busy, not kept
        assert not any(s < ch.end and ch.start < e for s, e in kept_or_busy)
    for t in tasks:
        need = max(0, t.remaining_minutes - F.planned_minutes(manual, t.id, F._release(t, NOW, TERM.zone), max(t.due, NOW)))
        placed = sum(ch.minutes for ch in by_task.get(t.id, []))
        assert placed + r.unplaced_of(t.id) == need                                                                # everything is placed or reported
        mine = by_task.get(t.id, [])
        if not t.is_overdue(NOW):
            assert all(ch.end <= t.due for ch in mine)                                                             # never after the deadline
            assert all(ch.start >= F._release(t, NOW, TERM.zone) for ch in mine)                                   # never before the start date
        if need >= CFG.min_block_minutes:
            assert all(ch.minutes >= CFG.min_block_minutes for ch in mine)                                         # the minimum block
        else:
            assert all(ch.minutes == need for ch in mine)                                                          # a short task: one short session
