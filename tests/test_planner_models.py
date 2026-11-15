"""Phase 1: the planner's setup models and time helpers (pure: no database)."""
from datetime import date, datetime, time, timezone

import pytest

from planner import timeutil
from planner.models import (AwakeTimes, Break, DayWindow, PlannerConfig, PlannerError, Term, DEFAULT_MIN_BLOCK, MIN_BLOCK_RANGE)

NY = "America/New_York"


def term(**kw):
    base = dict(start=date(2026, 8, 24), classes_end=date(2026, 12, 8), exams_end=date(2026, 12, 18), tz=NY)
    base.update(kw)
    return Term(**base)


# ---------- breaks ----------
def test_break_includes_both_ends_and_counts_days():
    b = Break("Fall Break", date(2026, 10, 12), date(2026, 10, 13))
    assert b.contains(date(2026, 10, 12)) and b.contains(date(2026, 10, 13))
    assert not b.contains(date(2026, 10, 11)) and not b.contains(date(2026, 10, 14))
    assert b.days == 2


def test_break_one_day_is_allowed():
    assert Break("Holiday", date(2026, 11, 26), date(2026, 11, 26)).days == 1


def test_break_must_have_a_name_and_ordered_dates():
    with pytest.raises(PlannerError):
        Break("  ", date(2026, 1, 1), date(2026, 1, 2))
    with pytest.raises(PlannerError, match="ends"):
        Break("Bad", date(2026, 1, 5), date(2026, 1, 4))


# ---------- awake window ----------
def test_day_window_minutes_and_order():
    assert DayWindow(time(8), time(23)).minutes == 900
    assert DayWindow(time(6, 30), time(7, 0)).minutes == 30
    with pytest.raises(PlannerError, match="later"):
        DayWindow(time(23), time(8))
    with pytest.raises(PlannerError):
        DayWindow(time(8), time(8))


def test_awake_times_default_uniform_and_per_day_change():
    a = AwakeTimes()
    assert all(w == DayWindow(time(8), time(23)) for w in a.windows)
    b = a.with_day(5, DayWindow(time(10), time(22)))                    # Saturday
    assert b.for_weekday(5) == DayWindow(time(10), time(22))
    assert b.for_weekday(4) == DayWindow(time(8), time(23))
    assert a.for_weekday(5) == DayWindow(time(8), time(23))              # the original is untouched
    assert b.for_date(date(2026, 11, 14)) == DayWindow(time(10), time(22))   # 2026-11-14 is a Saturday


def test_awake_times_need_seven_valid_days():
    with pytest.raises(PlannerError):
        AwakeTimes((DayWindow(),) * 6)
    with pytest.raises(PlannerError):
        AwakeTimes().with_day(7, DayWindow())


# ---------- term ----------
def test_term_dates_must_be_in_order():
    term()
    with pytest.raises(PlannerError, match="classes"):
        term(classes_end=date(2026, 8, 1))
    with pytest.raises(PlannerError, match="exams"):
        term(exams_end=date(2026, 12, 1))
    term(classes_end=date(2026, 8, 24), exams_end=date(2026, 8, 24))     # a one-day term is fine


def test_term_rejects_an_unknown_time_zone():
    with pytest.raises(PlannerError, match="Unknown time zone"):
        term(tz="Mars/Olympus")
    assert term(tz="UTC").zone is not None


def test_term_planning_days_skip_breaks_and_stay_inside_the_term():
    t = term(breaks=(Break("Fall Break", date(2026, 10, 12), date(2026, 10, 13)),))
    assert t.in_term(date(2026, 8, 24)) and t.in_term(date(2026, 12, 18))
    assert not t.in_term(date(2026, 8, 23)) and not t.in_term(date(2026, 12, 19))
    assert t.is_planning_day(date(2026, 10, 11)) and not t.is_planning_day(date(2026, 10, 12))
    assert t.break_on(date(2026, 10, 13)).name == "Fall Break"
    days = t.planning_days(date(2026, 10, 10), date(2026, 10, 15))
    assert days == [date(2026, 10, 10), date(2026, 10, 11), date(2026, 10, 14), date(2026, 10, 15)]
    assert t.planning_days(date(2026, 8, 20), date(2026, 8, 25)) == [date(2026, 8, 24), date(2026, 8, 25)]    # cut at the first day
    assert t.planning_days(date(2027, 1, 1), date(2027, 1, 5)) == []


def test_overlapping_breaks_are_both_fine():
    t = term(breaks=(Break("A", date(2026, 10, 1), date(2026, 10, 5)), Break("B", date(2026, 10, 4), date(2026, 10, 8))))
    assert t.break_on(date(2026, 10, 4)).name == "A"
    assert not t.is_planning_day(date(2026, 10, 8))


