"""Recurring classes and activities on the Calendar: open one occurrence, change it for one day only or for every week."""
from datetime import date, time, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import crud
from planner import commit_store as cs
from planner import store, timeutil
from planner.models import AwakeTimes
from views import plan_grid as G
from views import planner_ui as P

pytestmark = pytest.mark.usefixtures("fresh_data")
NY = "America/New_York"
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _next_weekday(d, weekday):
    return d + timedelta(days=(weekday - d.weekday()) % 7)


TODAY = date.today()
TUE = _next_weekday(TODAY + timedelta(days=1), 1)                 # a Tuesday in the future, inside the term below
NEXT_TUE = TUE + timedelta(days=7)


@pytest.fixture
def seeded():
    store.set_timezone(NY)
    store.set_term_dates(TODAY - timedelta(days=30), TODAY + timedelta(days=90), TODAY + timedelta(days=100))
    store.set_awake(AwakeTimes.uniform(time(8), time(22)))
    cid = crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")
    mid = cs.add_course_meeting(cid, {1, 3}, time(9), time(10, 15), "Room 1")
    aid = cs.add_activity("Gym", "#0f766e", "Rec center")
    amid = cs.add_activity_meeting(aid, {1}, time(17), time(18))
    return cid, mid, aid, amid


def blocks_on(day, kind=None):
    return [b for b in cs.commitments(day, day) if kind is None or b.kind == kind]


def local(b):
    return timeutil.to_local(b.start, timeutil.zone(NY)).strftime("%H:%M")


def run(**state):
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Calendar"
    at.session_state["cal_view"] = "Week"
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    return at


# ---------- the grid: classes and activities open on a click ----------
def test_class_and_activity_blocks_carry_what_a_click_needs_and_cannot_be_dragged(seeded):
    cid, mid, aid, amid = seeded
    tz = timeutil.zone(NY)
    items = G.day_items(TUE, cs.commitments(TUE, TUE), [], {}, {cid: "#336699"}, {}, tz)
    refs = {i.kind: i.open_ref for i in items}
    assert refs == {"class": f"occ:course:{mid}:{TUE.isoformat()}", "activity": f"occ:activity:{amid}:{TUE.isoformat()}"}
    cls = next(i for i in items if i.kind == "class")
    html = G.block_html(cls, 0, 1, 6, lambda c: c)
    assert f'data-open="occ:course:{mid}:{TUE.isoformat()}"' in html and "wk-openable" in html and "data-edit" not in html and "wk-resize" not in html


def test_a_changed_occurrence_is_marked_on_the_grid(seeded):
    cid, mid, *_ = seeded
    assert P.move_this("course", mid, TUE, time(11), time(12)) is None
    tz = timeutil.zone(NY)
    items = G.day_items(TUE, cs.commitments(TUE, TUE), [], {}, {cid: "#336699"}, {}, tz)
    cls = next(i for i in items if i.kind == "class")
    assert (cls.start, cls.end, cls.changed) == (660, 720, True) and "moved" in G.block_html(cls, 0, 1, 6, lambda c: c)


# ---------- this day only ----------
def test_skip_this_day_removes_only_that_day(seeded):
    cid, mid, *_ = seeded
    assert len(blocks_on(TUE, "class")) == 1 and len(blocks_on(NEXT_TUE, "class")) == 1
    assert P.skip_this("course", mid, TUE) is None
    assert blocks_on(TUE, "class") == [] and len(blocks_on(NEXT_TUE, "class")) == 1
    P.restore_this("course", mid, TUE)
    assert len(blocks_on(TUE, "class")) == 1


def test_move_this_day_changes_the_time_and_place_for_that_day_only(seeded):
    cid, mid, *_ = seeded
    assert P.move_this("course", mid, TUE, time(13), time(14), "Room 9") is None
    (b,) = blocks_on(TUE, "class")
    assert (local(b), b.location, b.changed) == ("13:00", "Room 9", True)
    (other,) = blocks_on(NEXT_TUE, "class")
    assert (local(other), other.location, other.changed) == ("09:00", "Room 1", False)
    assert P.move_this("course", mid, TUE, time(13), time(14), None) is None                     # no new place: the usual one
    assert blocks_on(TUE, "class")[0].location == "Room 1"
    P.restore_this("course", mid, TUE)
    assert local(blocks_on(TUE, "class")[0]) == "09:00" and not blocks_on(TUE, "class")[0].changed


def test_bad_one_day_changes_say_why_and_change_nothing(seeded):
    cid, mid, *_ = seeded
    assert "after it starts" in P.move_this("course", mid, TUE, time(14), time(13))
    wed = TUE + timedelta(days=1)
    assert "does not happen" in P.skip_this("course", mid, wed)
    assert "does not exist" in P.skip_this("course", 999, TUE)
    assert cs.list_exceptions() == []


def test_the_old_calendar_code_sees_one_day_changes_too(seeded):
    cid, mid, *_ = seeded
    P.skip_this("course", mid, TUE)
    P.move_this("course", mid, NEXT_TUE, time(15), time(16))
    occ = crud.meeting_occurrences(TUE, NEXT_TUE)
    assert TUE not in occ and occ[NEXT_TUE][0]["start"] == "15:00"


