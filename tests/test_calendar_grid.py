"""Phase 6: the time grid of the planner calendar (pure drawing code, no Streamlit)."""
from datetime import date, datetime, time, timedelta, timezone

from planner import commitments as c
from planner import freetime as F
from planner import sessions as S
from planner import tasks as T
from planner import timeutil
from views import plan_grid as G

NY = "America/New_York"
MON = date(2026, 9, 7)


def at(day, hh=0, mm=0):
    return timeutil.to_utc(day, time(hh, mm), NY)


def block(kind, start, end, label="X", busy=True, owner=1, ref=1, color="", loc="", source=None, all_day=False, changed=False):
    return c.Block(start, end, kind, label, busy, owner, ref, color, loc, changed, all_day, source)


def items(blocks=(), sessions=(), tasks=None, day=MON, levels=None):
    return G.day_items(day, list(blocks), list(sessions), tasks or {}, {1: "#123456"}, levels or {}, timeutil.zone(NY))


def test_minutes_and_times_are_written_plainly():
    assert [G.fmt_minutes(m) for m in (0, 5, 60, 90, 125, -45, -120, -130)] == ["0 min", "5 min", "1 h", "1 h 30 min", "2 h 5 min", "-45 min", "-2 h", "-2 h 10 min"]
    assert G.hhmm(0) == "00:00" and G.hhmm(545) == "09:05" and G.hhmm(1440) == "24:00" and G.hhmm(2000) == "24:00" and G.hhmm(-5) == "00:00"


def test_a_block_becomes_an_item_in_local_minutes_with_its_colour():
    (it,) = items([block("class", at(MON, 9, 30), at(MON, 10, 45), "AE 6765", color="#abcdef", loc="Room 1")])
    assert (it.kind, it.title, it.start, it.end, it.color, it.sub, it.ref) == ("class", "AE 6765", 570, 645, "#abcdef", "Room 1", "")


def test_items_use_the_wall_clock_on_clock_change_days():
    spring = date(2026, 3, 8)
    (it,) = items([block("event", at(spring, 9), at(spring, 10), "Talk", source=None)], day=spring)
    assert (it.start, it.end) == (540, 600)                                       # 09:00-10:00 on the wall clock although the day has 23 hours


def test_a_block_across_midnight_is_cut_into_one_item_per_day():
    b = block("event", at(MON, 22), at(MON + timedelta(days=1), 1), "Night lab")
    (first,) = items([b], day=MON)
    (second,) = items([b], day=MON + timedelta(days=1))
    assert (first.start, first.end) == (22 * 60, 1440) and (second.start, second.end) == (0, 60)
    assert items([b], day=MON + timedelta(days=2)) == []


def test_all_day_blocks_are_not_on_the_grid_and_other_days_are_empty():
    assert items([block("event", at(MON), at(MON + timedelta(days=1)), "Conference", all_day=True)]) == []
    assert items([block("class", at(MON + timedelta(days=1), 9), at(MON + timedelta(days=1), 10))]) == []


def test_an_in_class_exam_replaces_the_class_on_the_grid():
    cls = block("class", at(MON, 9), at(MON, 10, 15), "AE 6765", owner=1)
    exam = block("event", at(MON, 9), at(MON, 10, 15), "Midterm 1", owner=1, source="legacy")
    other = block("class", at(MON, 13), at(MON, 14), "AE 6765", owner=1)
    got = items([cls, exam, other])
    assert [(i.kind, i.title) for i in got] == [("event", "Midterm 1"), ("class", "AE 6765")]


def test_only_events_made_in_the_planner_can_be_dragged():
    own = block("event", at(MON, 9), at(MON, 10), "Dentist", ref=4)
    old = block("event", at(MON, 11), at(MON, 12), "Midterm", ref=5, source="legacy")
    cls = block("class", at(MON, 13), at(MON, 14), "AE 6765", ref=6)
    assert [i.ref for i in items([own, old, cls])] == ["event:4", "", ""]


