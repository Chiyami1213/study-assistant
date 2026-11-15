"""Settings: the time zone list shows UTC offsets, and the bar at the top has a link for every section."""
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import available_timezones

import pytest
from streamlit.testing.v1 import AppTest

from planner import store, timeutil
from views import settings_view

pytestmark = pytest.mark.usefixtures("fresh_data")
APP = str(Path(__file__).resolve().parent.parent / "app.py")
WINTER = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
SUMMER = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)


def test_utc_offsets_as_text():
    ny = "America/New_York"
    assert timeutil.utc_offset_text(ny, WINTER) == "UTC-05:00" and timeutil.utc_offset_text(ny, SUMMER) == "UTC-04:00"      # daylight saving
    assert timeutil.utc_offset_text("Asia/Kolkata", WINTER) == "UTC+05:30"
    assert timeutil.utc_offset_text("Asia/Kathmandu", WINTER) == "UTC+05:45"
    assert timeutil.utc_offset_text("UTC", WINTER) == "UTC+00:00"
    assert timeutil.utc_offset_text("Pacific/Kiritimati", WINTER) == "UTC+14:00"
    assert timeutil.utc_offset_text("America/New_York").startswith("UTC-0")                                                  # now


def test_zone_labels_show_the_offset_and_the_short_name_when_there_is_one():
    assert timeutil.zone_label("America/New_York", WINTER) == "America/New_York (UTC-05:00, EST)"
    assert timeutil.zone_label("America/New_York", SUMMER) == "America/New_York (UTC-04:00, EDT)"
    assert timeutil.zone_label("Asia/Dubai", WINTER) == "Asia/Dubai (UTC+04:00)"                      # its short name is just "+04": left out
    assert timeutil.zone_label("Europe/Paris", WINTER) == "Europe/Paris (UTC+01:00, CET)"


def test_every_zone_has_a_label():
    for name in available_timezones():
        label = timeutil.zone_label(name, WINTER)
        assert label.startswith(name + " (UTC") and label.endswith(")"), label


def test_zones_are_listed_from_west_to_east():
    names = ["Asia/Tokyo", "America/Los_Angeles", "Europe/London", "America/New_York", "Asia/Kolkata", "Pacific/Honolulu"]
    assert timeutil.zones_by_offset(names, WINTER) == ["Pacific/Honolulu", "America/Los_Angeles", "America/New_York", "Europe/London", "Asia/Kolkata", "Asia/Tokyo"]
    ordered = timeutil.zones_by_offset(available_timezones(), WINTER)
    offsets = [WINTER.astimezone(timeutil.zone(n)).utcoffset() for n in ordered]
    assert offsets == sorted(offsets)


def _run():
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Settings"
    at.run()
    return at


def test_the_planner_time_zone_box_shows_offsets_and_saves_the_name():
    at = _run()
    box = at.selectbox(key="planner_tz")
    assert any(" (UTC" in str(o) for o in box.options) and box.value in available_timezones()
    shown = [o for o in box.options if "America/Chicago" in str(o)]
    assert shown and "UTC-0" in shown[0]
    box.set_value("America/Chicago")
    at.button(key="planner_save").click(); at.run()
    assert store.get_timezone() == "America/Chicago" and not at.exception


def test_the_jump_bar_links_to_every_section_heading():
    at = _run()
    bar = next(m.value for m in at.markdown if "set-nav" in m.value and "<nav" in m.value)
    for name in settings_view.SECTIONS:
        slug = name.lower().replace(" ", "-")
        assert f'href="#{slug}"' in bar and f'data-jump="{slug}"' in bar and f">{name}<" in bar
    headings = [h.value for h in at.header]
    assert headings == settings_view.SECTIONS                                      # the bar lists the sections in the order they appear
    assert not at.exception
