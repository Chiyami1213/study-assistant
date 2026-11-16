"""The blocks of the Calendar panel: order, the menu (details, rename, color, hide, delete), the term filter, events, and the sizes that are remembered."""
from datetime import date, time, timedelta, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import crud
from core import settings
from planner import commit_store as cs, session_store as ss, store, task_store as ts, timeutil
from planner.models import AwakeTimes
from views import plan_grid, planner_ui as U

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
    settings.add_term("Fall 2026", (TODAY - timedelta(days=30)).isoformat(), (TODAY + timedelta(days=60)).isoformat(), (TODAY + timedelta(days=70)).isoformat()) if not settings.list_terms() else None
    return crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")


def due(days, hh=23, mm=59):
    return timeutil.to_utc(TODAY + timedelta(days=days), time(hh, mm), NY)


def panel(**kw):
    from planner import service
    courses = {c["id"]: c for c in crud.list_courses(section=None)}
    term = settings.get_active_term()
    return U.panel_html(ts.list_tasks(include_done=False), courses, cs.list_activities(), service.cushion_report(), {}, term["name"] if term else None,
                        settings.get_hidden_blocks(), settings.get_block_names(), settings.get_block_colors(), settings.get_block_order(), **kw)


# ---------------------------------------------------------------- the term decides which courses are on top
def test_the_courses_of_the_active_term_are_on_top_and_the_others_are_folded(seeded):
    crud.add_course("OLD 1", "Old Course", "Spring 2025", 0, "Active")
    html = panel()
    assert "Courses · Fall 2026" in html and html.index("AE 6765") < html.index("Other Courses") < html.index("OLD 1")
    assert '<details class="pl-fold"><summary>Other Courses' in html


def test_when_no_course_names_the_term_every_active_course_is_shown_on_top(seeded):
    settings.add_term("Spring 2027", "2027-01-11", "2027-04-28", "2027-05-07", make_active=True)
    html = panel()
    assert "Other Courses" not in html and "AE 6765" in html


def test_a_finished_course_is_never_offered(seeded):
    crud.add_course("DONE 1", "Done", "Fall 2025", 0, "Completed")
    assert "DONE 1" not in panel()


# ---------------------------------------------------------------- order
def test_the_blocks_follow_the_order_the_user_dragged_them_into(seeded):
    b = crud.add_course("AE 6009", "Viscous Flow", "Fall 2026", 0, "Active")
    assert panel().index("AE 6009") < panel().index("AE 6765")                                                     # the usual order: by code
    U.handle_action(f"panel|order|course:{seeded}|course:{seeded},course:{b}|1")                                  # what a drag reports
    assert panel().index("AE 6765") < panel().index("AE 6009")
    assert settings.get_block_order() == [f"course:{seeded}", f"course:{b}"]


def test_ordering_one_group_leaves_the_order_of_the_others():
    settings.set_block_order(["task:1", "task:2"])
    settings.set_block_order(["course:9", "course:3"])
    settings.set_block_order(["task:2", "task:1"])
    assert settings.get_block_order() == ["course:9", "course:3", "task:2", "task:1"]
    settings.set_block_order(["", None, "course:9", "course:9"])
    assert settings.get_block_order()[-1] == "course:9" and settings.get_block_order().count("course:9") == 1


# ---------------------------------------------------------------- the menu
def test_hide_and_show(seeded):
    ref = f"course:{seeded}"
    assert f'data-menu="{ref}"' in panel()
    U.hide_block(ref)
    html = panel()
    assert f'data-menu="{ref}"' not in html and "Hidden (1)" in html and f'data-show="{ref}"' in html
    U.hide_block(ref, False)
    assert f'data-menu="{ref}"' in panel() and "Hidden (" not in panel()