# ---------- config ----------
def test_config_min_block_defaults_and_limits():
    assert PlannerConfig(term()).min_block_minutes == DEFAULT_MIN_BLOCK == 30
    lo, hi = MIN_BLOCK_RANGE
    PlannerConfig(term(), min_block_minutes=lo)
    PlannerConfig(term(), min_block_minutes=hi)
    for bad in (lo - 1, hi + 1, 0, -5, 30.5, True, "30"):
        with pytest.raises(PlannerError):
            PlannerConfig(term(), min_block_minutes=bad)


def test_awake_interval_is_utc_and_respects_daylight_saving():
    cfg = PlannerConfig(term(start=date(2026, 3, 1), classes_end=date(2026, 4, 30), exams_end=date(2026, 5, 10)))
    # a winter day (EST, UTC-5): 08:00-23:00 local = 13:00-04:00 UTC next day
    s, e = cfg.awake_interval(date(2026, 3, 6))
    assert (s, e) == (datetime(2026, 3, 6, 13, tzinfo=timezone.utc), datetime(2026, 3, 7, 4, tzinfo=timezone.utc))
    # the day the clocks go forward (2026-03-08, EDT from 03:00): 08:00 EDT = 12:00 UTC, 23:00 EDT = 03:00 UTC next day
    s, e = cfg.awake_interval(date(2026, 3, 8))
    assert (s, e) == (datetime(2026, 3, 8, 12, tzinfo=timezone.utc), datetime(2026, 3, 9, 3, tzinfo=timezone.utc))
    assert cfg.awake_minutes(date(2026, 3, 8)) == 900                    # a wall-clock window is the same length (waking after the change)


def test_awake_interval_on_the_fall_back_day():
    cfg = PlannerConfig(term(start=date(2026, 10, 1), classes_end=date(2026, 11, 30), exams_end=date(2026, 12, 20)))
    s, e = cfg.awake_interval(date(2026, 11, 1))                         # clocks went back at 02:00: 08:00 EST = 13:00 UTC
    assert s == datetime(2026, 11, 1, 13, tzinfo=timezone.utc) and e == datetime(2026, 11, 2, 4, tzinfo=timezone.utc)


def test_awake_interval_none_in_a_break_or_outside_the_term():
    cfg = PlannerConfig(term(breaks=(Break("Break", date(2026, 10, 12), date(2026, 10, 13)),)))
    assert cfg.awake_interval(date(2026, 10, 12)) is None and cfg.awake_minutes(date(2026, 10, 12)) == 0
    assert cfg.awake_interval(date(2026, 8, 1)) is None
    assert cfg.awake_interval(date(2026, 10, 14)) is not None


def test_weekday_specific_window_is_used():
    cfg = PlannerConfig(term(), AwakeTimes().with_day(6, DayWindow(time(9), time(21))))   # Sunday
    assert cfg.awake_minutes(date(2026, 11, 15)) == 12 * 60               # 2026-11-15 is a Sunday
    assert cfg.awake_minutes(date(2026, 11, 16)) == 15 * 60


# ---------- time helpers ----------
def test_utc_text_round_trip_and_zone_conversion():
    moment = datetime(2026, 11, 16, 14, 30, 5, 999, tzinfo=timezone.utc)
    text = timeutil.utc_iso(moment)
    assert text == "2026-11-16T14:30:05Z"
    assert timeutil.parse_utc(text) == moment.replace(microsecond=0)
    assert timeutil.to_local(moment, NY).hour == 9                        # EST
    assert timeutil.local_day(datetime(2026, 11, 17, 2, 0, tzinfo=timezone.utc), NY) == date(2026, 11, 16)   # late evening there
    with pytest.raises(ValueError):
        timeutil.utc_iso(datetime(2026, 1, 1))


def test_day_length_is_23_or_25_hours_on_a_change_day():
    assert timeutil.minutes_between(*timeutil.day_bounds_utc(date(2026, 3, 8), NY)) == 23 * 60
    assert timeutil.minutes_between(*timeutil.day_bounds_utc(date(2026, 11, 1), NY)) == 25 * 60
    assert timeutil.minutes_between(*timeutil.day_bounds_utc(date(2026, 6, 1), NY)) == 24 * 60


def test_hhmm_parsing():
    assert timeutil.parse_hhmm("08:05") == time(8, 5) and timeutil.fmt_hhmm(time(8, 5)) == "08:05"
    for bad in ("8", "25:00", "ab:cd", None):
        with pytest.raises(ValueError):
            timeutil.parse_hhmm(bad)
