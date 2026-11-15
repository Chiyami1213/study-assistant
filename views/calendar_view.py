"""Calendar: a week view (class blocks on a time grid) and a month view, colored by course."""
import calendar
import html
import re
from datetime import date, datetime, time, timedelta

import streamlit as st

import crud
import settings
from planner import commit_store, service, session_store, store as planner_store, task_store, timeutil, track_store
from views import plan_grid, planner_ui, tasklist_view

MONTH_NAMES = list(calendar.month_name)
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MAX_CHIPS = 3
HOUR_PX = 56            # height of one hour in the week grid
DAY_START_HOUR, DAY_END_HOUR = 6, 24     # the week grid always shows at least this part of the day
VIEWS = ["Day", "Week", "Month"]
PAGES = ["Calendar", "Task List"]


def _week_start(day):
    """The Sunday on or before a date."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def _hhmm(text):
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def _label_time(text):
    return text


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


# ------------------------------------------------------------------ the planner grid (Day, Week)
def _grid_days(view, anchor):
    if view == "Week":
        first = _week_start(anchor)
        return [first + timedelta(days=i) for i in range(7)]
    return [anchor]


def _planner_grid(days, today, report, show_free=True):
    """The HTML of the time grid for the given days: classes, activities, events with their travel time, and the study sessions."""
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
    return plan_grid.grid_html(days, today, items, allday, set(crud.holiday_days(days[0], days[-1])), lo, hi, crud.darken, local_now.hour * 60 + local_now.minute, free, settings.get_calendar_hour_px())


def _panel(report, courses):
    """The draggable blocks on the left of the grid, and the buttons to add a task or an activity."""
    open_tasks = task_store.list_tasks(include_done=False)
    sessions = session_store.list_sessions()
    now = datetime.now(timeutil.UTC)
    left = {t.id: max(0, t.remaining_minutes - sum(s.minutes for s in sessions if s.task_id == t.id and s.end > now)) for t in open_tasks}
    ordered = sorted(open_tasks, key=lambda t: (t.due is None, t.due or now, t.id))
    a, b = st.columns(2)
    if a.button("+ Task", key="pl_add_task", width="stretch"):
        planner_ui.add_task_dialog()
    if b.button("+ Activity", key="pl_add_activity", width="stretch"):
        planner_ui.activity_dialog()
    term = settings.get_active_term()
    st.markdown(planner_ui.panel_html(ordered, courses, commit_store.list_activities(), report, left, term["name"] if term else None, settings.get_hidden_blocks(),
                                      settings.get_block_names(), settings.get_block_colors(), settings.get_block_order()), unsafe_allow_html=True)


def _span_title(view, days):
    a, b = days[0], days[-1]
    if view == "Day":
        return f"{WEEKDAYS[(a.weekday() + 1) % 7]}, {MONTH_NAMES[a.month][:3]} {a.day}, {a.year}"
    return (f"{MONTH_NAMES[a.month][:3]} {a.day} – {b.day}" if a.month == b.month else f"{MONTH_NAMES[a.month][:3]} {a.day} – {MONTH_NAMES[b.month][:3]} {b.day}") + f", {b.year}"


def _step(view):
    return {"Week": 7, "Day": 1}[view]


def _auto_plan():
    result, report = service.auto_plan()
    placed = len(result.add)
    left = len(result.unplaced)
    st.session_state["cal_toast"] = (f"Planned {placed} study session{'s' if placed != 1 else ''}." if placed else "Nothing to plan: every task is already covered, or has no due date.") + \
        (f" {left} task{'s' if left != 1 else ''} do not fully fit." if left else "")


# ------------------------------------------------------------------ month view
def _shift_month(delta):
    y, m = st.session_state["cal_month"]
    m += delta
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    st.session_state["cal_month"] = (y, m)


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


def _cell_html(day, items, is_today):
    chips = "".join(
        f'<div class="cal-chip" style="background:{color}" title="{html.escape(label)}">{html.escape(label)}</div>'
        for label, color in items[:MAX_CHIPS])
    more = f'<div class="cal-more">+{len(items) - MAX_CHIPS} more</div>' if len(items) > MAX_CHIPS else ""
    cls = "cal-cell today" if is_today else "cal-cell"
    return f'<div class="{cls}"><div class="cal-day">{day.day}</div>{chips}{more}</div>'


def _month_view(today):
    year, month = st.session_state["cal_month"]
    items = _items_by_day(year, month)
    head = st.columns(7)
    for col, name in zip(head, WEEKDAYS):
        col.markdown(f'<div class="cal-head">{name}</div>', unsafe_allow_html=True)
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(year, month):
        cols = st.columns(7)
        for col, day in zip(cols, week):
            if day.month != month:
                col.markdown('<div class="cal-cell blank"></div>', unsafe_allow_html=True)
            else:
                col.markdown(_cell_html(day, items.get(day.isoformat(), []), day == today), unsafe_allow_html=True)


# ------------------------------------------------------------------ terms
# ------------------------------------------------------------------ schedule editor
@st.dialog("Edit Schedule", width="large")
def _schedule_dialog():
    start = date.fromisoformat(settings.get_semester()["start"])
    st.caption("The terms (semesters) are managed from the term list above the calendar: choose Manage Terms.")

    st.subheader("Holidays")
    holidays = crud.list_holidays()
    if not holidays:
        st.caption("No holidays yet.")
    for h in holidays:
        x, y = st.columns([6, 1], vertical_alignment="center")
        same = h["start_date"] == h["end_date"]
        x.markdown(f"**{h['name']}** · {h['start_date']}" + ("" if same else f" to {h['end_date']}"))
        if y.button("Remove", key=f"rm_holiday_{h['id']}"):
            crud.delete_holiday(h["id"]); st.rerun()
    n1, n2, n3 = st.columns([2, 1, 1], vertical_alignment="bottom")
    hname = n1.text_input("Holiday Name", key="hol_name", placeholder="Fall Break")
    hstart = n2.date_input("Starts", value=start, key="hol_start")
    hend = n3.date_input("Ends", value=start, key="hol_end")
    if st.button("Add Holiday", key="hol_add", disabled=not hname.strip() or hend < hstart):
        crud.add_holiday(hname.strip(), hstart.isoformat(), hend.isoformat())
        st.rerun()

    st.subheader("Class Times")
    courses = {c["id"]: c for c in crud.list_courses(section=None)}
    meetings = crud.list_meetings()
    if not meetings:
        st.caption("No class times yet.")
    for m in meetings:
        course = courses.get(m["course_id"])
        x, y = st.columns([6, 1], vertical_alignment="center")
        x.markdown(f"**{crud.label(course) if course else 'Removed Course'}** · {crud.meeting_days_label(m)} · "
                   f"{m['start_time']} - {m['end_time']}" + (f" · {m['location']}" if m["location"] else ""))
        if y.button("Remove", key=f"rm_meeting_{m['id']}"):
            crud.delete_meeting(m["id"]); st.rerun()

    st.subheader("Add Class Time")
    active = {c["id"]: crud.label(c) for c in crud.courses_by_status("Active")}
    if not active:
        st.caption("Add an active course first."); return
    course_id = st.selectbox("Course", list(active), format_func=active.get, key="mt_course")
    days = st.multiselect("Days", list(range(7)), default=[1, 3], format_func=lambda d: crud.DAY_ABBR[d], key="mt_days")
    t1, t2, t3 = st.columns([1, 1, 2])
    start_t = t1.time_input("Start Time", value=time(9, 30), step=300, key="mt_start")
    end_t = t2.time_input("End Time", value=time(10, 45), step=300, key="mt_end")
    where = t3.text_input("Location (Optional)", key="mt_loc", placeholder="Clough 102")
    if st.button("Add Class Time", type="primary", key="mt_add", disabled=not days or end_t <= start_t):
        crud.add_meeting(course_id, days, start_t.strftime("%H:%M"), end_t.strftime("%H:%M"), where.strip())
        st.rerun()


# ------------------------------------------------------------------ page
def render():
    today = date.today()
    st.session_state.setdefault("cal_month", (today.year, today.month))
    st.session_state.setdefault("cal_anchor", today)
    st.session_state.setdefault("cal_view", "Week")

    st.session_state.setdefault("cal_page", "Calendar")
    head, tog, btn = st.columns([2.2, 2.6, 1.6], vertical_alignment="center")
    page = tog.segmented_control("Page", PAGES, key="cal_page", label_visibility="collapsed") or "Calendar"
    head.title(page)
    if page == "Calendar" and btn.button("Edit Schedule", key="edit_schedule_open"):
        _schedule_dialog()

    sink = st.text_input("Calendar Actions", key="cal_sink", label_visibility="collapsed")          # a drag or click in the grid writes here (see app.py)
    if sink and sink != st.session_state.get("_cal_sink_done"):
        st.session_state["_cal_sink_done"] = sink
        planner_ui.handle_action(sink)

    if page == "Task List":
        planner_ui.show_pending()
        planner_ui.timer_bar()
        tasklist_view.render(service.cushion_report(), _course_map(), planner_store.get_term().zone)
        return

    cf, c0, c1, c2, c3, c4, ct, c5 = st.columns([0.45, 2.6, 0.9, 0.9, 0.9, 2.3, 1.5, 1.4], vertical_alignment="center")
    planner_ui.term_select(ct)
    panel_open = settings.get_calendar_panel_open()
    if cf.button("", key="cal_fold", icon=":material/left_panel_close:" if panel_open else ":material/left_panel_open:",
                 help="fold the left panel" if panel_open else "show the left panel"):
        settings.set_calendar_panel_open(not panel_open)
        st.rerun()
    view = c0.segmented_control("View", VIEWS, key="cal_view", label_visibility="collapsed") or "Week"
    anchor = st.session_state["cal_anchor"]
    if c1.button("‹ Prev", key="cal_prev"):
        if view == "Month":
            _shift_month(-1)
        else:
            st.session_state["cal_anchor"] = anchor - timedelta(days=_step(view))
        st.rerun()
    if c2.button("Today", key="cal_today"):
        st.session_state["cal_anchor"] = today
        st.session_state["cal_month"] = (today.year, today.month)
        st.rerun()
    if c3.button("Next ›", key="cal_next"):
        if view == "Month":
            _shift_month(1)
        else:
            st.session_state["cal_anchor"] = anchor + timedelta(days=_step(view))
        st.rerun()
    if c5.button("Auto-Plan", key="cal_autoplan", type="primary", icon=":material/auto_awesome:", help="places study sessions for the tasks that have a due date, earliest deadline first"):
        _auto_plan()
        st.rerun()

    report = service.cushion_report()
    tz = planner_store.get_term().zone
    courses = _course_map()
    planner_ui.show_pending()
    planner_ui.timer_bar()
    if view == "Month":
        year, month = st.session_state["cal_month"]
        c4.subheader(f"{MONTH_NAMES[month]} {year}")
        _month_view(today)
    else:
        days = _grid_days(view, anchor)
        c4.subheader(_span_title(view, days))
        planner_ui.banner(report, courses, tz)
        side, main = st.columns([1.15, 4.2], gap="medium")                     # the panel stays in the page when folded: its column glides shut (CSS) and open again
        with side:
            _panel(report, courses)
        with main:
            show_free = st.toggle("Show Free Time", True, key="cal_free", help="shades the time that is free for study and writes how long each stretch is")
            st.markdown(_planner_grid(days, today, report, show_free), unsafe_allow_html=True)
            st.caption("Drag a block from the left into the schedule, drag a session or an event to move it, drag its bottom edge to change its length, or drag over empty time to add one. Click one to open it.")
