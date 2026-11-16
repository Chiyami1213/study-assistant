"""The left panel of draggable blocks and the free time in the grid: drawing code, and what a drop does (rendered with Streamlit's test runner)."""
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import crud
from planner import commit_store as cs
from planner import freetime as F
from planner import service, session_store as ss, store, task_store as ts, timeutil
from planner.models import AwakeTimes
from views import plan_grid as G
from views import planner_ui

pytestmark = pytest.mark.usefixtures("fresh_data")
NY = "America/New_York"
TODAY = date.today()
APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def seeded():
    store.set_timezone(NY)
    store.set_term_dates(TODAY - timedelta(days=30), TODAY + timedelta(days=60), TODAY + timedelta(days=70))
    store.set_awake(AwakeTimes.uniform(time(8), time(22)))
    store.set_min_block(30)
    return crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")


def due(days, hh=23, mm=59):
    return timeutil.to_utc(TODAY + timedelta(days=days), time(hh, mm), NY)


def run(**state):
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Calendar"
    at.session_state["cal_view"] = "Week"
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    return at


# ---------- free time in the grid ----------
def test_free_items_are_clipped_to_the_day_and_labeled_with_their_length():
    tz = timeutil.zone(NY)
    day = date(2026, 9, 7)
    pieces = [(timeutil.to_utc(day, time(9), NY), timeutil.to_utc(day, time(10, 30), NY)),
              (timeutil.to_utc(day, time(23), NY), timeutil.to_utc(day + timedelta(days=1), time(1), NY)),
              (timeutil.to_utc(day, time(12), NY), timeutil.to_utc(day, time(12, 10), NY))]                 # 10 minutes: too small to show
    got = G.free_items(day, pieces, tz)
    assert [(i.kind, i.title, i.start, i.end) for i in got] == [("free", "1 h 30 min", 540, 630), ("free", "1 h", 23 * 60, 1440)]
    assert G.free_items(day + timedelta(days=2), pieces, tz) == []


def test_free_areas_are_drawn_behind_the_blocks_and_do_not_widen_the_grid():
    day = date(2026, 9, 7)
    free = {day: [G.Item("free", "2 h", 600, 720, "#7c6aff")]}
    html = G.grid_html([day], day, {day: [G.Item("class", "A", 600, 660, "#123456")]}, {}, set(), 6, 24, lambda c: c, None, free)
    assert html.index("wk-free") < html.index("wk-block") and ">2 h<" in html
    assert G.hour_range({day: [G.Item("free", "x", 0, 1440, "#1")]}) == (6, 24)               # free time never stretches the day


# ---------- the panel ----------
def test_panel_lists_dragable_blocks_for_tasks_courses_activities_and_an_event():
    t = G.Item  # (unused name kept short)
    from planner import tasks as T
    courses = {1: {"id": 1, "code": "AE 6765", "name": "Kinetics", "is_active": 1, "section": "courses", "color": "#336699", "category": None},
               2: {"id": 2, "code": "OLD 1", "name": "Old", "is_active": 0, "section": "courses", "color": None, "category": None}}
    task = T.Task(5, "HW <6>", 1, "Homework", datetime(2026, 9, 10, tzinfo=timezone.utc), 120)
    report = F.CushionReport((F.Cushion(5, task.due, -30, 0, 30, task.due, F.RED),), (), True)
    html = planner_ui.panel_html([task], courses, [{"id": 9, "name": "Gym", "color": "#0f766e"}], report, {5: 90})
    for part in ('data-drag="event:0"', 'data-drag="course:1"', 'data-drag="activity:9"', "Custom Event", "AE 6765", "Gym"):
        assert part in html
    assert 'data-drag="task:' not in html and "HW" not in html                  # tasks are in the Task List, not in the panel
    assert 'data-drag="course:2"' not in html                                  # a finished course is not offered
    assert "No active courses." in planner_ui.panel_html([], {}, [], F.CushionReport((), (), False), {})


def test_the_panel_is_on_the_page_and_free_time_can_be_hidden(seeded):
    ts.add_task("HW 6", seeded, "Homework", due=due(3), estimate=120)
    at = run()
    html = " ".join(m.value for m in at.markdown)
    assert 'data-drag="course:' in html and 'class="wk-free"' in html and not at.exception
    at.toggle(key="cal_free").set_value(False); at.run()
    assert 'class="wk-free"' not in " ".join(m.value for m in at.markdown)


