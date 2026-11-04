"""Calendar: month view of homework due dates and your own events, colored by course."""
import calendar
import html
from datetime import date

import streamlit as st

import crud

MONTH_NAMES = list(calendar.month_name)
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MAX_CHIPS = 3


def _shift_month(delta):
    y, m = st.session_state["cal_month"]
    m += delta
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    st.session_state["cal_month"] = (y, m)


def _items_by_day(year, month):
    """{date: [(label, color)]} for homework due dates and events in the month."""
    first = date(year, month, 1).isoformat()
    last = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
    courses = {c["id"]: c for c in crud.list_courses(section=None)}
    items = {}

    def add(day, label, course_id, kind):
        c = courses.get(course_id)
        color = crud.course_color(c) if c else "#6b7280"
        tag = (c["code"] or c["name"]) + " " if c else ""
        items.setdefault(day, []).append((f"{kind}{tag}{label}", color))

    for hw in crud.homework_due_between(first, last):
        add(hw["due_date"], hw["title"], hw["course_id"], "Due: ")
    for ev in crud.list_events(first, last):
        add(ev["date"], ev["title"], ev["course_id"], "")
    return items


def _cell_html(day, items, is_today):
    chips = "".join(
        f'<div class="cal-chip" style="background:{color}" title="{html.escape(label)}">{html.escape(label)}</div>'
        for label, color in items[:MAX_CHIPS])
    more = f'<div class="cal-more">+{len(items) - MAX_CHIPS} more</div>' if len(items) > MAX_CHIPS else ""
    cls = "cal-cell today" if is_today else "cal-cell"
    return f'<div class="{cls}"><div class="cal-day">{day.day}</div>{chips}{more}</div>'


def render():
    today = date.today()
    st.session_state.setdefault("cal_month", (today.year, today.month))
    year, month = st.session_state["cal_month"]

    st.title("Calendar")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 6], vertical_alignment="center")
    if c1.button("‹ Prev", key="cal_prev"):
        _shift_month(-1); st.rerun()
    if c2.button("Today", key="cal_today"):
        st.session_state["cal_month"] = (today.year, today.month); st.rerun()
    if c3.button("Next ›", key="cal_next"):
        _shift_month(1); st.rerun()
    c4.subheader(f"{MONTH_NAMES[month]} {year}")

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

    st.divider()
    left, right = st.columns([2, 3])
    with left:
        st.subheader("Add Event")
        courses = {0: "None"} | {c["id"]: crud.label(c) for c in crud.list_courses(section=None)}
        with st.form("add_event", clear_on_submit=True):
            title = st.text_input("Title", placeholder="Midterm Exam")
            when = st.date_input("Date", value=today)
            course_id = st.selectbox("Course (Optional)", list(courses), format_func=courses.get)
            if st.form_submit_button("Add") and title.strip():
                crud.add_event(title.strip(), when.isoformat(), course_id or None)
                st.session_state["cal_month"] = (when.year, when.month)
                st.rerun()
    with right:
        st.subheader("This Month")
        first = date(year, month, 1).isoformat()
        last = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        homework = crud.homework_due_between(first, last)
        events = crud.list_events(first, last)
        if not homework and not events:
            st.caption("Nothing scheduled this month.")
        for hw in homework:
            st.markdown(f"**{hw['due_date']}** · Homework Due: {hw['title']}")
        for ev in events:
            a, b = st.columns([6, 1], vertical_alignment="center")
            a.markdown(f"**{ev['date']}** · {ev['title']}")
            if b.button("Remove", key=f"rm_event_{ev['id']}"):
                crud.delete_event(ev["id"]); st.rerun()