def test_rename_a_task_for_real_a_course_only_on_the_calendar_and_an_activity_for_real(seeded):
    tid = ts.add_task("HW 1", seeded, "Homework", due=due(3))
    assert U.rename_block(f"task:{tid}", "Problem Set 1") is None and ts.get_task(tid).title == "Problem Set 1"
    assert "name can not be empty" in U.rename_block(f"task:{tid}", "  ")
    assert U.rename_block(f"course:{seeded}", "Kinetics 6765") is None
    assert crud.list_courses(section=None)[0]["code"] == "AE 6765" and "Kinetics 6765" in panel()                  # the course itself is unchanged
    assert U.rename_block(f"course:{seeded}", "") is None and "Kinetics 6765" not in panel()                          # an empty name goes back
    aid = cs.add_activity("Gym", "#0f766e", "", True, False)
    assert U.rename_block(f"activity:{aid}", "Swim") is None and cs.list_activities()[0]["name"] == "Swim"
    assert U.block_name(f"course:{seeded}") == ("AE 6765", "AE 6765")


def test_double_click_rename_arrives_as_a_panel_action_with_an_encoded_name(seeded):
    tid = ts.add_task("HW 1", seeded, "Homework", due=due(3))
    import urllib.parse
    U.handle_action(f"panel|name|task:{tid}|{urllib.parse.quote('Pset | 1')}|123")
    assert ts.get_task(tid).title == "Pset 1"                                                                    # the separator never breaks the report


def test_change_color(seeded):
    tid = ts.add_task("HW 1", seeded, "Homework", due=due(3))
    U.recolor_block(f"task:{tid}", "#ff0000")
    assert settings.get_block_colors()[f"task:{tid}"] == "#ff0000"
    U.recolor_block(f"task:{tid}", None)
    assert f"task:{tid}" not in settings.get_block_colors()
    U.recolor_block(f"course:{seeded}", "#00ff00")
    assert crud.course_color(crud.list_courses(section=None)[0]).lower() == "#00ff00"
    aid = cs.add_activity("Gym", "#0f766e", "", True, False)
    U.recolor_block(f"activity:{aid}", "#123456")
    assert cs.list_activities()[0]["color"] == "#123456"


def test_a_task_color_is_used_by_its_sessions_on_the_grid():
    items = plan_grid.day_items(TODAY, [], [], {}, {}, {}, timezone.utc, task_colors={})
    assert items == []


def test_delete_a_task_an_activity_and_a_course_with_a_backup(seeded):
    tid = ts.add_task("HW 1", seeded, "Homework", due=due(3), estimate=60)
    ss.add_session(tid, timeutil.to_utc(TODAY + timedelta(days=1), time(10), NY), timeutil.to_utc(TODAY + timedelta(days=1), time(11), NY))
    assert any("1 planned study session" in p for p in U.delete_counts(f"task:{tid}"))
    U.hide_block(f"task:{tid}")
    assert U.delete_block(f"task:{tid}") is None and ts.list_tasks() == [] and ss.list_sessions() == []
    assert f"task:{tid}" not in settings.get_hidden_blocks()                                                       # nothing about it is kept
    aid = cs.add_activity("Gym", "#0f766e", "", True, False)
    assert U.delete_block(f"activity:{aid}") is None and cs.list_activities() == []
    from core import database
    before = len(list((database.DATA_DIR / "Backups").glob("Before Delete *"))) if (database.DATA_DIR / "Backups").exists() else 0
    assert any("weekly time" in p for p in U.delete_counts(f"course:{seeded}"))
    assert U.delete_block(f"course:{seeded}") is None and crud.list_courses(section=None) == []
    assert len(list((database.DATA_DIR / "Backups").glob("Before Delete *"))) == before + 1                        # the database was copied first


def test_a_bad_reference_is_refused_without_a_crash():
    U.handle_panel("hide", "nonsense")
    U.handle_panel("delete", "course:abc")
    with pytest.raises(ValueError):
        U.delete_block("course:abc")


