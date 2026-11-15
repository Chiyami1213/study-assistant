"""Phase 2: activities, weekly meetings, exceptions and events are saved, validated and read back (a temporary database)."""
import sqlite3
from datetime import date, datetime, time, timedelta, timezone

import pytest

import crud
import database
from planner import commit_store as cs
from planner import store, timeutil
from planner.commitments import ACTIVITY, COURSE
from planner.models import PlannerError

pytestmark = pytest.mark.usefixtures("fresh_data")
NY = "America/New_York"


@pytest.fixture
def term():
    store.set_timezone(NY)
    store.set_term_dates(date(2026, 8, 24), date(2026, 12, 8), date(2026, 12, 18))
    store.add_break("Fall Break", date(2026, 10, 12), date(2026, 10, 13))


def make_course(code="AE 6765", status="Active"):
    return crud.add_course(code, "Kinetics", "Fall 2026", 0, status)


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


# ---------- activities and their meetings ----------
def test_activity_and_meeting_round_trip(term):
    gym = cs.add_activity("Gym", "#ff0000", "Rec center", busy=True, in_breaks=False)
    mid = cs.add_activity_meeting(gym, {1, 3}, time(17), time(18), "", date(2026, 11, 30))
    (series,) = [s for s in cs.load_series() if s.kind == ACTIVITY]
    assert (series.name, series.color, series.busy, series.in_breaks) == ("Gym", "#ff0000", True, False)
    (meeting,) = series.meetings
    assert meeting.id == mid and meeting.days == frozenset({1, 3}) and (meeting.start, meeting.end) == (time(17), time(18))
    assert meeting.location == "Rec center" and meeting.end_date == date(2026, 11, 30)      # the activity's place when the meeting has none


def test_invalid_activities_and_meetings_are_refused_without_saving(term):
    with pytest.raises(PlannerError):
        cs.add_activity("   ")
    gym = cs.add_activity("Gym")
    for bad in (dict(days=set(), start=time(9), end=time(10)), dict(days={7}, start=time(9), end=time(10)), dict(days={1}, start=time(10), end=time(9))):
        with pytest.raises(PlannerError):
            cs.add_activity_meeting(gym, **bad)
    with pytest.raises(PlannerError, match="does not exist"):
        cs.add_activity_meeting(999, {1}, time(9), time(10))
    assert database.get_conn().execute("SELECT COUNT(*) FROM activity_meetings").fetchone()[0] == 0


def test_update_the_whole_series_keeps_the_exceptions(term):
    gym = cs.add_activity("Gym")
    mid = cs.add_activity_meeting(gym, {1}, time(17), time(18))
    cs.skip_occurrence(ACTIVITY, mid, date(2026, 9, 1))                      # a Tuesday
    cs.update_meeting(ACTIVITY, mid, {1, 3}, time(6), time(7), "Pool", None)
    (series,) = [s for s in cs.load_series() if s.kind == ACTIVITY]
    assert series.meetings[0].days == frozenset({1, 3}) and series.meetings[0].start == time(6) and series.meetings[0].location == "Pool"
    assert len(cs.list_exceptions(ACTIVITY)) == 1
    with pytest.raises(PlannerError):
        cs.update_meeting(ACTIVITY, mid, {1}, time(8), time(7))
    with pytest.raises(PlannerError, match="does not exist"):
        cs.update_meeting(ACTIVITY, 999, {1}, time(8), time(9))


def test_deleting_a_meeting_or_an_activity_removes_its_exceptions(term):
    gym = cs.add_activity("Gym")
    m1 = cs.add_activity_meeting(gym, {1}, time(17), time(18))
    m2 = cs.add_activity_meeting(gym, {2}, time(17), time(18))
    cs.skip_occurrence(ACTIVITY, m1, date(2026, 9, 1))
    cs.skip_occurrence(ACTIVITY, m2, date(2026, 9, 2))
    cs.delete_meeting(ACTIVITY, m1)
    assert [e.meeting_id for e in cs.list_exceptions()] == [m2]
    cs.delete_activity(gym)
    assert cs.list_exceptions() == [] and cs.list_activities() == []
    assert database.get_conn().execute("SELECT COUNT(*) FROM activity_meetings").fetchone()[0] == 0


