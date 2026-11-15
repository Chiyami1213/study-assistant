"""Back and Forward return to the place the student was, also inside a page (the Task List, a Library tile), in the order the places were visited."""
import pytest
import streamlit as st

import navigation as N


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    monkeypatch.setattr(st, "rerun", lambda: None)                                          # a rerun is not needed to look at what was restored
    st.session_state["page"] = "Home"
    yield
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def visit(page, **state):
    st.session_state["page"] = page
    st.session_state.update(state)
    return N.record_view()


def test_back_and_forward_follow_the_order_of_the_visits():
    visit("Home"); visit("Courses"); visit("Library"); visit("Settings")
    N.go_back(); assert st.session_state["page"] == "Library"; N.record_view()
    N.go_back(); assert st.session_state["page"] == "Courses"; N.record_view()
    N.go_forward(); assert st.session_state["page"] == "Library"; N.record_view()
    N.go_forward(); assert st.session_state["page"] == "Settings"; N.record_view()
    assert N.go_forward() is False                                                           # nothing further


def test_a_new_visit_after_going_back_clears_forward():
    visit("Home"); visit("Courses"); visit("Library")
    N.go_back(); N.record_view()
    visit("Settings")
    assert st.session_state["nav_forward"] == [] and [v[0] for v in st.session_state["nav_history"]] == ["Home", "Courses", "Settings"]


def test_back_returns_to_the_task_list_and_not_just_the_calendar_page():
    visit("Calendar", cal_page="Calendar"); visit("Calendar", cal_page="Task List"); visit("Library")
    N.go_back(); N.record_view()
    assert st.session_state["page"] == "Calendar" and st.session_state["cal_page"] == "Task List"
    N.go_back(); N.record_view()
    assert st.session_state["cal_page"] == "Calendar"
    N.go_forward(); assert st.session_state["cal_page"] == "Task List"


def test_back_returns_to_the_library_tile_and_its_sort():
    visit("Library", _lib={"sort": "Type", "tile": None, "inner": {}, "desc": True, "view": "Cards"})
    st.session_state["_lib"] = {"sort": "Type", "tile": "Homework", "inner": {"Type": "Date Added"}, "desc": True, "view": "Cards"}; N.record_view()
    visit("Courses")
    N.go_back(); N.record_view()
    lib = st.session_state["_lib"]
    assert st.session_state["page"] == "Library" and lib["tile"] == "Homework" and lib["inner"]["Type"] == "Date Added"
    N.go_back(); N.record_view()
    assert st.session_state["_lib"]["tile"] is None                                          # the overview of the types, before the tile was opened


def test_one_run_does_not_record_the_same_place_twice_and_the_history_is_capped():
    for _ in range(3):
        visit("Home")
    assert len(st.session_state["nav_history"]) == 1
    for i in range(80):
        visit("Calendar", cal_page="Calendar" if i % 2 else "Task List")
    assert len(st.session_state["nav_history"]) == 50


def test_views_stored_by_an_older_version_still_restore():
    st.session_state["nav_history"] = [("Home", None, None), ("Courses", 3, None)]
    st.session_state["page"] = "Courses"
    N.go_back()
    assert st.session_state["page"] == "Home" and st.session_state["open_course"] is None
