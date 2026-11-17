"""Color themes (Settings > Appearance): Graphite is the original look and renders exactly as before; the other themes recolor the surfaces and the buttons."""
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import settings

pytestmark = pytest.mark.usefixtures("fresh_data")
APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(autouse=True)
def graphite():
    settings.set_color_theme("graphite")
    yield
    settings.set_color_theme("graphite")


def names(palette):
    return set(re.findall(r"--([a-z0-9-]+):", palette))


def test_four_themes_graphite_first_and_a_bad_choice_is_graphite():
    assert list(settings.COLOR_THEMES) == ["graphite", "ocean", "forest", "plum"] and settings.get_color_theme() == "graphite"
    settings.set_color_theme("ocean")
    assert settings.get_color_theme() == "ocean"
    settings.set_color_theme("not a theme")
    assert settings.get_color_theme() == "graphite"


def test_graphite_renders_exactly_as_it_always_did():
    assert settings.css_vars("dark", "graphite") == ":root{" + settings.PALETTES["dark"] + "color-scheme:dark;}" + settings.OVERRIDE
    assert settings.css_vars("light") == ":root{" + settings.PALETTES["light"] + "color-scheme:light;}" + settings.OVERRIDE
    assert settings.css_vars("device") == ":root{" + settings.PALETTES["dark"] + "}@media (prefers-color-scheme: light){:root{" + settings.PALETTES["light"] + "}}"


@pytest.mark.parametrize("key", ["ocean", "forest", "plum"])
def test_every_other_theme_defines_the_same_colors_and_changes_surfaces_and_buttons(key):
    name, dark, light, primary = settings.COLOR_THEMES[key]
    assert names(dark) == names(settings.PALETTES["dark"]) and names(light) <= names(settings.PALETTES["light"])
    for mode in ("dark", "light", "device"):
        css = settings.css_vars(mode, key)
        assert f"--primary:{primary}" in css and settings.OVERRIDE in css
        assert (dark.split("--bg:")[1].split(";")[0] in css) == (mode != "light")                              # the dark surfaces are in Dark and in the device's setting, not in Light
        assert light.split("--accent:")[1].split(";")[0] in settings.css_vars("light", key)
    assert settings.css_vars("light", key) != settings.css_vars("light", "graphite")


def test_the_settings_page_offers_the_four_themes_and_a_click_chooses_one():
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Settings"
    at.run()
    assert not at.exception and all(at.button(key=f"theme_{k}") is not None for k in settings.COLOR_THEMES)
    at.button(key="theme_plum").click().run()
    assert settings.get_color_theme() == "plum" and not at.exception
    assert any("theme-card on" in m.value for m in at.markdown)                                                  # the chosen card has its ring