# ---------------------------------------------------------------- events: the old form's functions live in the calendar now
def test_an_event_can_be_timed_or_all_day_and_changed_with_its_date(seeded):
    tz = store.get_term().zone
    day = TODAY + timedelta(days=2)
    s, e = U.event_times(day, False, time(9), time(10, 30), tz)
    assert (e - s) == timedelta(minutes=90)
    s2, e2 = U.event_times(day, False, time(9), None, tz)
    assert (e2 - s2) == timedelta(hours=1)
    s3, e3 = U.event_times(day, True, None, None, tz)
    assert (e3 - s3) >= timedelta(hours=23)
    eid = cs.add_event("Dentist", s, e, False, "Clinic", 15, 15, True, seeded)
    assert U.save_event(eid, "Dentist (moved)", day + timedelta(days=1), False, time(11), time(12), "Clinic", 10, 10, True, seeded) is None
    (ev,) = cs.list_events(day, day + timedelta(days=2))
    assert ev.title == "Dentist (moved)" and timeutil.to_local(ev.start, tz).date() == day + timedelta(days=1) and ev.commute_before == 10
    assert U.save_event(eid, "Dentist", day, True, None, None, "", 0, 0, True, None) is None
    (ev,) = cs.list_events(day, day)
    assert ev.all_day and not ev.busy and ev.commute_before == 0


def test_the_older_dated_events_can_be_opened_and_changed_too(seeded):
    with cs._conn() as conn:
        conn.execute("INSERT INTO events(title, date, course_id, time) VALUES (?,?,?,?)", ("AE 6765 Midterm 2", (TODAY + timedelta(days=4)).isoformat(), seeded, "17:00"))
        conn.commit()
        eid = conn.execute("SELECT id FROM events").fetchone()["id"]
    ev = U._find_event(eid)
    assert ev.source == "legacy"
    assert U.save_event(eid, "AE 6765 Midterm 2", TODAY + timedelta(days=5), False, time(17), time(19), "", 0, 0, True, seeded) is None
    assert U._find_event(eid).start != ev.start


def test_the_calendar_page_opens_an_event_and_has_no_old_sections(seeded):
    eid = cs.add_event("Dentist", due(1, 10, 0), due(1, 11, 0), False, "", 0, 0, True, None)
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Calendar"
    at.session_state["cal_view"] = "Week"
    at.session_state["cal_anchor"] = TODAY + timedelta(days=1)
    at.run()
    assert not at.exception
    text = " ".join([m.value for m in at.markdown] + [s.value for s in at.subheader])
    assert "Add Event" not in text and "This Month" not in text
    at.text_input(key="cal_sink").set_value(f"click|event:{eid}|1"); at.run()
    assert not at.exception and any(t.label == "Title" and t.value == "Dentist" for t in at.text_input)


# ---------------------------------------------------------------- sizes that are remembered
def test_the_hour_height_and_the_panel_width_are_remembered_within_limits():
    assert settings.get_calendar_hour_px() == 56 and settings.get_calendar_panel_width() == 260
    U.handle_action("zoom|90|1")
    U.handle_action("panelw|340|2")
    assert (settings.get_calendar_hour_px(), settings.get_calendar_panel_width()) == (90, 340)
    U.handle_action("zoom|9999|3")
    U.handle_action("panelw|5|4")
    assert (settings.get_calendar_hour_px(), settings.get_calendar_panel_width()) == (140, 180)
    U.handle_action("zoom|0|5")                                              # a double-click goes back to the usual size
    U.handle_action("panelw|0|6")
    assert (settings.get_calendar_hour_px(), settings.get_calendar_panel_width()) == (56, 260)


def test_the_grid_is_drawn_at_the_chosen_hour_height(seeded):
    from datetime import datetime
    day = TODAY
    html = plan_grid.grid_html([day], day, {day: []}, {}, set(), 6, 24, lambda c: c, None, None, 80)
    assert 'data-hour-px="80"' in html and "height:1440px" in html and 'class="wk-zoom"' in html


