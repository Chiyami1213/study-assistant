"""Phase 2: recurring commitments, exceptions and one-off events (pure: no database)."""
from datetime import date, datetime, time, timedelta, timezone

import pytest

from planner import commitments as c
from planner.models import AwakeTimes, Break, PlannerConfig, PlannerError, Term

NY = "America/New_York"
FALL = Term(date(2026, 8, 24), date(2026, 12, 8), date(2026, 12, 18), NY, (Break("Fall Break", date(2026, 10, 12), date(2026, 10, 13)),))
SPRING = Term(date(2026, 1, 12), date(2026, 4, 28), date(2026, 5, 7), NY)
MWF = frozenset({0, 2, 4})


def m(id=1, days=MWF, start=time(9), end=time(9, 50), loc="Room 1", end_date=None):
    return c.Meeting(id, days, start, end, loc, end_date)


def course(meetings=None, owner=1, name="AE 6765"):
    return c.Series(c.COURSE, owner, name, tuple(meetings or [m()]), "#123456")


def activity(meetings=None, owner=1, name="Gym", busy=True, in_breaks=False):
    return c.Series(c.ACTIVITY, owner, name, tuple(meetings or [m(7, frozenset({1, 3}), time(17), time(18), "Gym")]), "", busy, in_breaks)


def days_of(occs):
    return [o.day for o in occs]


# ---------- validation ----------
def test_meeting_needs_weekdays_and_an_end_after_the_start():
    with pytest.raises(PlannerError):
        m(days=frozenset())
    with pytest.raises(PlannerError):
        m(days=frozenset({7}))
    with pytest.raises(PlannerError, match="after it starts"):
        m(start=time(10), end=time(9))
    with pytest.raises(PlannerError):
        m(start=time(10), end=time(10))


def test_series_and_exception_validation():
    with pytest.raises(PlannerError):
        c.Series("club", 1, "x")
    with pytest.raises(PlannerError):
        c.Series(c.COURSE, 1, "  ")
    with pytest.raises(PlannerError):
        c.MeetingException("course", 1, date(2026, 9, 1), "move")
    with pytest.raises(PlannerError, match="start and an end"):
        c.MeetingException("course", 1, date(2026, 9, 1), c.OVERRIDE)
    with pytest.raises(PlannerError, match="after it starts"):
        c.MeetingException("course", 1, date(2026, 9, 1), c.OVERRIDE, time(11), time(10))


# ---------- occurrences ----------
def test_weekly_meeting_lands_on_its_weekdays():
    occs = c.occurrences([course()], [], date(2026, 8, 24), date(2026, 8, 30), FALL)
    assert days_of(occs) == [date(2026, 8, 24), date(2026, 8, 26), date(2026, 8, 28)]       # Mon, Wed, Fri
    assert occs[0].start == time(9) and occs[0].end == time(9, 50) and occs[0].location == "Room 1" and not occs[0].changed


def test_classes_stop_with_the_term_but_activities_run_through_exams():
    gym = activity()
    cls = course()
    assert c.occurrences([cls], [], date(2026, 12, 9), date(2026, 12, 18), FALL) == []                    # classes ended on Dec 8
    assert days_of(c.occurrences([gym], [], date(2026, 12, 9), date(2026, 12, 18), FALL)) == [date(2026, 12, 10), date(2026, 12, 15), date(2026, 12, 17)]
    assert c.occurrences([cls, gym], [], date(2026, 8, 1), date(2026, 8, 23), FALL) == []                   # before the term
    assert c.occurrences([gym], [], date(2026, 12, 19), date(2026, 12, 31), FALL) == []                   # after the exams


def test_breaks_skip_classes_and_activities_unless_the_activity_stays():
    first, last = date(2026, 10, 12), date(2026, 10, 16)
    assert days_of(c.occurrences([course()], [], first, last, FALL)) == [date(2026, 10, 14), date(2026, 10, 16)]      # Mon 12 is in the break; Wed, Fri are not
    work = activity([m(3, frozenset({0, 1}), time(13), time(17), "Work")], name="Work", in_breaks=True)
    assert days_of(c.occurrences([work], [], first, last, FALL)) == [date(2026, 10, 12), date(2026, 10, 13)]
    work2 = activity([m(3, frozenset({0, 1}), time(13), time(17), "Work")], name="Work", in_breaks=False)
    assert c.occurrences([work2], [], first, last, FALL) == []


def test_end_date_cuts_a_meeting_short_and_is_inclusive():
    cls = course([m(end_date=date(2026, 9, 2))])
    assert days_of(c.occurrences([cls], [], date(2026, 8, 24), date(2026, 9, 11), FALL)) == [date(2026, 8, 24), date(2026, 8, 26), date(2026, 8, 28), date(2026, 8, 31), date(2026, 9, 2)]


