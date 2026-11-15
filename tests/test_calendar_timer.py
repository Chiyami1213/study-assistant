"""Phase 7 on the Calendar page: the study timer bar, start and log buttons, how much of a session was used, and suggested estimates."""
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import crud
from planner import service, session_store as ss, store, task_store as ts, timeutil, track_store as tr
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
    return crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")


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


def test_no_timer_bar_without_a_running_timer(seeded):
    ts.add_task("HW", seeded, "Homework", due=due(3), estimate=60)
    at = run()
    assert not [b for b in at.button if b.key in ("timer_stop", "timer_cancel")] and not at.exception


def test_the_play_button_starts_the_timer_and_shows_the_bar(seeded):
    a = ts.add_task("A", seeded, "Homework", due=due(3), estimate=60)
    b = ts.add_task("B", seeded, "Homework", due=due(4), estimate=60)
    at = run()
    assert not at.button(key=f"tk_start_{a}").disabled
    at.button(key=f"tk_start_{a}").click(); at.run()
    assert tr.running_timer().task_id == a and not at.exception
    assert at.button(key="timer_stop") is not None and at.button(key="timer_cancel") is not None
    assert "Studying A" in html_of(at) or any("Studying A" in m.value for m in at.markdown)
    assert at.button(key=f"tk_start_{b}").disabled                                          # one timer at a time


def test_stop_and_log_adds_the_time_and_raises_the_cushion(seeded):
    tid = ts.add_task("HW", seeded, "Homework", due=due(2), estimate=300)
    before = service.cushion_report().of(tid).cushion_minutes
    tr.start_timer(tid, now=datetime.now(timezone.utc) - timedelta(minutes=10, seconds=10))
    at = run()
    at.button(key="timer_stop").click(); at.run()
    assert ts.get_task(tid).logged_minutes == 10 and tr.running_timer() is None and not at.exception
    assert not [b for b in at.button if b.key == "timer_stop"]
    assert service.cushion_report().of(tid).demand_minutes == 290


def test_cancel_discards_the_timer_without_logging(seeded):
    tid = ts.add_task("HW", seeded, "Homework", due=due(2), estimate=300)
    tr.start_timer(tid, now=datetime.now(timezone.utc) - timedelta(minutes=20))
    at = run()
    at.button(key="timer_cancel").click(); at.run()
    assert tr.running_timer() is None and ts.get_task(tid).logged_minutes == 0 and not at.exception


def test_a_timer_for_a_task_that_was_deleted_is_cleared_not_a_crash(seeded):
    tid = ts.add_task("HW", seeded, "Homework", due=due(2), estimate=60)
    tr.start_timer(tid)
    ts.delete_task(tid)
    at = run()
    assert tr.running_timer() is None and not at.exception


def test_a_session_shows_how_much_of_it_was_used(seeded):
    tid = ts.add_task("HW", seeded, "Homework", due=due(4), estimate=120)
    day = TODAY + timedelta(days=1)
    sid = ss.add_session(tid, timeutil.to_utc(day, time(10), NY), timeutil.to_utc(day, time(11), NY))
    assert 'class="wk-used"' not in html_of(run(cal_anchor=day))
    tr.log_time(tid, 30, session_id=sid)
    html = html_of(run(cal_anchor=day))
    assert 'class="wk-used" style="width:50%"' in html


def test_the_task_row_shows_time_used(seeded):
    tid = ts.add_task("HW", seeded, "Homework", due=due(4), estimate=120)
    tr.log_time(tid, 45)
    at = run()
    assert any("45 min used" in m.value for m in at.markdown)


def test_the_add_task_form_suggests_an_estimate_from_finished_tasks(seeded):
    for minutes in (60, 100):
        tid = ts.add_task(f"Old {minutes}", seeded, "Homework", estimate=200)
        tr.log_time(tid, minutes)
        ts.set_done(tid)
    at = run()
    at.button(key="tk_add_open").click(); at.run()
    assert any("Suggestion" in c.value and "80 minutes" in c.value for c in at.caption) and not at.exception
    ts.add_task("Quiz one", seeded, "Quiz", estimate=45)                                                           # nothing finished in other categories: no suggestion there
    assert tr.suggestion("Quiz") is None
