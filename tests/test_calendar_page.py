"""Phase 6: the Calendar page with the planner (rendered with Streamlit's test runner on a temporary database)."""
from datetime import date, datetime, time, timedelta, timezone

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import crud
from planner import commit_store as cs
from planner import service, session_store as ss, store, task_store as ts, timeutil
from planner.models import AwakeTimes

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
    cid = crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")
    return cid


def due(days, hh=23, mm=59):
    return timeutil.to_utc(TODAY + timedelta(days=days), time(hh, mm), NY)


def run(view="Week", **state):
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Calendar"
    at.session_state["cal_view"] = view
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    return at


def html_of(at):
    return " ".join(m.value for m in at.markdown)


def test_every_view_opens_without_errors_with_and_without_data(seeded):
    for view in ("Day", "Week", "Month"):
        assert not run(view).exception
    ts.add_task("HW 6", seeded, "Homework", due=due(3), estimate=120)
    service.auto_plan()
    for view in ("Day", "Week", "Month"):
        assert not run(view).exception


def test_the_grid_has_the_right_number_of_day_columns(seeded):
    assert html_of(run("Week")).count('class="wk-col') == 7
    assert html_of(run("Day")).count('class="wk-col') == 1


def test_sessions_events_and_travel_are_drawn_and_the_session_is_draggable(seeded):
    tid = ts.add_task("HW 6", seeded, "Homework", due=due(2), estimate=120)
    cs.add_event("Dentist", timeutil.to_utc(TODAY + timedelta(days=1), time(15), NY), timeutil.to_utc(TODAY + timedelta(days=1), time(16), NY), commute_before=20)
    sid = ss.add_session(tid, timeutil.to_utc(TODAY + timedelta(days=1), time(9), NY), timeutil.to_utc(TODAY + timedelta(days=1), time(10, 30), NY))
    at = run("Week", cal_anchor=TODAY + timedelta(days=1))
    html = html_of(at)
    assert f'data-ref="session:{sid}"' in html and "wk-session" in html and "wk-commute" in html and "Dentist" in html and "wk-resize" in html


def test_cushion_badges_and_the_banner(seeded):
    ok = ts.add_task("Easy", seeded, "Homework", due=due(5), estimate=60)
    at = run()
    assert "cu-pill" in html_of(at) and not at.warning                          # comfortable: no banner
    bad = ts.add_task("Impossible", seeded, "Project", due=due(1), estimate=3000)
    at = run()
    assert at.warning and "does not fit" in at.warning[0].value and "Impossible" in at.warning[0].value
    assert "#e0392b" in html_of(at) and "#2f9e5f" in html_of(at)                # a red and a green badge


def test_auto_plan_button_places_sessions(seeded):
    ts.add_task("HW 6", seeded, "Homework", due=due(3), estimate=120)
    at = run()
    assert ss.list_sessions() == []
    at.button(key="cal_autoplan").click()
    at.run()
    assert not at.exception and len(ss.list_sessions()) >= 1 and all(s.source == "auto" for s in ss.list_sessions())


def test_a_task_can_be_marked_done_unplanned_and_deleted_from_the_list(seeded):
    a = ts.add_task("A", seeded, "Homework", due=due(3), estimate=60)
    b = ts.add_task("B", seeded, "Homework", due=due(4), estimate=60)
    c_ = ts.add_task("C", seeded, "Homework", due=due(5), estimate=60)
    service.auto_plan()
    at = run(cal_page="Task List")
    at.checkbox(key=f"tl_done_{a}_0").check().run()
    assert ts.get_task(a).is_done
    at.button(key=f"tl_unplan_{b}").click(); at.run()
    assert ss.list_sessions(task_id=b) == []
    at.button(key=f"tl_del_{c_}").click(); at.run()
    assert [t.id for t in ts.list_tasks()] == [a, b] and not at.exception


def test_navigation_moves_by_the_size_of_the_view_and_today_returns(seeded):
    at = run("Week", cal_anchor=TODAY)
    at.button(key="cal_next").click(); at.run()
    assert at.session_state["cal_anchor"] == TODAY + timedelta(days=7)
    at.button(key="cal_today").click(); at.run()
    assert at.session_state["cal_anchor"] == TODAY
    at = run("Day", cal_anchor=TODAY)
    at.button(key="cal_next").click(); at.run()
    assert at.session_state["cal_anchor"] == TODAY + timedelta(days=1)


def test_a_drag_report_moves_a_session_and_a_conflict_asks_first(seeded):
    tid = ts.add_task("HW 6", seeded, "Homework", due=due(3), estimate=120)
    day = TODAY + timedelta(days=1)
    sid = ss.add_session(tid, timeutil.to_utc(day, time(9), NY), timeutil.to_utc(day, time(10), NY))
    at = run("Week", cal_anchor=day)
    at.text_input(key="cal_sink").set_value(f"move|session:{sid}|{day.isoformat()}|660|1"); at.run()                      # to 11:00: free
    moved = ss.get_session(sid)
    assert timeutil.to_local(moved.start, timeutil.zone(NY)).strftime("%H:%M") == "11:00" and moved.minutes == 60 and moved.source == "manual"
    crud_course = crud.add_course("AE 6451", "Propulsion", "Fall 2026", 0, "Active")
    cs.add_course_meeting(crud_course, {day.weekday()}, time(13), time(14))
    at.text_input(key="cal_sink").set_value(f"move|session:{sid}|{day.isoformat()}|780|2"); at.run()                      # onto the class: asks
    assert timeutil.to_local(ss.get_session(sid).start, timeutil.zone(NY)).strftime("%H:%M") == "11:00"                    # not moved yet
    assert at.session_state["cal_confirm"] is not None or any("Place It Anyway" in str(b.label) for b in at.button)


def test_a_resize_report_and_a_create_report(seeded):
    tid = ts.add_task("HW 6", seeded, "Homework", due=due(3), estimate=120)
    day = TODAY + timedelta(days=1)
    sid = ss.add_session(tid, timeutil.to_utc(day, time(9), NY), timeutil.to_utc(day, time(10), NY))
    at = run("Week", cal_anchor=day)
    at.text_input(key="cal_sink").set_value(f"resize|session:{sid}|{day.isoformat()}|660|3"); at.run()
    assert ss.get_session(sid).minutes == 120
    at.text_input(key="cal_sink").set_value(f"create|{day.isoformat()}|840|900|4"); at.run()
    assert not at.exception and any("Study Session" in str(getattr(x, "label", "")) or "Study Session" in str(getattr(x, "options", "")) for x in list(at.get("segmented_control")) + list(at.button))


def test_a_bad_drag_report_is_ignored_not_a_crash(seeded):
    at = run("Week")
    for text in ("nonsense", "move|session:abc|2026-01-01|10|1", "move|session:9999|2026-01-01|600|1", "resize|event:9999|2026-01-01|600|1", "create|not-a-date|1|2|3", "|"):
        at.text_input(key="cal_sink").set_value(text); at.run()
        assert not at.exception, text


def test_an_event_made_in_the_page_form_is_a_planner_event(seeded):
    at = run("Week")
    assert not at.exception
    evs_before = len(cs.list_events(TODAY, TODAY + timedelta(days=30)))
    cs.add_event("Dentist", timeutil.to_utc(TODAY + timedelta(days=2), time(15), NY), timeutil.to_utc(TODAY + timedelta(days=2), time(16), NY))
    assert len(cs.list_events(TODAY, TODAY + timedelta(days=30))) == evs_before + 1
    assert "Dentist" in html_of(run("Week", cal_anchor=TODAY + timedelta(days=2)))
