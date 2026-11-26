"""What the calendar draws, without Streamlit and without Qt: the classes, activities, events, exams, homework deadlines, holidays and study sessions of the days shown, ready for a week grid or a month.
The classic page (`views/calendar_view.py`) and the native one (`qtui/pages/calendar_page.py`) both use it."""
import calendar
import re
from datetime import date, datetime, timedelta

from core import crud
from core import settings
from planner import commit_store, service, session_store, store as planner_store, task_store, timeutil, track_store
from views import plan_grid

def _week_start(day):
    """The Sunday on or before a date."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def _hhmm(text):
    h, m = text.split(":")
    return int(h) * 60 + int(m)


EXAM_RE = re.compile(r"midterm|final|exam", re.I)


DEFAULT_EXAM_MINUTES = 120


def _is_timed_exam(ev):
    return bool(EXAM_RE.search(ev["title"])) and bool(ev.get("time"))


def _plus(text, minutes):
    total = min(_hhmm(text) + minutes, 23 * 60 + 59)
    return f"{total // 60:02d}:{total % 60:02d}"


def _exam_blocks(first, last):
    """{date: [block]} for timed midterms and finals, shaped like class occurrences (end defaults to 2 hours)."""
    out = {}
    for ev in crud.list_events(first.isoformat(), last.isoformat()):
        if _is_timed_exam(ev):
            out.setdefault(date.fromisoformat(ev["date"]), []).append({
                "meeting_id": None, "course_id": ev["course_id"], "start": ev["time"],
                "end": ev.get("end_time") or _plus(ev["time"], DEFAULT_EXAM_MINUTES),
                "location": None, "title": ev["title"], "exam": True, "explicit_end": bool(ev.get("end_time"))})
    return out


def _merge_in_class(classes, exams):
    """In-class exams: a midterm that starts when the same course's regular class starts (and ends with it, or has
    no end time set) replaces that class block. Returns (classes to draw, exams to draw)."""
    kept, exams = list(classes), [dict(e) for e in exams]
    for e in exams:
        for c in kept:
            if (c["course_id"] == e["course_id"] and c["start"] == e["start"]
                    and (not e["explicit_end"] or c["end"] == e["end"])):
                kept.remove(c)
                if not e["explicit_end"]:
                    e["end"] = c["end"]          # the exam runs for the class period
                break
    return kept, exams


def _course_map():
    return {c["id"]: c for c in crud.list_courses(section=None)}


def _color(course):
    return crud.course_color(course) if course else "#6b7280"


def _day_items(first, last, skip_timed_exams=False, skip_timed=False):
    """All-day items (homework due dates and your own events) as {date: [(label, color)]}, earliest first.

    Labels read like "Due 22:00 MATH 101 HW 5" (homework) and "19:00 MATH 101 Midterm 2" (events)."""
    courses = _course_map()
    rows = {}

    def add(day, title, course_id, time, due=False):
        c = courses.get(course_id)
        code = ((crud.show_code(c["code"]) or c["name"]) if c else "")
        label = " ".join(x for x in (("Due" if due else "") + (f" {time}" if time and due else (time or "")),
                                     code, title) if x).strip()
        rows.setdefault(date.fromisoformat(day), []).append((time or "99:99", label, _color(c)))

    for hw in crud.homework_due_between(first.isoformat(), last.isoformat()):
        add(hw["due_date"], hw["title"], hw["course_id"], hw.get("due_time"), due=True)
    for ev in crud.list_events(first.isoformat(), last.isoformat()):
        if skip_timed_exams and _is_timed_exam(ev):
            continue                     # shown as a block on the time grid instead
        if skip_timed:
            continue                     # the planner draws every event itself: timed ones as blocks, all-day ones in the all-day row
        add(ev["date"], ev["title"], ev["course_id"], ev.get("time"))
    return {d: [(label, color) for _, label, color in sorted(items)] for d, items in rows.items()}


def _notices(first, last):
    """{date: [(label, color)]} for holidays and the exam period (the days after classes end)."""
    out = {}
    for day, name in crud.holiday_days(first, last).items():
        out.setdefault(day, []).append((name, "#6b7280"))
    sem = settings.get_semester()
    day, exam_end = max(first, date.fromisoformat(sem["end"]) + timedelta(days=1)), date.fromisoformat(sem["exam_end"])
    while day <= min(last, exam_end):
        out.setdefault(day, []).append(("Exam Period", "#c2410c"))
        day += timedelta(days=1)
    return out


def _items_by_day(year, month):
    """{date: [(label, color)]}: holidays and the exam period, then deadlines, then class meetings."""
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    courses = _course_map()
    items = {}
    for day, rows in _notices(first, last).items():
        items.setdefault(day.isoformat(), []).extend(rows)
    for day, rows in _day_items(first, last).items():
        items.setdefault(day.isoformat(), []).extend(rows)
    exams = _exam_blocks(first, last)
    for day, occs in crud.meeting_occurrences(first, last).items():
        for o in _merge_in_class(occs, exams.get(day, []))[0]:      # no class chip on an in-class exam day
            c = courses.get(o["course_id"])
            items.setdefault(day.isoformat(), []).append(
                (f'{o["start"]} {(crud.show_code(c["code"]) or c["name"]) if c else ""}', _color(c)))
    return items


def grid_data(days, today, report, show_free=True):
    """Everything the time grid draws for the given days: (items by day, all-day rows by day, the days off, first hour, last hour, minutes of now, free time by day, pixels per hour).
    Classes, activities, events with their travel time, and the study sessions."""
    tz = planner_store.get_term().zone
    blocks = commit_store.commitments(days[0], days[-1])
    sessions = session_store.list_sessions(days[0], days[-1])
    tasks = {x.id: x for x in task_store.list_tasks()}
    courses = _course_map()
    prefs = settings.get_block_colors()
    colors = {cid: prefs.get(f"course:{cid}") or crud.course_color(c) for cid, c in courses.items()}
    task_colors = {int(k.split(":")[1]): v for k, v in prefs.items() if k.startswith("task:")}
    names = settings.get_block_names()
    levels = {c.task_id: c.level for c in report.items}
    used = {}
    for log in track_store.list_logs():
        if log.session_id is not None:
            used[log.session_id] = used.get(log.session_id, 0) + log.minutes
    progress = {s.id: min(1.0, used.get(s.id, 0) / s.minutes) for s in sessions if s.minutes and used.get(s.id)}
    items = {d: plan_grid.day_items(d, blocks, sessions, tasks, colors, levels, tz, progress, task_colors, names) for d in days}
    allday = _day_items(days[0], days[-1], skip_timed_exams=True, skip_timed=True)
    for b in blocks:
        if b.all_day:
            first_day = timeutil.local_day(b.start, tz)
            for d in days:
                if first_day <= d <= timeutil.local_day(b.end - timedelta(seconds=1), tz):
                    allday.setdefault(d, []).append((b.label, colors.get(b.owner_id, "#6b7280"), f"event:{b.ref_id}" if b.kind == "event" else ""))
    for d, rows in _notices(days[0], days[-1]).items():
        allday[d] = rows + allday.get(d, [])
    lo, hi = plan_grid.hour_range(items)
    local_now = timeutil.to_local(datetime.now(timeutil.UTC), tz)
    free = {}
    if show_free:
        now_utc = datetime.now(timeutil.UTC)
        pieces = service.free_time(days[0], days[-1], now_utc)
        personal_pieces = service.free_time(days[0], days[-1], now_utc, personal=True)                   # in a break or outside the term only personal work can be planned
        term = planner_store.get_term()
        free = {d: plan_grid.free_items(d, pieces if term.is_planning_day(d) else personal_pieces, tz) for d in days}
    return items, allday, set(crud.holiday_days(days[0], days[-1])), lo, hi, local_now.hour * 60 + local_now.minute, free, settings.get_calendar_hour_px()