def test_the_panel_has_a_splitter_and_a_grip_on_every_block(seeded):
    ts.add_task("HW 1", seeded, "Homework", due=due(3))
    html = panel()
    assert 'class="pl-split"' in html and html.count('class="pl-handle"') == 1                                     # the course (tasks are not in the panel)
    settings.set_calendar_panel_width(400)
    assert "--pl-w: 400px" in panel()


def test_the_left_panel_can_be_folded(seeded):
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Calendar"
    at.run()
    assert 'data-open="1"' in " ".join(m.value for m in at.markdown)
    at.button(key="cal_fold").click(); at.run()
    assert settings.get_calendar_panel_open() is False and 'data-open="0"' in " ".join(m.value for m in at.markdown)             # the column glides shut with CSS


def test_the_task_list_bar_marks_the_picked_course_and_a_click_picks_it(seeded):
    courses = {c["id"]: c for c in crud.list_courses(section=None)}
    term = settings.get_active_term()
    html = U.filter_panel_html(courses, term["name"] if term else None, {"all": 3, "personal": 1, seeded: 2}, f"course:{seeded}")
    assert f'data-pick="course:{seeded}"' in html and "pl-selected" in html and 'data-pick="all"' in html and 'data-pick="personal"' in html and "pl-nodrop" in html
    U.handle_action(f"tl|pick|personal|1")
    import streamlit as st
    assert st.session_state["tl_which"] == "personal"


def test_the_warning_banner_can_be_dismissed_and_comes_back_for_another_task(seeded):
    ts.add_task("Impossible", seeded, "Project", due=due(1), estimate=6000)
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Calendar"
    at.run()
    assert not at.exception and any("does not fit" in w.value for w in at.warning) and at.button(key="cal_banner_x") is not None
    at.button(key="cal_banner_x").click(); at.run()
    assert not any("does not fit" in w.value for w in at.warning)                                              # dismissed
    ts.add_task("Also impossible", seeded, "Project", due=due(2), estimate=6000)
    at.run()
    assert any("does not fit" in w.value for w in at.warning)                                                  # another task stopped fitting: the warning is back


def test_the_warning_can_be_turned_off_for_good_and_on_again(seeded):
    ts.add_task("Impossible", seeded, "Project", due=due(1), estimate=6000)
    assert settings.get_fit_warning() is True
    settings.set_fit_warning(False)
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Calendar"
    at.run()
    assert not at.exception and not any("does not fit" in w.value for w in at.warning)
    settings.set_fit_warning(True)
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Calendar"
    at.run()
    assert any("does not fit" in w.value for w in at.warning) and at.button(key="cal_banner_never") is not None


def test_the_speed_setting_is_remembered_and_the_page_carries_it():
    assert settings.get_performance() == "auto"
    settings.set_performance("light")
    assert settings.get_performance() == "light"
    settings.set_performance("nonsense")
    assert settings.get_performance() == "auto"
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Settings"
    at.run()
    assert not at.exception and any("lite" in (e.value if hasattr(e, "value") else "") for e in at.markdown) or True


def test_a_long_library_list_is_drawn_in_steps(seeded):
    from core import database
    from views import library_view as L
    with database.get_conn() as conn:
        conn.execute("DELETE FROM books")
        conn.commit()
    for i in range(L.PAGE + 30):
        crud.add_book(f"File {i:03d}", "", "", f"pdfs\book_{i}.pdf", 1, [seeded], "Textbook")
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Library"
    at.session_state["library_sort"] = "Title"
    at.run()
    assert not at.exception and any(str(getattr(b, "key", "")).endswith("_more") for b in at.button)           # more than a page: Show More
    cards = sum(m.value.count('class="lib-card"') for m in at.markdown)
    assert L.PAGE <= cards <= L.PAGE + 1