def test_sessions_carry_their_task_course_colour_and_cushion_level():
    t = T.Task(7, "HW 6", 1, "Homework", at(MON + timedelta(days=2), 17), 120)
    s = S.Session(12, 7, at(MON, 10), at(MON, 11, 30), S.AUTO)
    (it,) = items([], [s], {7: t}, levels={7: F.RED})
    assert (it.kind, it.title, it.color, it.ref, it.level, it.start, it.end, it.changed) == ("session", "HW 6", "#123456", "session:12", F.RED, 600, 690, False)
    manual = S.Session(13, 7, at(MON, 10), at(MON, 11), S.MANUAL)
    assert items([], [manual], {7: t})[0].changed is True                              # drawn solid: the student placed it
    assert items([], [s], {})[0].title == "Study" and items([], [s], {})[0].color == G.NEUTRAL


def test_lanes_put_overlapping_items_side_by_side():
    a, b, d = G.Item("class", "A", 540, 660, "#1"), G.Item("class", "B", 600, 700, "#2"), G.Item("class", "C", 720, 780, "#3")
    got = G.lanes([a, b, d])
    assert [(i.title, lane, count) for i, lane, count in got] == [("A", 0, 2), ("B", 1, 2), ("C", 0, 1)]
    assert G.lanes([]) == []


def test_the_grid_shows_the_usual_day_and_grows_for_early_or_late_items():
    assert G.hour_range({}) == (6, 24)
    assert G.hour_range({MON: [G.Item("class", "x", 480, 600, "#1")]}) == (6, 24)
    assert G.hour_range({MON: [G.Item("class", "x", 4 * 60, 600, "#1")]}) == (4, 24)


def test_block_html_has_what_the_drag_script_needs_only_for_editable_items():
    editable = G.Item("session", "HW 6", 600, 690, "#123456", "Study", "session:12", F.GREEN, False)
    html = G.block_html(editable, 0, 1, 6, lambda col: col)
    for part in ('data-ref="session:12"', 'data-start="600"', 'data-end="690"', 'data-edit="1"', "wk-session", "wk-resize", "10:00 - 11:30"):
        assert part in html
    fixed = G.block_html(G.Item("class", "AE 6765", 600, 690, "#123456"), 0, 1, 6, lambda col: col)
    assert "data-ref" not in fixed and "wk-resize" not in fixed
    commute = G.block_html(G.Item("commute", "Travel to Dentist", 880, 900, "#123456"), 0, 1, 6, lambda col: col)
    assert "wk-commute" in commute and "Travel to Dentist" in commute and "data-ref" not in commute


def test_block_html_escapes_titles():
    html = G.block_html(G.Item("class", "<script>x</script>", 600, 690, "#123456"), 0, 1, 6, lambda col: col)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_block_position_follows_the_hour_height():
    html = G.block_html(G.Item("class", "A", 9 * 60, 10 * 60, "#123456"), 0, 1, 6, lambda col: col)
    assert f"top:{3 * G.HOUR_PX:.1f}px" in html and f"height:{G.HOUR_PX - 2:.1f}px" in html


def test_grid_html_has_one_column_per_day_and_the_data_the_script_reads():
    days = [MON + timedelta(days=i) for i in range(2)]
    html = G.grid_html(days, MON, {MON: [G.Item("class", "A", 600, 660, "#123456")]}, {MON: [("Due HW", "#999999")]}, {days[1]}, 6, 24, lambda col: col, 12 * 60)
    assert html.count('class="wk-col') == 2 and 'style="--n:2"' in html and 'data-day="2026-09-07"' in html and 'data-day="2026-09-08"' in html
    assert 'data-lo="6"' in html and f'data-hour-px="{G.HOUR_PX}"' in html and f'data-snap="{G.SNAP_MINUTES}"' in html
    assert "holiday" in html and "wk-now" in html and "Due HW" in html
    one = G.grid_html(days[:1], MON, {}, {}, set(), 6, 24, lambda col: col)
    assert one.count('class="wk-col') == 1 and "wk-now" not in one