def test_several_meetings_of_one_series_and_sorting():
    cls = course([m(1, frozenset({0}), time(14), time(15)), m(2, frozenset({0}), time(8), time(9))])
    occs = c.occurrences([cls], [], date(2026, 8, 24), date(2026, 8, 24), FALL)
    assert [o.start for o in occs] == [time(8), time(14)]


def test_skip_removes_only_that_day():
    skip = c.MeetingException(c.COURSE, 1, date(2026, 8, 26), c.SKIP)
    occs = c.occurrences([course()], [skip], date(2026, 8, 24), date(2026, 8, 30), FALL)
    assert days_of(occs) == [date(2026, 8, 24), date(2026, 8, 28)]


def test_override_moves_one_occurrence_and_marks_it():
    ov = c.MeetingException(c.COURSE, 1, date(2026, 8, 26), c.OVERRIDE, time(11), time(12), "Room 9")
    occs = c.occurrences([course()], [ov], date(2026, 8, 24), date(2026, 8, 30), FALL)
    moved = next(o for o in occs if o.day == date(2026, 8, 26))
    assert (moved.start, moved.end, moved.location, moved.changed) == (time(11), time(12), "Room 9", True)
    other = next(o for o in occs if o.day == date(2026, 8, 24))
    assert (other.start, other.location, other.changed) == (time(9), "Room 1", False)
    ov2 = c.MeetingException(c.COURSE, 1, date(2026, 8, 26), c.OVERRIDE, time(11), time(12))               # no new location: keeps the old one
    assert next(o for o in c.occurrences([course()], [ov2], date(2026, 8, 26), date(2026, 8, 26), FALL)).location == "Room 1"


def test_exceptions_do_not_leak_between_owners_or_meetings():
    # a course meeting and an activity meeting can both have the id 1
    skip_activity = c.MeetingException(c.ACTIVITY, 1, date(2026, 8, 25), c.SKIP)
    gym = activity([m(1, frozenset({1}), time(17), time(18))])
    cls = course([m(1, frozenset({1}), time(9), time(10))])
    occs = c.occurrences([cls, gym], [skip_activity], date(2026, 8, 25), date(2026, 8, 25), FALL)
    assert [(o.kind) for o in occs] == [c.COURSE]
    skip_other_meeting = c.MeetingException(c.COURSE, 2, date(2026, 8, 25), c.SKIP)
    assert len(c.occurrences([cls], [skip_other_meeting], date(2026, 8, 25), date(2026, 8, 25), FALL)) == 1


def test_occurrence_interval_follows_daylight_saving():
    cls = course([m(1, frozenset({0, 4}), time(9), time(10))])
    occs = c.occurrences([cls], [], date(2026, 3, 6), date(2026, 3, 9), SPRING)           # Fri Mar 6 (EST) and Mon Mar 9 (EDT)
    friday, monday = (c.occurrence_interval(o, SPRING.zone) for o in occs)
    assert friday[0] == datetime(2026, 3, 6, 14, tzinfo=timezone.utc) and monday[0] == datetime(2026, 3, 9, 13, tzinfo=timezone.utc)
    assert friday[1] - friday[0] == timedelta(hours=1)


# ---------- events ----------
def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def test_event_validation():
    ok = dict(id=1, title="Talk", start=utc(2026, 9, 1, 14), end=utc(2026, 9, 1, 15))
    c.Event(**ok)
    with pytest.raises(PlannerError):
        c.Event(**{**ok, "title": " "})
    with pytest.raises(PlannerError, match="after it starts"):
        c.Event(**{**ok, "end": utc(2026, 9, 1, 14)})
    with pytest.raises(PlannerError, match="UTC"):
        c.Event(**{**ok, "start": datetime(2026, 9, 1, 14)})
    for bad in (-1, 241, 5.5, True):
        with pytest.raises(PlannerError, match="Commute"):
            c.Event(**{**ok, "commute_before": bad})


def test_timed_event_and_commute_make_busy_blocks():
    cfg = PlannerConfig(FALL)
    ev = c.timed_event(5, "Dentist", date(2026, 9, 3), time(10), time(11), NY, commute_before=20, commute_after=30, location="Clinic")
    found = c.blocks(cfg, [], [], [ev], date(2026, 9, 3), date(2026, 9, 3))
    assert [(b.kind, b.label) for b in found] == [("commute", "Travel to Dentist"), ("event", "Dentist"), ("commute", "Travel from Dentist")]
    assert found[0].start == ev.start - timedelta(minutes=20) and found[0].end == ev.start
    assert found[2].end == ev.end + timedelta(minutes=30)
    assert all(b.busy for b in found)
    assert found[1].location == "Clinic"


def test_a_free_event_shows_but_does_not_block_and_has_no_commute_blocks():
    cfg = PlannerConfig(FALL)
    ev = c.timed_event(5, "Optional talk", date(2026, 9, 3), time(10), time(11), NY, commute_before=20, busy=False)
    found = c.blocks(cfg, [], [], [ev], date(2026, 9, 3), date(2026, 9, 3))
    assert [(b.kind, b.busy) for b in found] == [("event", False)]


