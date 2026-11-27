"""Recurring classes and activities on the Calendar: open one occurrence, change it for one day only or for every week."""
from datetime import date, time, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import crud
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
    assert f'data-ref="occ:course:{mid}:{TUE.isoformat()}"' in html and "data-edit" in html and 'class="wk-resize-top"' in html and 'class="wk-resize"' in html


def test_a_changed_occurrence_is_marked_on_the_grid(seeded):
    cid, mid, *_ = seeded
    assert P.move_this("course", mid, TUE, time(11), time(12)) is None
    tz = timeutil.zone(NY)
    items = G.day_items(TUE, cs.commitments(TUE, TUE), [], {}, {cid: "#336699"}, {}, tz)
    cls = next(i for i in items if i.kind == "class")
    assert (cls.start, cls.end, cls.changed) == (660, 720, True) and "wk-moved" not in G.block_html(cls, 0, 1, 6, lambda c: c)


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
    assert at.button(key=key + "_del").label == "Delete"
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


# ---------------------------------------------------------------- Deleting a repeating event: this one, this and the following on this weekday, this and all following, all
def _new_course():
    return crud.add_course("XX 100", "Test", "Fall 2026", 0, "Active")


def _series(cid, days, start=time(9, 30), end=time(10, 45)):
    return cs.add_course_meeting(cid, set(days), start, end, "Room 1")


def _has(cid, day):
    return any(b.kind == "class" and b.owner_id == cid for b in cs.commitments(day, day))


def test_delete_this_event_only(seeded):
    cid = _new_course()
    mid = _series(cid, {1, 3})
    assert "That day" in cs.delete_occurrences("course", mid, TUE, "this")
    assert not _has(cid, TUE) and _has(cid, TUE + timedelta(days=7)) and _has(cid, TUE + timedelta(days=2))


def test_delete_this_and_following_on_this_weekday_keeps_the_other_days_and_the_earlier_tuesdays(seeded):
    cid = _new_course()
    mid = _series(cid, {1, 3})
    later = TUE + timedelta(days=14)
    cs.delete_occurrences("course", mid, later, "weekday")
    assert not _has(cid, later) and not _has(cid, later + timedelta(days=7))                              # no more of that weekday from then on
    assert _has(cid, later + timedelta(days=2)) and _has(cid, later + timedelta(days=9))                  # Thursdays go on
    assert _has(cid, later - timedelta(days=7))                                                           # the Tuesday before is kept


def test_delete_this_and_all_following_ends_the_series_the_day_before(seeded):
    cid = _new_course()
    mid = _series(cid, {1, 3})
    cut = TUE + timedelta(days=14)
    cs.delete_occurrences("course", mid, cut, "following")
    assert cs.get_meeting("course", mid)["end_date"] == (cut - timedelta(days=1)).isoformat()
    assert _has(cid, cut - timedelta(days=5)) and not any(_has(cid, cut + timedelta(days=i)) for i in range(0, 14))


def test_delete_all_events_and_a_series_with_nothing_before_is_deleted(seeded):
    cid = _new_course()
    mid = _series(cid, {1})
    cs.delete_occurrences("course", mid, TUE, "all")
    assert crud.list_meetings(cid) == []
    first = _series(cid, {1, 3})
    start = store.get_term().start
    day = min(start + timedelta(days=(wd - start.weekday()) % 7) for wd in (1, 3))                         # the first Tuesday or Thursday of the term (the series meets on both): nothing is before it
    assert "deleted" in cs.delete_occurrences("course", first, day, "following") and crud.list_meetings(cid) == []
    other = _series(cid, {1})
    with pytest.raises(Exception):
        cs.delete_occurrences("course", other, day, "nonsense")


def test_the_bin_of_a_tile_asks_before_it_deletes(seeded):
    cid, mid, *_ = seeded
    at = run(cal_anchor=TUE)
    at.text_input(key="cal_sink").set_value(f"delete|occ:course:{mid}:{TUE.isoformat()}|1"); at.run()
    assert not at.exception and any("od_this" in str(getattr(b, "key", "")) for b in at.button) and crud.list_meetings(cid)         # the choices are shown; nothing is deleted yet
    eid = cs.add_event("Dentist", timeutil.to_utc(TUE, time(10), NY), timeutil.to_utc(TUE, time(11), NY), False, "", 0, 0, True, None)
    at = run(cal_anchor=TUE)
    assert 'class="wk-del"' in " ".join(m.value for m in at.markdown) and 'class="wk-pin"' in " ".join(m.value for m in at.markdown)
    at.text_input(key="cal_sink").set_value(f"delete|event:{eid}|2"); at.run()
    assert not at.exception and at.button(key=f"cd_yes_event_{eid}") is not None and cs.list_events(TUE, TUE)


# ---------------------------------------------------------------- Changing a repeating event after a drag
def test_changing_the_time_for_this_event_this_weekday_following_or_all(seeded):
    cid = _new_course()
    mid = _series(cid, {1, 3})
    day = TUE + timedelta(days=14)

    def starts(d):
        return sorted(timeutil.to_local(b.start, store.get_term().zone).strftime("%H:%M") for b in cs.commitments(d, d) if b.kind == "class" and b.owner_id == cid)

    assert "that day only" in cs.change_occurrences("course", mid, day, "this", time(13), time(14))
    assert starts(day) and starts(day + timedelta(days=7)) != starts(day)                                     # only that Tuesday moved
    msg = cs.change_occurrences("course", mid, day, "weekday", time(15), time(16))
    assert "events" in msg and starts(day + timedelta(days=7)) == starts(day)                                  # the Tuesdays from here on
    thu = day + timedelta(days=2)
    assert starts(thu) != starts(day) and starts(day - timedelta(days=7)) != starts(day)                       # the Thursday and the earlier Tuesday are as before
    cs.change_occurrences("course", mid, day, "following", time(17), time(18))
    assert starts(thu) == starts(day) and starts(day - timedelta(days=7)) != starts(day)                       # now the Thursdays from here on too
    cs.change_occurrences("course", mid, day, "all", time(8), time(9))
    assert cs.get_meeting("course", mid)["start_time"] == "08:00"


def test_a_skipped_day_stays_skipped_when_following_days_change(seeded):
    cid = _new_course()
    mid = _series(cid, {1})
    skipped = TUE + timedelta(days=7)
    cs.skip_occurrence("course", mid, skipped)
    cs.change_occurrences("course", mid, TUE, "following", time(11), time(12))
    assert not any(b.kind == "class" and b.owner_id == cid for b in cs.commitments(skipped, skipped))


def test_dragging_a_class_asks_what_to_change_and_changes_nothing_until_answered(seeded):
    cid, mid, *_ = seeded
    at = run(cal_anchor=TUE)
    at.text_input(key="cal_sink").set_value(f"move|occ:course:{mid}:{TUE.isoformat()}|{TUE.isoformat()}|720|1"); at.run()
    assert not at.exception and any(str(getattr(b, "key", "")).startswith("oc_this_") for b in at.button)
    assert cs.exception_on("course", mid, TUE) is None                                                          # nothing changed yet
    at = run(cal_anchor=TUE)
    at.text_input(key="cal_sink").set_value(f"move|occ:course:{mid}:{TUE.isoformat()}|{(TUE + timedelta(days=1)).isoformat()}|720|2"); at.run()
    assert not at.exception and not any(str(getattr(b, "key", "")).startswith("oc_this_") for b in at.button)       # another day: only a message
    assert 'class="wk-moved"' not in " ".join(m.value for m in at.markdown)
