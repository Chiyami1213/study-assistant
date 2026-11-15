"""Phase 4: free intervals (the free-time engine). Pure: no database."""
import random
from datetime import date, datetime, time, timedelta, timezone

import pytest

from planner import commitments as c
from planner import freetime as F
from planner.models import AwakeTimes, Break, DayWindow, PlannerConfig, Term

NY = "America/New_York"
TERM = Term(date(2026, 9, 1), date(2026, 12, 8), date(2026, 12, 18), NY, (Break("Break", date(2026, 10, 12), date(2026, 10, 13)),))
CFG = PlannerConfig(TERM, AwakeTimes.uniform(time(9), time(17)), 30)          # awake 09:00-17:00 local, blocks of at least 30 minutes
MON = date(2026, 9, 7)                                                        # a Monday in EDT (UTC-4)


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def local(day, hh, mm=0, cfg=CFG):
    from planner import timeutil
    return timeutil.to_utc(day, time(hh, mm), cfg.term.zone)


def blk(day, h1, m1, h2, m2, busy=True, kind="class", cfg=CFG):
    return c.Block(local(day, h1, m1, cfg), local(day, h2, m2, cfg), kind, "x", busy)


def span(day, h1, m1, h2, m2, cfg=CFG):
    return (local(day, h1, m1, cfg), local(day, h2, m2, cfg))


def free(blocks, planned=(), first=MON, last=MON, now=None, cfg=CFG):
    return F.free_intervals(cfg, blocks, planned, first, last, now)


# ---------- awake time as the base ----------
def test_with_nothing_busy_the_free_time_is_the_awake_window_of_each_day():
    f = free([], first=MON, last=MON + timedelta(days=2))
    assert f == [span(MON + timedelta(days=i), 9, 0, 17, 0) for i in range(3)]
    assert F.total_minutes(f) == 3 * 480


def test_a_class_splits_the_day():
    assert free([blk(MON, 10, 0, 11, 0)]) == [span(MON, 9, 0, 10, 0), span(MON, 11, 0, 17, 0)]


def test_a_busy_block_at_the_edges_shortens_the_window():
    assert free([blk(MON, 8, 0, 9, 30), blk(MON, 16, 0, 18, 0)]) == [span(MON, 9, 30, 16, 0)]


def test_blocks_covering_the_whole_awake_time_leave_nothing():
    assert free([blk(MON, 8, 0, 18, 0)]) == []


# ---------- overlapping and nested blocks ----------
def test_overlapping_and_nested_busy_blocks_are_merged():
    blocks = [blk(MON, 10, 0, 12, 0), blk(MON, 11, 0, 13, 0), blk(MON, 10, 30, 11, 0), blk(MON, 15, 0, 15, 30)]
    assert free(blocks) == [span(MON, 9, 0, 10, 0), span(MON, 13, 0, 15, 0), span(MON, 15, 30, 17, 0)]


def test_touching_busy_blocks_leave_no_sliver():
    assert free([blk(MON, 10, 0, 11, 0), blk(MON, 11, 0, 12, 0)]) == [span(MON, 9, 0, 10, 0), span(MON, 12, 0, 17, 0)]


def test_a_free_busy_false_block_does_not_take_time():
    assert free([blk(MON, 10, 0, 12, 0, busy=False)]) == [span(MON, 9, 0, 17, 0)]


# ---------- commute ----------
def test_commute_after_an_event_pushes_busy_time_past_the_awake_window_without_adding_free_time():
    ev = c.timed_event(1, "Late talk", MON, time(16, 0), time(18, 0), NY, commute_after=90)          # ends after the awake time ends
    blocks = c.blocks(CFG, [], [], [ev], MON, MON)
    assert free(blocks) == [span(MON, 9, 0, 16, 0)]
    assert free(blocks, last=MON + timedelta(days=1))[-1] == span(MON + timedelta(days=1), 9, 0, 17, 0)      # nothing spills into the next morning


def test_commute_before_an_early_event_removes_the_start_of_the_awake_time():
    ev = c.timed_event(1, "Early lab", MON, time(8, 30), time(10, 0), NY, commute_before=45, commute_after=15)
    assert free(c.blocks(CFG, [], [], [ev], MON, MON)) == [span(MON, 10, 15, 17, 0)]


def test_commute_overnight_event_reaches_into_the_next_morning():
    ev = c.timed_event(1, "Night shift", MON, time(23, 0), time(2, 0), NY, end_day=MON + timedelta(days=1), commute_after=120)   # busy until 04:00
    nxt = MON + timedelta(days=1)
    assert free(c.blocks(CFG, [], [], [ev], MON, nxt), first=MON, last=nxt) == [span(MON, 9, 0, 17, 0), span(nxt, 9, 0, 17, 0)]
    long_shift = c.timed_event(2, "Long shift", MON, time(23, 0), time(8, 0), NY, end_day=MON + timedelta(days=1), commute_after=120)   # busy until 10:00
    assert free(c.blocks(CFG, [], [], [long_shift], MON, nxt), first=MON, last=nxt) == [span(MON, 9, 0, 17, 0), span(nxt, 10, 0, 17, 0)]


def test_an_all_day_busy_event_takes_the_whole_day_and_a_free_one_does_not():
    day = c.all_day_event(1, "Conference", MON, MON, NY)
    assert free(c.blocks(CFG, [], [], [day], MON, MON)) == []
    optional = c.all_day_event(2, "Optional", MON, MON, NY, busy=False)
    assert free(c.blocks(CFG, [], [], [optional], MON, MON)) == [span(MON, 9, 0, 17, 0)]