# ---------- dropping ----------
def test_how_long_a_dropped_study_session_is(seeded):
    big = ts.add_task("Big", seeded, "Project", due=due(5), estimate=600)
    small = ts.add_task("Small", seeded, "Quiz", due=due(5), estimate=45)
    tiny = ts.add_task("Tiny", seeded, "Other", due=due(5), estimate=10 if False else 20)
    assert planner_ui._drop_duration(big) == 120                                  # at most two hours
    assert planner_ui._drop_duration(small) == 45
    assert planner_ui._drop_duration(tiny) == 30                                   # at least the minimum block
    ss.add_session(small, due(1, 9, 0), due(1, 9, 45))
    assert planner_ui._drop_duration(small) == 30                                  # nothing left to plan: the minimum block


def test_dropping_a_task_adds_a_manual_study_session_at_that_time(seeded):
    tid = ts.add_task("HW 6", seeded, "Homework", due=due(4), estimate=90)
    day = TODAY + timedelta(days=1)
    at = run(cal_anchor=day)
    at.text_input(key="cal_sink").set_value(f"drop|task:{tid}|{day.isoformat()}|600|1"); at.run()                  # 10:00
    (s,) = ss.list_sessions()
    local = timeutil.to_local(s.start, timeutil.zone(NY))
    assert (s.task_id, local.strftime("%H:%M"), local.date(), s.minutes, s.source) == (tid, "10:00", day, 90, "manual") and not at.exception


def test_dropping_a_task_onto_a_class_asks_before_placing(seeded):
    tid = ts.add_task("HW 6", seeded, "Homework", due=due(4), estimate=60)
    day = TODAY + timedelta(days=1)
    cs.add_course_meeting(seeded, {day.weekday()}, time(10), time(11))
    at = run(cal_anchor=day)
    at.text_input(key="cal_sink").set_value(f"drop|task:{tid}|{day.isoformat()}|600|1"); at.run()
    assert ss.list_sessions() == [] and any("Place It Anyway" in str(b.label) for b in at.button)                # nothing placed yet; the question is open


def test_dropping_the_custom_event_block_opens_the_event_form_and_a_course_block_the_weekly_time_form(seeded):
    day = TODAY + timedelta(days=1)
    at = run(cal_anchor=day)
    at.text_input(key="cal_sink").set_value(f"drop|event:0|{day.isoformat()}|840|1"); at.run()
    assert not at.exception and at.button(key="cr_add_event") is not None and at.text_input(key="cr_title") is not None
    at = run(cal_anchor=day)
    at.text_input(key="cal_sink").set_value(f"drop|course:{seeded}|{day.isoformat()}|660|2"); at.run()
    assert not at.exception
    assert at.multiselect(key=f"mt2_days_course_{seeded}").value == [day.weekday()]                  # the day it was dropped on is ticked
    assert at.button(key=f"mt2_save_course_{seeded}") is not None
    assert planner_ui.save_meeting("course", seeded, [day.weekday(), (day.weekday() + 2) % 7], time(11), time(12, 15)) is None
    meetings = crud.list_meetings(seeded)
    assert len(meetings) == 1 and set(meetings[0]["days"].split(",")) == {str(day.weekday()), str((day.weekday() + 2) % 7)} and meetings[0]["start_time"] == "11:00"


def test_dropping_an_activity_block_adds_its_weekly_time(seeded):
    aid = cs.add_activity("Gym")
    day = TODAY + timedelta(days=1)
    at = run(cal_anchor=day)
    at.text_input(key="cal_sink").set_value(f"drop|activity:{aid}|{day.isoformat()}|1080|1"); at.run()
    assert not at.exception and at.button(key=f"mt2_save_activity_{aid}") is not None
    assert planner_ui.save_meeting("activity", aid, [day.weekday()], time(18), time(19)) is None
    series = [s for s in cs.load_series() if s.kind == "activity"]
    assert len(series) == 1 and series[0].meetings[0].days == frozenset({day.weekday()}) and series[0].meetings[0].start == time(18)


def test_bad_drops_are_ignored(seeded):
    at = run()
    for text in ("drop|task:9999|2026-01-01|600|1", "drop|nonsense|2026-01-01|600|1", "drop|task:1|not-a-date|600|1", "drop|course:abc|2026-01-01|600|1", "drop|task:1|2026-01-01|x|1"):
        at.text_input(key="cal_sink").set_value(text); at.run()
        assert not at.exception, text


def test_a_weekly_time_that_makes_no_sense_is_refused_with_the_reason(seeded):
    assert "after it starts" in planner_ui.save_meeting("course", seeded, [1], time(12), time(11))
    assert planner_ui.save_meeting("course", seeded, [], time(9), time(10))
    assert crud.list_meetings(seeded) == []
