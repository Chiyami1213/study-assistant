"""The time grid of the planner calendar (Week, 2 Days, Day): turns the planner's blocks and sessions into drawn items and into HTML. No Streamlit here, so it can be tested.

Everything is drawn in the term's time zone. An item is one stretch of one local day, in minutes from midnight of the wall clock; a block that crosses midnight becomes
one item on each day. Study sessions are drawn dashed and light, classes and events solid, travel time hatched."""
import html
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from planner import freetime, timeutil

HOUR_PX = 56
DAY_START_HOUR, DAY_END_HOUR = 6, 24
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
LEVEL_COLORS = {freetime.GREEN: "#2f9e5f", freetime.YELLOW: "#d9a400", freetime.RED: "#e0392b"}
ACTIVITY_COLOR, EVENT_COLOR, NEUTRAL = "#0f766e", "#6b7280", "#6b7280"
SNAP_MINUTES = 15


@dataclass(frozen=True)
class Item:
    kind: str                 # "class", "activity", "event", "commute", "session"
    title: str
    start: int                # minutes from local midnight
    end: int
    color: str
    sub: str = ""             # a second line (location, the task of a session ...)
    ref: str = ""             # "session:12" or "event:4": what a drag or a click acts on; "" when it can not be edited
    level: str = ""           # the cushion level of a session's task
    changed: bool = False
    progress: float = 0.0     # how much of a session was used (0 to 1)


def fmt_minutes(minutes):
    """90 -> '1 h 30 min', -45 -> '-45 min'."""
    sign = "-" if minutes < 0 else ""
    m = abs(int(minutes))
    h, rest = divmod(m, 60)
    if h and rest:
        return f"{sign}{h} h {rest} min"
    if h:
        return f"{sign}{h} h"
    return f"{sign}{rest} min"


def hhmm(minutes):
    minutes = max(0, min(24 * 60, int(minutes)))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _clip(day, start, end, tz):
    """The part of the UTC span start..end that falls on the local day, as (start minute, end minute), or None."""
    lo, hi = timeutil.day_bounds_utc(day, tz)
    s, e = max(start, lo), min(end, hi)
    if e <= s:
        return None

    def minute(moment):
        local = timeutil.to_local(moment, tz)
        return (24 * 60) if local.date() > day else local.hour * 60 + local.minute

    return minute(s), minute(e)


def day_items(day, blocks, sessions, tasks, course_colors, levels, tz, progress=None):
    """The items of one local day. `tasks`: {task id: Task}; `course_colors`: {course id: color}; `levels`: {task id: cushion level}."""
    items = []
    exam_starts = {(b.owner_id, _clip(day, b.start, b.end, tz)[0]) for b in blocks
                   if b.kind == "event" and b.source == "legacy" and not b.all_day and _clip(day, b.start, b.end, tz)}
    for b in blocks:
        if b.all_day:
            continue
        span = _clip(day, b.start, b.end, tz)
        if not span:
            continue
        if b.kind == "class" and (b.owner_id, span[0]) in exam_starts:
            continue                                                       # an in-class exam replaces the class on the grid
        if b.kind == "class":
            color = b.color or course_colors.get(b.owner_id, NEUTRAL)
        elif b.kind == "activity":
            color = b.color or ACTIVITY_COLOR
        elif b.kind == "commute":
            color = course_colors.get(b.owner_id, EVENT_COLOR)
        else:
            color = course_colors.get(b.owner_id, EVENT_COLOR)
        ref = f"event:{b.ref_id}" if b.kind == "event" and b.source != "legacy" else ""
        items.append(Item(b.kind, b.label, span[0], span[1], color, b.location or "", ref, "", b.changed))
    for s in sessions:
        span = _clip(day, s.start, s.end, tz)
        if not span:
            continue
        task = tasks.get(s.task_id)
        color = course_colors.get(task.course_id, NEUTRAL) if task else NEUTRAL
        items.append(Item("session", task.title if task else "Study", span[0], span[1], color, "Study", f"session:{s.id}", levels.get(s.task_id, ""), s.source == "manual", (progress or {}).get(s.id, 0.0)))
    items.sort(key=lambda i: (i.start, i.end, i.kind, i.title))
    return items


def free_items(day, intervals, tz):
    """Free-time areas of one local day as items (kind "free", the length as its title), from the free intervals (UTC pairs)."""
    out = []
    for s, e in intervals:
        span = _clip(day, s, e, tz)
        if span and span[1] - span[0] >= 15:
            out.append(Item("free", fmt_minutes(span[1] - span[0]), span[0], span[1], "#7c6aff"))
    return out


def lanes(items):
    """Side-by-side lanes for items that overlap: [(item, lane, lanes in its cluster)]."""
    placed, cluster, cluster_end = [], [], -1
    for it in items:
        if cluster and it.start >= cluster_end:
            placed += _finish(cluster)
            cluster, cluster_end = [], -1
        cluster.append(it)
        cluster_end = max(cluster_end, it.end)
    return placed + _finish(cluster)


def _finish(cluster):
    ends, out = [], []
    for it in cluster:
        for i, e in enumerate(ends):
            if it.start >= e:
                ends[i] = it.end
                out.append((it, i))
                break
        else:
            ends.append(it.end)
            out.append((it, len(ends) - 1))
    return [(it, lane, len(ends)) for it, lane in out]