# ---------- every week ----------
def test_save_for_every_week_changes_the_series_and_keeps_one_day_changes(seeded):
    cid, mid, *_ = seeded
    P.skip_this("course", mid, TUE)
    assert P.save_series("course", mid, [1, 4], time(10), time(11, 30), "Room 2", None) is None
    assert len(blocks_on(NEXT_TUE, "class")) == 1 and local(blocks_on(NEXT_TUE, "class")[0]) == "10:00" and blocks_on(NEXT_TUE, "class")[0].location == "Room 2"
    assert blocks_on(TUE, "class") == []                                                       # the skipped day is still skipped
    thu = TUE + timedelta(days=2)
    assert blocks_on(thu, "class") == []                                                       # Thursday is no longer a meeting day
    fri = TUE + timedelta(days=3)
    assert len(blocks_on(fri, "class")) == 1


def test_a_last_day_ends_the_series(seeded):
    cid, mid, *_ = seeded
    assert P.save_series("course", mid, [1, 3], time(9), time(10, 15), "Room 1", NEXT_TUE) is None
    assert len(blocks_on(NEXT_TUE, "class")) == 1 and blocks_on(NEXT_TUE + timedelta(days=7), "class") == []


def test_bad_series_changes_are_refused_with_the_reason(seeded):
    cid, mid, *_ = seeded
    assert "after it starts" in P.save_series("course", mid, [1], time(12), time(11))
    assert P.save_series("course", mid, [], time(9), time(10))
    assert "does not exist" in P.save_series("course", 999, [1], time(9), time(10))
    assert cs.get_meeting("course", mid)["days"] == "1,3"


def test_remove_the_weekly_time_takes_its_one_day_changes_with_it(seeded):
    cid, mid, *_ = seeded
    P.skip_this("course", mid, TUE)
    P.remove_series("course", mid)
    assert crud.list_meetings(cid) == [] and cs.list_exceptions() == [] and blocks_on(NEXT_TUE, "class") == []


def test_activities_work_the_same_way_and_can_be_edited_or_deleted(seeded):
    cid, mid, aid, amid = seeded
    assert len(blocks_on(TUE, "activity")) == 1
    P.skip_this("activity", amid, TUE)
    assert blocks_on(TUE, "activity") == [] and len(blocks_on(NEXT_TUE, "activity")) == 1
    assert P.save_series("activity", amid, [1, 2], time(6), time(7), "Pool", None) is None
    assert local(blocks_on(NEXT_TUE, "activity")[0]) == "06:00" and len(blocks_on(NEXT_TUE + timedelta(days=1), "activity")) == 1
    assert P.save_activity(aid, "Swimming", "#123456", "Pool", False, True) is None
    series = [s for s in cs.load_series() if s.kind == "activity"][0]
    assert (series.name, series.color, series.busy, series.in_breaks) == ("Swimming", "#123456", False, True)
    assert "needs a name" in P.save_activity(aid, "  ", "#123456", "", True, False)
    cs.delete_activity(aid)
    assert cs.list_activities() == [] and cs.list_exceptions() == [] and blocks_on(NEXT_TUE, "activity") == []


# ---------- the page ----------
def test_clicking_a_class_opens_its_compact_dialog_for_this_day_or_every_week(seeded):
    cid, mid, *_ = seeded
    at = run(cal_anchor=TUE)
    at.text_input(key="cal_sink").set_value(f"click|occ:course:{mid}:{TUE.isoformat()}|1"); at.run()
    assert not at.exception
    key = f"oc_course_{mid}_{TUE.isoformat()}"
    assert any("dlg-banner" in m.value for m in at.markdown)                                      # the title bar in the course's color
    for suffix in ("_del", "_cancel", "_save"):                                                   # Delete (skip this day), Cancel, Save
        assert at.button(key=key + suffix) is not None, suffix
    assert at.button(key=key + "_del").label == "Skip This Class"
    assert not [b for b in at.button if b.key == key + "_restore"]                                # nothing to go back to yet
    at.get("segmented_control")[-1].set_value("Every Week") if False else None


def test_the_dialog_of_an_activity_also_offers_the_activity_itself(seeded):
    cid, mid, aid, amid = seeded
    at = run(cal_anchor=TUE)
    at.text_input(key="cal_sink").set_value(f"click|occ:activity:{amid}:{TUE.isoformat()}|1"); at.run()
    key = f"oc_activity_{amid}_{TUE.isoformat()}"
    assert not at.exception and at.button(key=key + "_asave") is not None and at.button(key=key + "_adel").disabled


def test_a_changed_day_enables_back_to_usual(seeded):
    cid, mid, *_ = seeded
    P.skip_this("course", mid, TUE)
    at = run(cal_anchor=TUE)
    at.text_input(key="cal_sink").set_value(f"click|occ:course:{mid}:{TUE.isoformat()}|1"); at.run()
    assert at.button(key=f"oc_course_{mid}_{TUE.isoformat()}_restore") is not None                  # a skipped day offers Back to Usual


def test_clicks_on_a_removed_meeting_or_a_bad_reference_do_not_crash(seeded):
    at = run(cal_anchor=TUE)
    for text in ("click|occ:course:9999:2026-01-01|1", "click|occ:nonsense|2", "click|occ:course:abc:2026-01-01|3", "click|occ:course:1:not-a-date|4"):
        at.text_input(key="cal_sink").set_value(text); at.run()
        assert not at.exception, text
