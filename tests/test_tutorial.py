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