# ---------- breaks and the term ----------
def test_no_free_time_in_a_break_or_outside_the_term():
    brk = date(2026, 10, 12)
    assert free([], first=brk, last=brk + timedelta(days=1)) == []
    assert free([], first=date(2026, 8, 20), last=date(2026, 8, 31)) == []
    assert free([], first=date(2026, 12, 19), last=date(2026, 12, 30)) == []
    assert free([], first=date(2026, 10, 11), last=date(2026, 10, 14)) == [span(date(2026, 10, 11), 9, 0, 17, 0), span(date(2026, 10, 14), 9, 0, 17, 0)]


# ---------- planned sessions ----------
def test_planned_sessions_are_taken_out_as_pairs_or_objects():
    class Session:
        def __init__(self, s, e):
            self.start, self.end = s, e
    planned = [span(MON, 10, 0, 11, 0), Session(*span(MON, 13, 0, 14, 0))]
    assert free([], planned) == [span(MON, 9, 0, 10, 0), span(MON, 11, 0, 13, 0), span(MON, 14, 0, 17, 0)]


# ---------- minimum block ----------
def test_pieces_shorter_than_the_minimum_block_are_dropped_and_the_minimum_is_kept():
    blocks = [blk(MON, 9, 25, 12, 0), blk(MON, 12, 30, 16, 30)]                    # gaps: 09:00-09:25 (25), 12:00-12:30 (30), 16:30-17:00 (30)
    assert free(blocks) == [span(MON, 12, 0, 12, 30), span(MON, 16, 30, 17, 0)]
    assert free([blk(MON, 9, 26, 17, 0)]) == []                                   # 26 minutes left: below 30


def test_a_different_minimum_block_changes_what_is_kept():
    cfg = PlannerConfig(TERM, AwakeTimes.uniform(time(9), time(17)), 60)
    assert free([blk(MON, 9, 45, 16, 30, cfg=cfg)], cfg=cfg) == []                 # 45 and 30 minutes are both below 60
    cfg15 = PlannerConfig(TERM, AwakeTimes.uniform(time(9), time(17)), 15)
    assert free([blk(MON, 9, 20, 16, 40, cfg=cfg15)], cfg=cfg15) == [span(MON, 9, 0, 9, 20, cfg15), span(MON, 16, 40, 17, 0, cfg15)]


# ---------- now ----------
def test_nothing_before_now_and_a_cut_piece_must_still_reach_the_minimum():
    assert free([], now=local(MON, 13, 0)) == [span(MON, 13, 0, 17, 0)]
    assert free([], now=local(MON, 16, 45)) == []                                  # 15 minutes left today
    assert free([], now=local(MON, 17, 30)) == []
    assert free([], now=local(MON, 6, 0)) == [span(MON, 9, 0, 17, 0)]


# ---------- daylight saving ----------
def test_awake_time_on_the_days_the_clocks_change_is_still_a_full_window():
    spring, fall = date(2026, 3, 8), date(2026, 11, 1)
    cfg = PlannerConfig(Term(date(2026, 1, 12), date(2026, 4, 28), date(2026, 12, 18), NY), AwakeTimes.uniform(time(9), time(17)), 30)
    assert F.total_minutes(free([], first=spring, last=spring, cfg=cfg)) == 480
    assert F.total_minutes(free([], first=fall, last=fall, cfg=cfg)) == 480
    assert free([], first=fall, last=fall, cfg=cfg)[0][0] == utc(2026, 11, 1, 14)    # 09:00 EST is 14:00 UTC


# ---------- the interval helpers, against a brute-force model ----------
def _grid(intervals):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {m for s, e in intervals for m in range(int((s - base).total_seconds() // 60), int((e - base).total_seconds() // 60))}


def _random_intervals(rng, n):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = []
    for _ in range(n):
        s = rng.randrange(0, 400)
        out.append((base + timedelta(minutes=s), base + timedelta(minutes=s + rng.randrange(0, 90))))
    return out


@pytest.mark.parametrize("seed", range(40))
def test_merge_and_subtract_match_a_minute_by_minute_model(seed):
    rng = random.Random(seed)
    a, b = _random_intervals(rng, rng.randrange(0, 8)), _random_intervals(rng, rng.randrange(0, 8))
    merged = F.merge(a)
    assert _grid(merged) == _grid(a)
    assert all(merged[i][1] < merged[i + 1][0] for i in range(len(merged) - 1))     # sorted, separate
    diff = F.subtract(a, b)
    assert _grid(diff) == _grid(a) - _grid(b)
    assert F.total_minutes(diff) == len(_grid(a) - _grid(b))
    assert all(diff[i][1] <= diff[i + 1][0] for i in range(len(diff) - 1))


@pytest.mark.parametrize("seed", range(25))
def test_free_minutes_between_matches_a_minute_by_minute_model(seed):
    rng = random.Random(1000 + seed)
    pieces = F.merge(_random_intervals(rng, rng.randrange(1, 8)))
    ft = F.FreeTime(pieces)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    grid = _grid(pieces)
    for _ in range(20):
        lo, hi = sorted(rng.randrange(-20, 520) for _ in range(2))
        expected = sum(1 for m in range(lo, hi) if m in grid)
        assert ft.minutes_between(base + timedelta(minutes=lo), base + timedelta(minutes=hi)) == expected


def test_subtract_edge_cases():
    base = utc(2026, 1, 1, 9)
    hour = timedelta(hours=1)
    assert F.subtract([], [(base, base + hour)]) == []
    assert F.subtract([(base, base + hour)], []) == [(base, base + hour)]
    assert F.subtract([(base, base + hour)], [(base - hour, base + 2 * hour)]) == []
    assert F.subtract([(base, base + 3 * hour)], [(base + hour, base + 2 * hour)]) == [(base, base + hour), (base + 2 * hour, base + 3 * hour)]
    assert F.merge([(base, base)]) == []                                             # an empty interval is nothing
