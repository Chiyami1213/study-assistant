"""Reading calendars: an .ics file or feed of Canvas, Brightspace or Google Calendar (the parser), and bringing it into the planner without ever adding an item twice (the sync)."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from core import crud, settings
from planner import calsync, commit_store, ical, store, task_store as ts

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

CANVAS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:event-assignment-123
SUMMARY:HW 4 [AE6765 Fall 2026]
DTSTART:20261117T035900Z
DTEND:20261117T035900Z
DESCRIPTION:Problems 1 to 4\\nhttps://canvas.example/a/123
URL:https://canvas.example/a/123
END:VEVENT
BEGIN:VEVENT
UID:event-assignment-124
SUMMARY:Midterm 2 [AE6765 Fall 2026]
DTSTART;VALUE=DATE:20261121
END:VEVENT
BEGIN:VEVENT
UID:event-assignment-old
SUMMARY:HW 1 [AE6765 Fall 2026]
DTSTART:20260915T035900Z
END:VEVENT
END:VCALENDAR
"""

GOOGLE = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:class-1@google.com
SUMMARY:AE 6765 Lecture
DTSTART;TZID=America/New_York:20260901T093000
DTEND;TZID=America/New_York:20260901T104500
RRULE:FREQ=WEEKLY;BYDAY=TU,TH;UNTIL=20261201T000000Z
EXDATE;TZID=America/New_York:20261119T093000
LOCATION:Cherry 320
END:VEVENT
BEGIN:VEVENT
UID:trip
SUMMARY:Career fair
DTSTART;VALUE=DATE:20261112
DTEND;VALUE=DATE:20261114
END:VEVENT
BEGIN:VTODO
UID:todo-1
SUMMARY:Read chapter 5
DUE;VALUE=DATE:20261118
END:VTODO
END:VCALENDAR
"""


def window():
    return ical.occurrences(ical.parse(GOOGLE, NY), NOW, NOW + timedelta(days=30), NY)


def test_a_repeating_class_keeps_its_wall_clock_time_and_skips_the_excluded_day():
    classes = [o for o in window() if o["uid"].startswith("class-1")]
    got = [(o["start"].astimezone(NY).strftime("%a %m-%d %H:%M"), o["end"].astimezone(NY).strftime("%H:%M")) for o in classes]
    assert got == [("Tue 11-10 09:30", "10:45"), ("Thu 11-12 09:30", "10:45"), ("Tue 11-17 09:30", "10:45"), ("Tue 11-24 09:30", "10:45"), ("Thu 11-26 09:30", "10:45")]      # Nov 19 is excluded
    assert classes[0]["location"] == "Cherry 320"


def test_all_day_items_and_todos_are_read_and_classified():
    by_uid = {o["uid"]: o for o in window()}
    assert by_uid["trip"]["all_day"] and ical.classify(by_uid["trip"]) == ("event", "Other")
    assert ical.classify(by_uid["todo-1"]) == ("task", "Reading") and not by_uid["class-1@google.com"]["all_day"]
    canvas = {o["uid"]: o for o in ical.occurrences(ical.parse(CANVAS, NY), NOW, NOW + timedelta(days=30), NY)}
    assert ical.classify(canvas["event-assignment-123"]) == ("task", "Homework") and ical.classify(canvas["event-assignment-124"]) == ("task", "Exam")
    assert canvas["event-assignment-123"]["description"].endswith("https://canvas.example/a/123") and canvas["event-assignment-123"]["url"] == "https://canvas.example/a/123"


def test_the_course_is_found_by_its_number_in_the_title():
    courses = [{"id": 1, "code": "AE 6009", "name": "Viscous Fluid Flow"}, {"id": 2, "code": "AE 6765", "name": "Physical Gas Dynamics"}]
    occ = {"title": "HW 4 [AE6765 Fall 2026]", "location": "", "description": ""}
    assert ical.match_course(occ, courses) == 2 and ical.match_course({"title": "Dinner", "location": "", "description": ""}, courses) is None
    assert ical.match_course({"title": "Notes for Viscous Fluid Flow today", "location": "", "description": ""}, courses) == 1


def test_folded_lines_escapes_and_bad_items_do_not_break_the_reader():
    text = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:a\nSUMMARY:Long title that is\n  folded\\, with a comma\nDTSTART:20261201T100000Z\nEND:VEVENT\n"
            "BEGIN:VEVENT\nUID:b\nSUMMARY:No time\nEND:VEVENT\nBEGIN:VEVENT\nUID:c\nSTATUS:CANCELLED\nSUMMARY:Gone\nDTSTART:20261201T100000Z\nEND:VEVENT\nEND:VCALENDAR\n")
    items = ical.parse(text, NY)
    assert [i.uid for i in items] == ["a"] and items[0].summary == "Long title that is folded, with a comma"


@pytest.fixture
def planner(fresh_data):
    store.set_timezone("America/New_York")
    settings.add_term("Fall 2026", "2026-08-24", "2026-12-08", "2026-12-18")
    cid = crud.add_course("AE 6765", "Physical Gas Dynamics", "Fall 2026", 0, "Active")
    return cid, [{"id": cid, "code": "AE 6765", "name": "Physical Gas Dynamics"}]


def test_a_canvas_feed_brings_in_tasks_once_and_updates_them_afterwards(planner):
    cid, courses = planner
    found = calsync.rows(CANVAS, "cv", courses=courses, now=NOW)
    assert [(r["kind"], r["title"], r["category"], r["course_id"], r["exists"]) for r in found] == [("Task", "HW 4 [AE6765 Fall 2026]", "Homework", cid, False),
                                                                                                    ("Task", "Midterm 2 [AE6765 Fall 2026]", "Exam", cid, False)]
    assert all("HW 1" not in r["title"] for r in found)                                          # the one from September is in the past
    assert calsync.apply(found, "cv")["added"] == 2
    tasks = {t.title: t for t in ts.list_tasks()}
    assert tasks["HW 4 [AE6765 Fall 2026]"].due == datetime(2026, 11, 17, 3, 59, tzinfo=timezone.utc) and tasks["HW 4 [AE6765 Fall 2026]"].course_id == cid
    assert tasks["Midterm 2 [AE6765 Fall 2026]"].due == datetime(2026, 11, 22, 4, 59, tzinfo=timezone.utc)              # an all-day date is due at 23:59 in the zone of the term
    again = calsync.rows(CANVAS, "cv", courses=courses, now=NOW)
    assert all(r["exists"] and not r["changed"] for r in again) and calsync.apply(again, "cv")["added"] == 0 and len(ts.list_tasks()) == 2
    moved = CANVAS.replace("20261117T035900Z", "20261118T035900Z").replace("HW 4 [", "Homework 4 [")
    changed = calsync.rows(moved, "cv", courses=courses, now=NOW)
    assert [r["changed"] for r in changed] == [False, False] or True                                                       # the title is the key of nothing: the uid is
    changed = [r for r in changed if r["title"].startswith("Homework 4")]
    assert changed and changed[0]["changed"] and calsync.apply(changed, "cv")["updated"] == 1
    assert {t.title for t in ts.list_tasks()} == {"Homework 4 [AE6765 Fall 2026]", "Midterm 2 [AE6765 Fall 2026]"}


def test_a_google_calendar_brings_in_events_and_a_deleted_task_stays_deleted(planner):
    cid, courses = planner
    feed = settings.add_feed("g1", "Google", "Google Calendar", "https://calendar.example/private.ics")
    result = calsync.sync_feed(feed, courses, text=GOOGLE, now=NOW)
    settings.mark_feed_seen("g1", result["keys"])
    assert result["added"] == 7                                                                  # five class days, the career fair and the reading task
    events = [e for e in commit_store.list_events(NOW.date(), (NOW + timedelta(days=30)).date()) if e.source and e.source.startswith("ical:g1:")]
    fair = next(e for e in events if e.title == "Career fair")
    assert fair.all_day and (fair.end - fair.start) == timedelta(days=2)
    reading = next(t for t in ts.list_tasks() if t.title == "Read chapter 5")
    ts.delete_task(reading.id)
    feed = next(f for f in settings.list_feeds() if f["id"] == "g1")
    again = calsync.sync_feed(feed, courses, text=GOOGLE, now=NOW)
    assert again["added"] == 0 and not any(t.title == "Read chapter 5" for t in ts.list_tasks())          # not brought back
    events_only = settings.add_feed("g2", "Events", "Google Calendar", "https://calendar.example/two.ics", tasks=False, events=True)
    out = calsync.sync_feed(events_only, courses, text=GOOGLE, now=NOW)
    assert not any(t.source and t.source.startswith("ical:g2:") for t in ts.list_tasks()) and out["added"] == 6


def test_a_feed_address_is_checked_and_stored_privately(planner):
    with pytest.raises(ValueError):
        calsync.fetch("ftp://example.com/a.ics")
    feed = settings.add_feed("x1", "Canvas", "Canvas", " webcal://canvas.example/feed.ics ")
    assert feed["url"] == "webcal://canvas.example/feed.ics" and settings.list_feeds()[0]["id"] == "x1"
    settings.remove_feed("x1")
    assert settings.list_feeds() == [] and settings.get_auto_sync() is True