def test_all_day_event_blocks_the_whole_local_day_even_on_a_clock_change_day():
    cfg = PlannerConfig(SPRING)
    ev = c.all_day_event(9, "Conference", date(2026, 3, 8), date(2026, 3, 9), NY)
    (block,) = c.blocks(cfg, [], [], [ev], date(2026, 3, 8), date(2026, 3, 9))
    assert block.busy and (block.end - block.start) == timedelta(hours=47)                    # 23 + 24
    with pytest.raises(PlannerError):
        c.all_day_event(9, "x", date(2026, 3, 9), date(2026, 3, 8), NY)


def test_event_across_midnight_shows_on_both_days_and_not_outside():
    cfg = PlannerConfig(FALL)
    ev = c.timed_event(3, "Night lab", date(2026, 9, 3), time(22), time(1), NY, end_day=date(2026, 9, 4))
    assert len(c.blocks(cfg, [], [], [ev], date(2026, 9, 3), date(2026, 9, 3))) == 1
    assert len(c.blocks(cfg, [], [], [ev], date(2026, 9, 4), date(2026, 9, 4))) == 1
    assert c.blocks(cfg, [], [], [ev], date(2026, 9, 5), date(2026, 9, 5)) == []
    assert c.blocks(cfg, [], [], [ev], date(2026, 9, 2), date(2026, 9, 2)) == []


def test_an_event_that_ends_exactly_at_the_range_start_is_not_in_it():
    cfg = PlannerConfig(FALL)
    ev = c.timed_event(3, "Late", date(2026, 9, 2), time(20), time(23, 59), NY)
    assert c.blocks(cfg, [], [], [ev], date(2026, 9, 3), date(2026, 9, 3)) == []


def test_a_commute_can_reach_into_the_next_range():
    cfg = PlannerConfig(FALL)
    ev = c.timed_event(3, "Evening class", date(2026, 9, 2), time(22), time(23, 30), NY, commute_after=60)     # the trip home ends after midnight
    assert [b.kind for b in c.blocks(cfg, [], [], [ev], date(2026, 9, 3), date(2026, 9, 3))] == ["commute"]


def test_blocks_combine_classes_activities_and_events_in_time_order():
    cfg = PlannerConfig(FALL)
    gym = activity([m(7, frozenset({1}), time(17), time(18), "Gym")])
    ev = c.timed_event(5, "Advising", date(2026, 8, 25), time(8), time(8, 30), NY)
    found = c.blocks(cfg, [course([m(1, frozenset({1}), time(9), time(10))]), gym], [], [ev], date(2026, 8, 25), date(2026, 8, 25))
    assert [(b.kind, b.label) for b in found] == [("event", "Advising"), ("class", "AE 6765"), ("activity", "Gym")]
    assert found == sorted(found, key=lambda b: b.start)


def test_a_non_busy_activity_stays_non_busy_in_its_blocks():
    cfg = PlannerConfig(FALL)
    found = c.blocks(cfg, [activity(busy=False)], [], [], date(2026, 8, 25), date(2026, 8, 25))
    assert [(b.kind, b.busy) for b in found] == [("activity", False)]


# ---------- the older rows of the events table ----------
def test_legacy_event_with_times_is_timed_and_busy():
    ev = c.legacy_event({"id": 4, "title": "Midterm 1", "date": "2026-10-07", "time": "13:00", "end_time": "14:15", "course_id": 7}, FALL)
    assert ev.busy and not ev.all_day and ev.source == "legacy" and ev.course_id == 7
    assert ev.end - ev.start == timedelta(minutes=75) and ev.start == datetime(2026, 10, 7, 17, tzinfo=timezone.utc)       # 13:00 EDT


def test_legacy_event_without_an_end_gets_two_hours_and_a_bad_end_too():
    a = c.legacy_event({"id": 1, "title": "Final", "date": "2026-12-11", "time": "10:00", "end_time": None, "course_id": None}, FALL)
    b = c.legacy_event({"id": 2, "title": "Final", "date": "2026-12-11", "time": "10:00", "end_time": "09:00", "course_id": None}, FALL)
    assert a.end - a.start == timedelta(hours=2) and b.end - b.start == timedelta(hours=2)


def test_legacy_event_without_a_time_is_an_all_day_marker_that_does_not_block():
    ev = c.legacy_event({"id": 3, "title": "Project due", "date": "2026-11-20", "time": None, "end_time": None, "course_id": None}, FALL)
    assert ev.all_day and not ev.busy
    (block,) = c.blocks(PlannerConfig(FALL), [], [], [ev], date(2026, 11, 20), date(2026, 11, 20))
    assert not block.busy
