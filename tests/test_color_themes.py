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
    assert settings.css_vars("dark", "graphite") == ":root{" + settings.PALETTES["dark"] + "color-scheme:dark;}" + settings.OVERRIDE + settings.SWITCH_CSS
    assert settings.css_vars("light") == ":root{" + settings.PALETTES["light"] + "color-scheme:light;}" + settings.OVERRIDE + settings.SWITCH_CSS
    assert settings.css_vars("device") == ":root{" + settings.PALETTES["dark"] + "}@media (prefers-color-scheme: light){:root{" + settings.PALETTES["light"] + "}}" + settings.SWITCH_CSS      # only the off switch's track is new


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


def test_every_theme_card_shows_four_color_tiles():
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Settings"
    at.run()
    cards = [m.value for m in at.markdown if "<div class='theme-card" in m.value]
    assert len(cards) == len(settings.COLOR_THEMES) and all(c.count("<span") == 4 for c in cards)


@pytest.mark.parametrize("mode", ["light", "dark", "device"])
@pytest.mark.parametrize("theme", list(settings.COLOR_THEMES))
def test_the_off_switch_has_a_visible_track_in_every_appearance_and_theme(mode, theme):
    assert settings.SWITCH_CSS in settings.css_vars(mode, theme)


def test_the_settings_page_hands_the_browser_every_theme_for_an_instant_repaint():
    import json
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Settings"
    at.run()
    assert not at.exception
    from views import settings_view
    script = settings_view._LIVE_THEME_JS
    assert "sa-theme-live" in script and "__MAP__" in script and "__KEYS__" in script
    css = {k: settings.css_vars(settings.get_appearance(), k) for k in settings.COLOR_THEMES}
    assert len(json.dumps(css)) < 60000 and len(set(css.values())) == 4                                      # four different looks, a small script


@pytest.mark.parametrize("key", ["ocean", "forest", "plum"])
def test_a_theme_is_visible_in_light_too_not_only_in_its_accent(key):
    base = settings.theme_colors("graphite", "light")
    mine = settings.theme_colors(key, "light")
    assert mine["bg"] != base["bg"] and mine["card"] != base["card"] and mine["accent"] != base["accent"]        # the page and the cards are tinted
    assert settings.theme_colors(key, "dark")["bg"] != settings.theme_colors("graphite", "dark")["bg"]
    assert settings.theme_colors("graphite", "light")["bg"] == "#ffffff"                                          # Graphite stays as it was


def test_the_whole_theme_card_is_the_button_not_only_its_name():
    css = (Path(APP).parent / "app.py").read_text(encoding="utf-8")
    assert '.st-key-color_themes [class*="st-key-theme_"] {{position: absolute !important; inset: 0;' in css      # the button covers the card: a click on the colors chooses the theme