# ---------- courses ----------
def test_course_meetings_with_an_end_date_and_exceptions_reach_the_planner(term):
    cid = make_course()
    mid = cs.add_course_meeting(cid, {0, 2, 4}, time(9), time(9, 50), "Room 1", date(2026, 9, 30))
    cs.override_occurrence(COURSE, mid, date(2026, 9, 2), time(11), time(11, 50), "Room 9")
    cs.skip_occurrence(COURSE, mid, date(2026, 9, 4))
    found = [b for b in cs.commitments(date(2026, 8, 31), date(2026, 9, 5)) if b.kind == "class"]
    assert [(timeutil.to_local(b.start, NY).strftime("%a %H:%M"), b.location, b.changed) for b in found] == [
        ("Mon 09:00", "Room 1", False), ("Wed 11:00", "Room 9", True)]
    assert cs.commitments(date(2026, 10, 5), date(2026, 10, 9)) == []                 # after the meeting's end date


def test_finished_courses_are_left_out_of_the_planner(term):
    done = make_course("MA 266", "Completed")
    cs.add_course_meeting(done, {0}, time(9), time(10))
    live = make_course("AE 6765")
    cs.add_course_meeting(live, {0}, time(9), time(10))
    assert [s.name for s in cs.load_series() if s.kind == COURSE] == ["AE 6765"]


def test_old_calendar_code_sees_end_dates_and_exceptions_too(term):
    cid = make_course()
    mid = cs.add_course_meeting(cid, {0, 2}, time(9), time(10), "Room 1", date(2026, 9, 9))
    cs.skip_occurrence(COURSE, mid, date(2026, 9, 2))
    cs.override_occurrence(COURSE, mid, date(2026, 9, 7), time(13), time(14), None)
    occ = crud.meeting_occurrences(date(2026, 8, 31), date(2026, 9, 14))
    assert sorted(occ) == [date(2026, 8, 31), date(2026, 9, 7), date(2026, 9, 9)]                    # Sep 2 skipped, nothing after Sep 9
    assert occ[date(2026, 9, 7)][0]["start"] == "13:00" and occ[date(2026, 9, 7)][0]["location"] == "Room 1"


# ---------- exceptions ----------
def test_exceptions_are_validated_replaced_and_restored(term):
    gym = cs.add_activity("Gym")
    mid = cs.add_activity_meeting(gym, {1}, time(17), time(18))
    with pytest.raises(PlannerError, match="does not happen"):
        cs.skip_occurrence(ACTIVITY, mid, date(2026, 9, 2))                   # a Wednesday
    with pytest.raises(PlannerError):
        cs.override_occurrence(ACTIVITY, mid, date(2026, 9, 1), time(19), time(18))
    with pytest.raises(PlannerError, match="does not exist"):
        cs.skip_occurrence(ACTIVITY, 999, date(2026, 9, 1))
    cs.override_occurrence(ACTIVITY, mid, date(2026, 9, 1), time(19), time(20), "Pool")
    cs.skip_occurrence(ACTIVITY, mid, date(2026, 9, 1))                       # one exception per day: the skip replaces the move
    (e,) = cs.list_exceptions()
    assert e.kind == "skip" and e.start is None
    cs.restore_occurrence(ACTIVITY, mid, date(2026, 9, 1))
    assert cs.list_exceptions() == []


# ---------- events ----------
def test_event_round_trip_in_utc_with_the_old_columns_filled(term):
    start, end = utc(2026, 9, 3, 14), utc(2026, 9, 3, 15)                    # 10:00-11:00 in New York
    eid = cs.add_event("Dentist", start, end, location="Clinic", commute_before=20, commute_after=30, course_id=None, source="manual")
    (ev,) = cs.list_events(date(2026, 9, 3), date(2026, 9, 3))
    assert (ev.id, ev.title, ev.start, ev.end, ev.location, ev.commute_before, ev.commute_after, ev.busy, ev.source) == (eid, "Dentist", start, end, "Clinic", 20, 30, True, "manual")
    row = dict(database.get_conn().execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone())
    assert row["start_utc"] == "2026-09-03T14:00:00Z" and (row["date"], row["time"], row["end_time"]) == ("2026-09-03", "10:00", "11:00")


def test_all_day_and_overnight_events_fill_the_old_columns_sensibly(term):
    cs.add_event("Conference", utc(2026, 9, 10, 4), utc(2026, 9, 12, 4), all_day=True)
    cs.add_event("Night lab", utc(2026, 9, 3, 2), utc(2026, 9, 3, 5))        # 22:00 Sep 2 to 01:00 Sep 3 in New York
    rows = {r["title"]: dict(r) for r in database.get_conn().execute("SELECT * FROM events")}
    assert rows["Conference"]["time"] is None and rows["Conference"]["date"] == "2026-09-10"
    assert rows["Night lab"]["date"] == "2026-09-02" and rows["Night lab"]["time"] == "22:00" and rows["Night lab"]["end_time"] is None


