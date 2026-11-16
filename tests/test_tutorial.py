"""The getting-started tutorial on Home: it starts for a student with no course, ticks its steps off from what they have done, can be skipped for good, and comes back from Settings > Help."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import crud, settings
from views import tutorial

pytestmark = pytest.mark.usefixtures("fresh_data")
APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(autouse=True)
def reset():
    settings.set_tutorial(mode=None, welcomed=None)
    data = settings._load()
    data.pop("tutorial", None)
    settings._save(data)


def home():
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Home"
    at.run()
    assert not at.exception
    return at


def test_a_new_student_gets_the_checklist_and_an_existing_one_does_not():
    at = home()
    assert settings.get_tutorial()["mode"] == "active" and any(s.value == "Getting Started" for s in at.subheader)
    assert at.button(key="tut_skip") is not None and at.button(key="tut_go_courses") is not None
    settings.set_tutorial(mode="dismissed")
    data = settings._load()
    data.pop("tutorial")
    settings._save(data)
    crud.add_course("AE 1", "A", "Fall 2026", 0, "Active")                                      # someone who already has data is not a new student
    again = home()
    assert settings.get_tutorial()["mode"] == "dismissed" and not any(s.value == "Getting Started" for s in again.subheader)


def test_skipping_hides_it_for_good_and_settings_brings_it_back():
    at = home()
    at.button(key="tut_skip").click().run()
    assert settings.get_tutorial()["mode"] == "dismissed" and not any(s.value == "Getting Started" for s in at.subheader)
    assert not any(s.value == "Getting Started" for s in home().subheader)                      # still gone on the next start
    st_page = AppTest.from_file(APP, default_timeout=90)
    st_page.session_state["page"] = "Settings"
    st_page.run()
    st_page.button(key="tut_again").click().run()
    assert settings.get_tutorial()["mode"] == "active" and st_page.session_state["page"] == "Home"


def test_a_step_button_goes_to_its_page_and_asks_for_its_window():
    at = home()
    at.button(key="tut_go_files").click().run()
    assert at.session_state["page"] == "Library"
    at2 = home()
    at2.button(key="tut_go_tasks").click().run()
    assert at2.session_state["page"] == "Calendar" and at2.session_state["cal_page"] == "Task List"


def test_the_steps_are_ticked_off_from_what_the_student_has_done():
    f = {"courses": 0, "terms": 0, "meetings": 0, "books": 0, "guides": 0, "tasks": 0, "sessions": 0}
    assert not any(tutorial.done_flags(f).values())
    crud.add_course("AE 1", "A", "Fall 2026", 0, "Active")
    got = tutorial.facts()
    assert got["courses"] == 1 and tutorial.done_flags(got)["courses"] and not tutorial.done_flags(got)["files"]
    assert tutorial.done_flags({**f, "courses": 2, "terms": 1, "meetings": 1, "books": 3, "guides": 1, "tasks": 4, "sessions": 5}) == {k: True for k, *_ in tutorial.STEPS}
    assert [k for k, *_ in tutorial.STEPS] == ["courses", "term", "meetings", "files", "guides", "tasks", "schedule"]


def test_the_tutorial_can_be_opened_again_from_home_after_it_was_skipped_or_finished():
    at = home()
    at.button(key="tut_skip").click().run()
    assert at.button(key="tut_reopen") is not None and not any(s.value == "Getting Started" for s in at.subheader)
    at.button(key="tut_reopen").click().run()
    assert settings.get_tutorial()["mode"] == "active" and any(s.value == "Getting Started" for s in at.subheader) and not at.exception
    crud.add_course("AE 1", "A", "Fall 2026", 0, "Active")                                       # a student who has data and never saw it can open it too
    settings.set_tutorial(mode="dismissed")
    again = home()
    assert again.button(key="tut_reopen") is not None


def test_the_guided_tour_covers_every_step_of_the_chain_and_each_page_it_opens_exists():
    keys = [k for k, *_ in tutorial.STEPS]
    assert [s["main"] for s in tutorial.TOUR if s["main"] not in (None, "done")] == [s["main"] for s in tutorial.TOUR if s["main"] in keys]
    assert set(keys) <= {s["main"] for s in tutorial.TOUR} and tutorial.TOUR[0]["main"] is None and tutorial.TOUR[-1]["main"] == "done"
    for s in tutorial.TOUR:
        assert s["page"] in ("Home", "Courses", "Calendar", "Library") and s["title"] and s["text"]
        assert not s["target"] or s["target"].split(":")[0] in ("css", "label", "button")
        assert s.get("open") in (None, "add_course", "new_term", "schedule", "add_file", "prompt")
    assert tutorial.OVERLAY.exists() and "__CFG__" in tutorial.OVERLAY.read_text(encoding="utf-8")


def test_the_tour_moves_with_next_and_back_opens_each_page_and_stops_with_skip():
    at = home()
    at.button(key="tut_tour").click().run()
    assert at.session_state["_tour"]["i"] == 0 and at.text_input(key="tour_sink") is not None
    at.text_input(key="tour_sink").input("next|1").run()
    assert at.session_state["_tour"]["i"] == 1 and at.session_state["page"] == "Courses" and not at.exception
    at.text_input(key="tour_sink").input("next|2").run()
    assert at.session_state["_tour"]["i"] == 2 and tutorial.TOUR[2]["open"] == "add_course" and not at.exception        # the window of the step is open on the page
    at.text_input(key="tour_sink").input("back|3").run()
    assert at.session_state["_tour"]["i"] == 1
    at.text_input(key="tour_sink").input("skip|4").run()
    assert "_tour" not in at.session_state and settings.get_tutorial()["mode"] == "dismissed"


def test_a_step_that_waits_for_the_student_moves_on_when_it_is_done():
    at = home()
    i = next(n for n, s in enumerate(tutorial.TOUR) if s.get("advance") == "courses")
    at.button(key="tut_go_courses").click().run()
    at.session_state["_tour"]["i"], at.session_state["_tour"]["applied"] = i, -1
    at.run()
    assert at.session_state["_tour"]["i"] == i and at.session_state["_tour"]["base"] == 0
    crud.add_course("AE 1", "A", "Fall 2026", 0, "Active")                                       # the student saved the course in the window
    at.run()
    assert at.session_state["_tour"]["i"] == i + 1 and at.session_state["page"] == "Calendar" and not at.exception


def test_the_overlay_is_taken_away_when_the_tour_ends():
    at = home()
    at.button(key="tut_tour").click().run()
    at.text_input(key="tour_sink").input("next|1").run()
    assert at.session_state["_tour_drawn"] is True
    at.text_input(key="tour_sink").input("done|2").run()
    assert "_tour" not in at.session_state and "_tour_drawn" not in at.session_state and not at.exception                  # the run that ends the tour sent the clean-up script
