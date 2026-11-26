"""The native (Qt) interface: its pure parts (colors, the eye rest logic) and a smoke test of the window drawn without a screen."""
import os

import pytest

from qtui import theme
from qtui.eyerest import EyeRest

CFG = {"rest_seconds": 20, "sound": False, "max_skips": 2, "required_minutes": 5}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_the_palette_follows_the_appearance_and_the_color_theme():
    assert theme.resolve_mode("light", True) == "light" and theme.resolve_mode("dark", False) == "dark"
    assert theme.resolve_mode("device", True) == "dark" and theme.resolve_mode("device", False) == "light"
    dark, light = theme.colors("dark", "ocean"), theme.colors("light", "ocean")
    assert dark["mode"] == "dark" and light["mode"] == "light" and dark["bg"] != light["bg"]
    assert theme.colors("dark", "plum")["primary"] != theme.colors("dark", "forest")["primary"]
    sheet = theme.stylesheet(dark)
    assert dark["bg"] in sheet and dark["primary"] in sheet and "QPushButton#nav" in sheet


def test_the_eye_rest_asks_after_twenty_minutes_and_forces_a_rest_after_too_many_skips():
    clock = Clock()
    er = EyeRest(CFG, clock)
    assert er.tick() is None
    clock.t += 1199
    assert er.tick() is None
    clock.t += 2
    assert er.tick() == "ask" and er.tick() is None                  # one offer at a time
    assert er.refuse() is False                                       # first skip
    clock.t += 1201
    assert er.tick() == "ask"
    assert er.refuse() is True                                        # the second skip in a row: a warning
    clock.t += 1201
    assert er.tick() == "force" and er.forced_left() == 300           # the third reminder is a required rest
    clock.t += 301
    assert er.forced_left() == 0
    er.end_force()
    assert er.refused == 0 and er.tick() is None


def test_taking_a_rest_forgets_the_skips_and_restarts_the_twenty_minutes():
    clock = Clock()
    er = EyeRest(CFG, clock)
    clock.t += 1201
    assert er.tick() == "ask"
    er.refuse()
    clock.t += 600
    assert er.rest_now() is True                                      # Rest Now: counts as the eye rest
    assert er.refused == 0 and er.next == clock.t + 1200
    er.finished()
    clock.t += 1199
    assert er.tick() is None                                          # the 20 minutes started again at that moment
    clock.t += 2
    assert er.tick() == "ask"


def test_rest_now_cannot_replace_a_required_rest():
    clock = Clock()
    er = EyeRest({**CFG, "max_skips": 0}, clock)
    clock.t += 1201
    assert er.tick() == "force"
    assert er.rest_now() is False


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_the_window_has_the_menu_the_settings_page_and_rest_now(qapp, fresh_data):
    from core import crud, settings
    from qtui.window import MainWindow
    cid = crud.add_course("QT 1", "Native", "Fall 2026", 0, "Active")
    w = MainWindow(use_server=False)
    w.show()
    qapp.processEvents()
    assert set(w.sidebar.buttons) == {"Home", "Calendar", "Library", "Note Reader", "Courses", "Rest Now", "Settings"}
    w.choose_course(cid)
    assert w.page == "Courses" and w.course == cid and cid in w.sidebar.courses.course_buttons and w.sidebar.courses.isVisibleTo(w.sidebar)
    w.show_page("Settings")
    assert w.stack.currentWidget() is w.settings_page
    # a change on the Settings page is saved
    from PySide6.QtWidgets import QSpinBox
    spins = w.settings_page.findChildren(QSpinBox)
    assert len(spins) == 4                                            # rest length, skips, required rest, seconds per question
    spins[3].setValue(9)
    assert settings.get_quiz()["speed_seconds"] == 9
    settings.set_quiz(speed_seconds=5)
    w.settings_page._set_theme("plum")
    assert settings.get_color_theme() == "plum"
    settings.set_color_theme("graphite")
    # Rest Now starts the rest card at once and the reminder starts again
    w.rest.rest_now()
    assert w.rest.mode == "rest" and w.rest.overlay.isVisibleTo(w) and w.rest.logic.refused == 0
    w.close()
