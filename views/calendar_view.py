"""Calendar: a week view (class blocks on a time grid) and a month view, colored by course."""
import calendar
import html
import re
from datetime import date, datetime, time, timedelta

import streamlit as st

from core import crud
from core import settings
from views import tutorial
from planner import commit_store, service, session_store, store as planner_store, task_store, timeutil, track_store
from views import plan_grid, planner_ui, tasklist_view
from planner import gridview
from planner.gridview import (EXAM_RE, DEFAULT_EXAM_MINUTES, _week_start, _hhmm, _plus, _is_timed_exam, _exam_blocks, _merge_in_class, _course_map, _color, _day_items, _notices, _items_by_day)      # the pure part of the calendar: shared with the native interface


def _planner_grid(days, today, report, show_free=True):
    """The HTML of the time grid for the given days."""
    items, allday, off, lo, hi, now_minutes, free, hour_px = gridview.grid_data(days, today, report, show_free)
    return plan_grid.grid_html(days, today, items, allday, off, lo, hi, crud.darken, now_minutes, free, hour_px)

MONTH_NAMES = list(calendar.month_name)
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MAX_CHIPS = 3
HOUR_PX = 56            # height of one hour in the week grid
DAY_START_HOUR, DAY_END_HOUR = 6, 24     # the week grid always shows at least this part of the day
VIEWS = ["Day", "Week", "Month"]
PAGES = ["Calendar", "Task List"]






def _label_time(text):
    return text




















# ------------------------------------------------------------------ the planner grid (Day, Week)
def _grid_days(view, anchor):
    if view == "Week":
        first = _week_start(anchor)
        return [first + timedelta(days=i) for i in range(7)]
    return [anchor]




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

    st.caption("Holidays and breaks are managed with the terms: choose Manage Terms in the term list above the calendar.")

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
        with y.popover("Remove", icon=":material/delete:", key=f"meeting_pop_{m['id']}"):
            st.caption("Remove this class time and every change made to single days?")
            if st.button("Yes, Remove It", key=f"rm_meeting_{m['id']}", type="primary"):
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
    if st.session_state.get("lib_toast"):
        st.toast(st.session_state.pop("lib_toast"))

    st.session_state.setdefault("cal_page", "Calendar")
    head, tog, btn = st.columns([2.2, 2.6, 1.6], vertical_alignment="center")
    page = tog.segmented_control("Page", PAGES, key="cal_page", label_visibility="collapsed") or "Calendar"
    head.title(page)
    if page == "Calendar" and (btn.button("Edit Schedule", key="edit_schedule_open") or tutorial.wants("schedule")):          # the tour opens it too
        _schedule_dialog()
    elif tutorial.wants("new_term"):                                                                                     # the tour opens the window to add a term
        planner_ui.new_term_dialog()

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
            tcol, ccol = st.columns([3, 2], vertical_alignment="center")
            show_free = tcol.toggle("Show Free Time", True, key="cal_free", help="shades the time that is free for study and writes how long each stretch is")
            auto_left = session_store.count_auto()
            with ccol.popover("Clear Auto-Plan", icon=":material/delete_sweep:", key="clear_plan_pop", disabled=not auto_left,
                              help="removes the study sessions that auto-plan made and that have not started"):
                st.caption(f"Remove the {auto_left} study session{'s' if auto_left != 1 else ''} Auto-Plan made that {'have' if auto_left != 1 else 'has'} not started? Sessions you placed or changed yourself stay. "
                           "You can run Auto-Plan again at any time.")
                if st.button("Yes, Clear Them", key="clear_plan_go", type="primary"):
                    removed, _ = service.clear_auto_plan()
                    st.session_state["lib_toast"] = f"Removed {removed} auto-plan session{'s' if removed != 1 else ''}."
                    st.rerun()
            st.markdown(_planner_grid(days, today, report, show_free), unsafe_allow_html=True)
            st.caption("Drag a block from the left into the schedule, drag a session or an event to move it, drag its bottom edge to change its length, or drag over empty time to add one. Click one to open it.")