def hour_range(items_by_day):
    """The first and last hour the grid shows: the usual day, widened when something falls outside it."""
    starts = [i.start for items in items_by_day.values() for i in items if i.kind != "free"]
    ends = [i.end for items in items_by_day.values() for i in items]
    lo = min(DAY_START_HOUR, min(starts) // 60) if starts else DAY_START_HOUR
    hi = min(24, max(DAY_END_HOUR, -(-max(ends) // 60))) if ends else DAY_END_HOUR
    return lo, hi


def block_html(it, lane, count, lo, darken):
    top = (it.start - lo * 60) * HOUR_PX / 60
    height = max((it.end - it.start) * HOUR_PX / 60 - 2, 18)
    width = f"left:calc({lane * 100 / count}% + 2px);width:calc({100 / count}% - 4px);"
    edit = ' data-edit="1"' if it.ref else ""
    attrs = f' data-ref="{html.escape(it.ref)}" data-start="{it.start}" data-end="{it.end}"{edit}' if it.ref else ""
    time_text = f"{hhmm(it.start)} - {hhmm(it.end)}"
    sub = f'<div class="wk-loc">{html.escape(it.sub)}</div>' if it.sub and it.kind != "commute" else ""
    handle = '<div class="wk-resize" title="drag to change the length"></div>' if it.ref else ""
    if it.kind == "session":
        dot = f'<span class="wk-dot" style="background:{LEVEL_COLORS.get(it.level, NEUTRAL)}" title="cushion: {it.level or "none"}"></span>' if it.level else ""
        style = f"top:{top:.1f}px;height:{height:.1f}px;{width}border-color:{it.color};background:{it.color}2e"
        used = f'<div class="wk-used" style="width:{min(100, round(it.progress * 100))}%" title="{round(it.progress * 100)}% of this session used"></div>' if it.progress > 0 else ""
        return (f'<div class="wk-block wk-session{" wk-manual" if it.changed else ""}" style="{style}"{attrs}>{dot}<div class="wk-time">{time_text}</div>'
                f'<div class="wk-code">{html.escape(it.title)}</div>{sub}{used}{handle}</div>')
    if it.kind == "commute":
        style = f"top:{top:.1f}px;height:{height:.1f}px;{width}--c:{it.color}"
        return f'<div class="wk-block wk-commute" style="{style}"><div class="wk-time">{html.escape(it.title)}</div></div>'
    color = it.color
    style = f"top:{top:.1f}px;height:{height:.1f}px;{width}background:linear-gradient(150deg,{color},{darken(color)})"
    cls = {"activity": " wk-activity", "event": " wk-event"}.get(it.kind, "")
    changed = '<span class="wk-moved" title="this occurrence was changed">moved</span>' if it.changed else ""
    return (f'<div class="wk-block{cls}" style="{style}"{attrs}><div class="wk-time">{time_text}</div>'
            f'<div class="wk-code">{html.escape(it.title)}</div>{sub}{changed}{handle}</div>')


def free_html(it, lo):
    top = (it.start - lo * 60) * HOUR_PX / 60
    height = (it.end - it.start) * HOUR_PX / 60
    return f'<div class="wk-free" style="top:{top:.1f}px;height:{height:.1f}px"><span>{html.escape(it.title)}</span></div>'


def grid_html(days, today, items_by_day, allday_by_day, off_days, lo, hi, darken, now_minutes=None, free_by_day=None):
    """The HTML of the grid for the given local days (7, 2 or 1 of them)."""
    n = len(days)
    height = (hi - lo) * HOUR_PX
    head = '<div class="wk-corner"></div>' + "".join(
        f'<div class="wk-head{" today" if d == today else ""}"><span>{WEEKDAYS[(d.weekday() + 1) % 7]}</span><b>{d.day:02d}</b></div>' for d in days)
    strip = '<div class="wk-allday-label">All Day</div>' + "".join(
        '<div class="wk-allday">' + "".join(
            f'<div class="wk-pill" style="background:{color}" title="{html.escape(label)}">{html.escape(label)}</div>' for label, color in allday_by_day.get(d, [])) + "</div>"
        for d in days)
    gutter = "".join(f'<div class="wk-hour" style="top:{(h - lo) * HOUR_PX}px">{h:02d}:00</div>' for h in range(lo, hi))
    columns = ""
    for d in days:
        free = "".join(free_html(it, lo) for it in (free_by_day or {}).get(d, []))
        blocks = free + "".join(block_html(it, lane, count, lo, darken) for it, lane, count in lanes(items_by_day.get(d, [])))
        now_line = ""
        if d == today and now_minutes is not None and lo * 60 <= now_minutes <= hi * 60:
            now_line = f'<div class="wk-now" style="top:{(now_minutes - lo * 60) * HOUR_PX / 60:.1f}px"></div>'
        columns += (f'<div class="wk-col{" today" if d == today else ""}{" holiday" if d in off_days else ""}" data-day="{d.isoformat()}" data-lo="{lo}" '
                    f'style="height:{height}px">{blocks}{now_line}</div>')
    return (f'<div class="wk" data-hour-px="{HOUR_PX}" data-snap="{SNAP_MINUTES}" style="--n:{n}"><div class="wk-row wk-top">{head}</div><div class="wk-row wk-strip">{strip}</div>'
            f'<div class="wk-row wk-body"><div class="wk-gutter" style="height:{height}px">{gutter}</div>{columns}</div></div>')