def test_invalid_events_are_refused_and_nothing_is_saved(term):
    with pytest.raises(PlannerError):
        cs.add_event("  ", utc(2026, 9, 3, 14), utc(2026, 9, 3, 15))
    with pytest.raises(PlannerError):
        cs.add_event("Backwards", utc(2026, 9, 3, 15), utc(2026, 9, 3, 14))
    with pytest.raises(PlannerError):
        cs.add_event("Far", utc(2026, 9, 3, 14), utc(2026, 9, 3, 15), commute_before=500)
    assert database.get_conn().execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_update_and_delete_an_event(term):
    eid = cs.add_event("Dentist", utc(2026, 9, 3, 14), utc(2026, 9, 3, 15))
    cs.update_event(eid, "Dentist (moved)", utc(2026, 9, 4, 14), utc(2026, 9, 4, 15), busy=False)
    assert cs.list_events(date(2026, 9, 3), date(2026, 9, 3)) == []
    (ev,) = cs.list_events(date(2026, 9, 4), date(2026, 9, 4))
    assert ev.title == "Dentist (moved)" and not ev.busy
    cs.delete_event(eid)
    assert cs.list_events(date(2026, 9, 1), date(2026, 9, 30)) == []


def test_list_events_picks_by_range_and_includes_the_old_rows(term):
    cs.add_event("In range", utc(2026, 9, 3, 14), utc(2026, 9, 3, 15))
    cs.add_event("Next week", utc(2026, 9, 10, 14), utc(2026, 9, 10, 15))
    crud.add_event("Midterm 1", "2026-09-03", None, "13:00", "14:15")        # an older event: a date and local times
    crud.add_event("Project due", "2026-09-04", None)                         # an older marker without a time
    found = {e.title: e for e in cs.list_events(date(2026, 9, 3), date(2026, 9, 4))}
    assert set(found) == {"In range", "Midterm 1", "Project due"}
    assert found["Midterm 1"].source == "legacy" and found["Midterm 1"].start == utc(2026, 9, 3, 17) and found["Project due"].all_day


def test_everything_together_for_a_day(term):
    cid = make_course()
    cs.add_course_meeting(cid, {1}, time(9), time(10), "Room 1")
    gym = cs.add_activity("Gym")
    cs.add_activity_meeting(gym, {1}, time(17), time(18))
    cs.add_event("Dentist", utc(2026, 9, 1, 19), utc(2026, 9, 1, 20), commute_before=15)          # 15:00-16:00 on Tuesday Sep 1
    found = cs.commitments(date(2026, 9, 1), date(2026, 9, 1))
    assert [(b.kind, timeutil.to_local(b.start, NY).strftime("%H:%M")) for b in found] == [("class", "09:00"), ("commute", "14:45"), ("event", "15:00"), ("activity", "17:00")]


# ---------- migration of an older database ----------
def test_an_older_database_gets_the_new_columns_and_keeps_its_rows(tmp_path, monkeypatch):
    old = tmp_path / "old.db"
    conn = sqlite3.connect(old)
    conn.executescript("""
        CREATE TABLE courses (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, name TEXT NOT NULL, semester TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1, target_hours REAL NOT NULL DEFAULT 0);
        CREATE TABLE class_meetings (id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL, days TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, location TEXT);
        CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, date TEXT NOT NULL, course_id INTEGER, time TEXT, end_time TEXT);
        INSERT INTO courses(code, name, semester) VALUES ('AE 1', 'Old', 'Fall 2025');
        INSERT INTO class_meetings(course_id, days, start_time, end_time, location) VALUES (1, '0,2', '09:00', '10:00', 'R1');
        INSERT INTO events(title, date, time) VALUES ('Old event', '2025-10-01', '13:00');
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", old)
    database.init_db()
    c2 = sqlite3.connect(old)
    c2.row_factory = sqlite3.Row
    cols = {r["name"] for r in c2.execute("PRAGMA table_info(events)")}
    assert {"all_day", "location", "commute_before", "commute_after", "busy", "start_utc", "end_utc", "source"} <= cols
    assert "end_date" in {r["name"] for r in c2.execute("PRAGMA table_info(class_meetings)")}
    ev = c2.execute("SELECT * FROM events").fetchone()
    assert (ev["title"], ev["time"], ev["busy"], ev["commute_before"], ev["start_utc"]) == ("Old event", "13:00", 1, 0, None)
    assert c2.execute("SELECT days, end_date FROM class_meetings").fetchone()["days"] == "0,2"
    assert c2.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 0
    c2.close()
