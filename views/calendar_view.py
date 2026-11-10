"""Calendar: a week view (class blocks on a time grid) and a month view, colored by course."""
import calendar
import html
import re
from datetime import date, datetime, time, timedelta

import streamlit as st

import crud
import settings

MONTH_NAMES = list(calendar.month_name)
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MAX_CHIPS = 3
HOUR_PX = 56            # height of one hour in the week grid
DAY_START_HOUR, DAY_END_HOUR = 6, 24     # the week grid always shows at least this part of the day
VIEWS = ["Week", "Month"]


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


# ------------------------------------------------------------------ week view
def _lanes(occurrences):
    """Give overlapping blocks side-by-side lanes: [(occurrence, lane, lanes_in_cluster)]."""
    placed, cluster, end_of_cluster = [], [], -1
    for o in sorted(occurrences, key=lambda o: (_hhmm(o["start"]), _hhmm(o["end"]))):
        if cluster and _hhmm(o["start"]) >= end_of_cluster:
            placed += _finish_cluster(cluster)
            cluster, end_of_cluster = [], -1
        cluster.append(o)
        end_of_cluster = max(end_of_cluster, _hhmm(o["end"]))
    return placed + _finish_cluster(cluster)


def _finish_cluster(cluster):
    lane_ends, assigned = [], []
    for o in cluster:
        for i, end in enumerate(lane_ends):
            if _hhmm(o["start"]) >= end:
                lane_ends[i] = _hhmm(o["end"]); assigned.append((o, i)); break
        else:
            lane_ends.append(_hhmm(o["end"])); assigned.append((o, len(lane_ends) - 1))
    return [(o, lane, len(lane_ends)) for o, lane in assigned]


def _day_items(first, last, skip_timed_exams=False):
    """All-day items (homework due dates and your own events) as {date: [(label, color)]}, earliest first.

    Labels read like "Due 22:00 MATH 101 HW 5" (homework) and "19:00 MATH 101 Midterm 2" (events)."""
    courses = _course_map()
    rows = {}

    def add(day, title, course_id, time, due=False):
        c = courses.get(course_id)
        code = ((c["code"] or c["name"]) if c else "")
        label = " ".join(x for x in (("Due" if due else "") + (f" {time}" if time and due else (time or "")),
                                     code, title) if x).strip()
        rows.setdefault(date.fromisoformat(day), []).append((time or "99:99", label, _color(c)))

    for hw in crud.homework_due_between(first.isoformat(), last.isoformat()):
        add(hw["due_date"], hw["title"], hw["course_id"], hw.get("due_time"), due=True)
    for ev in crud.list_events(first.isoformat(), last.isoformat()):
        if skip_timed_exams and _is_timed_exam(ev):
            continue                     # shown as a block on the time grid instead
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


def _week_html(week_start, today):
    days = [week_start + timedelta(days=i) for i in range(7)]
    courses = _course_map()
    occ = crud.meeting_occurrences(days[0], days[-1])
    allday = _day_items(days[0], days[-1], skip_timed_exams=True)
    exams = _exam_blocks(days[0], days[-1])
    by_day = {}
    for d in days:
        kept, timed = _merge_in_class(occ.get(d, []), exams.get(d, []))
        by_day[d] = kept + timed
    notices = _notices(days[0], days[-1])
    off = crud.holiday_days(days[0], days[-1])
    for d, rows in notices.items():
        allday[d] = rows + allday.get(d, [])

    starts = [_hhmm(o["start"]) for items in by_day.values() for o in items]
    ends = [_hhmm(o["end"]) for items in by_day.values() for o in items]
    # The grid always covers the same full day, so every week has the same height; it only grows if a block
    # falls outside that range.
    lo = min(DAY_START_HOUR, min(starts) // 60) if starts else DAY_START_HOUR
    hi = min(24, max(DAY_END_HOUR, -(-max(ends) // 60))) if ends else DAY_END_HOUR
    height = (hi - lo) * HOUR_PX

    head = '<div class="wk-corner"></div>' + "".join(
        f'<div class="wk-head{" today" if d == today else ""}"><span>{WEEKDAYS[i]}</span><b>{d.day:02d}</b></div>'
        for i, d in enumerate(days))
    strip = '<div class="wk-allday-label">All Day</div>' + "".join(
        '<div class="wk-allday">' + "".join(
            f'<div class="wk-pill" style="background:{color}" title="{html.escape(label)}">{html.escape(label)}</div>'
            for label, color in allday.get(d, [])) + "</div>" for d in days)

    gutter = "".join(f'<div class="wk-hour" style="top:{(h - lo) * HOUR_PX}px">{h:02d}:00</div>'
                     for h in range(lo, hi))
    columns = ""
    for d in days:
        blocks = ""
        for o, lane, count in _lanes(by_day[d]):
            c = courses.get(o["course_id"])
            color = _color(c)
            top = (_hhmm(o["start"]) - lo * 60) * HOUR_PX / 60
            h = max((_hhmm(o["end"]) - _hhmm(o["start"])) * HOUR_PX / 60 - 2, 18)
            if o.get("exam"):
                where = f'<div class="wk-loc">{html.escape(o["title"])}</div><div class="wk-exam-tag">Exam</div>'
            else:
                where = f'<div class="wk-loc">{html.escape(o["location"])}</div>' if o["location"] else ""
            blocks += (f'<div class="wk-block{" wk-exam" if o.get("exam") else ""}" style="top:{top:.1f}px;height:{h:.1f}px;left:calc({lane * 100 / count}% + 2px);'
                       f'width:calc({100 / count}% - 4px);background:linear-gradient(150deg,{color},{crud.darken(color)})">'
                       f'<div class="wk-time">{o["start"]} - {o["end"]}</div>'
                       f'<div class="wk-code">{html.escape((c["code"] or c["name"]) if c else "")}</div>{where}</div>')
        now_line = ""
        if d == today:
            minutes = datetime.now().hour * 60 + datetime.now().minute
            if lo * 60 <= minutes <= hi * 60:
                now_line = f'<div class="wk-now" style="top:{(minutes - lo * 60) * HOUR_PX / 60:.1f}px"></div>'
        columns += (f'<div class="wk-col{" today" if d == today else ""}{" holiday" if d in off else ""}" '
                    f'style="height:{height}px">{blocks}{now_line}</div>')

    return (f'<div class="wk"><div class="wk-row wk-top">{head}</div><div class="wk-row wk-strip">{strip}</div>'
            f'<div class="wk-row wk-body"><div class="wk-gutter" style="height:{height}px">{gutter}</div>{columns}</div></div>')


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
                (f'{o["start"]} {(c["code"] or c["name"]) if c else ""}', _color(c)))
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


# ------------------------------------------------------------------ schedule editor
@st.dialog("Edit Schedule", width="large")
def _schedule_dialog():
    sem = settings.get_semester()
    st.subheader("Term Dates")
    a, b, c = st.columns(3)
    start = a.date_input("Classes Start", value=date.fromisoformat(sem["start"]), key="sem_start")
    end = b.date_input("Classes End", value=date.fromisoformat(sem["end"]), key="sem_end")
    exam_end = c.date_input("End of Exam Period", value=date.fromisoformat(sem["exam_end"]), key="sem_exam")
    if st.button("Save Term Dates", key="sem_save", disabled=not (start <= end <= exam_end)):
        settings.set_semester(start.isoformat(), end.isoformat(), exam_end.isoformat())
        st.rerun()

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
    st.session_state.setdefault("cal_week", _week_start(today))
    st.session_state.setdefault("cal_view", "Week")

    head, btn = st.columns([6, 1.6], vertical_alignment="center")
    head.title("Calendar")
    if btn.button("Edit Schedule", key="edit_schedule_open"):
        _schedule_dialog()

    c0, c1, c2, c3, c4 = st.columns([1.6, 0.9, 0.9, 0.9, 5], vertical_alignment="center")
    view = c0.segmented_control("View", VIEWS, key="cal_view", label_visibility="collapsed") or "Week"
    week = st.session_state["cal_week"]
    if c1.button("‹ Prev", key="cal_prev"):
        if view == "Week":
            st.session_state["cal_week"] = week - timedelta(days=7)
        else:
            _shift_month(-1)
        st.rerun()
    if c2.button("Today", key="cal_today"):
        st.session_state["cal_week"] = _week_start(today)
        st.session_state["cal_month"] = (today.year, today.month)
        st.rerun()
    if c3.button("Next ›", key="cal_next"):
        if view == "Week":
            st.session_state["cal_week"] = week + timedelta(days=7)
        else:
            _shift_month(1)
        st.rerun()
    if view == "Week":
        end = week + timedelta(days=6)
        span = (f"{MONTH_NAMES[week.month][:3]} {week.day} – {end.day}" if week.month == end.month
                else f"{MONTH_NAMES[week.month][:3]} {week.day} – {MONTH_NAMES[end.month][:3]} {end.day}")
        c4.subheader(f"{span}, {end.year}")
        st.markdown(_week_html(week, today), unsafe_allow_html=True)
    else:
        year, month = st.session_state["cal_month"]
        c4.subheader(f"{MONTH_NAMES[month]} {year}")
        _month_view(today)

    st.divider()
    left, right = st.columns([2, 3])
    with left:
        st.subheader("Add Event")
        courses = {0: "None"} | {c["id"]: crud.label(c) for c in crud.list_courses(section=None)}
        with st.form("add_event", clear_on_submit=True):
            title = st.text_input("Title", placeholder="Midterm Exam")
            when = st.date_input("Date", value=today)
            t1, t2 = st.columns(2)
            at = t1.time_input("Start Time (Optional)", value=None, step=300)
            until = t2.time_input("End Time (Optional)", value=None, step=300)
            course_id = st.selectbox("Course (Optional)", list(courses), format_func=courses.get)
            if st.form_submit_button("Add") and title.strip():
                crud.add_event(title.strip(), when.isoformat(), course_id or None,
                               at.strftime("%H:%M") if at else None, until.strftime("%H:%M") if until else None)
                st.session_state["cal_month"] = (when.year, when.month)
                st.session_state["cal_week"] = _week_start(when)
                st.rerun()
    with right:
        year, month = st.session_state["cal_month"]
        st.subheader("This Month")
        first = date(year, month, 1).isoformat()
        last = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        homework = crud.homework_due_between(first, last)
        events = crud.list_events(first, last)
        if not homework and not events:
            st.caption("Nothing scheduled this month.")
        courses_by_id = _course_map()
        code = lambda cid: ((courses_by_id[cid]["code"] or courses_by_id[cid]["name"]) + " ") if cid in courses_by_id else ""
        for hw in homework:
            st.markdown(f"**{hw['due_date']}**{' ' + hw['due_time'] if hw.get('due_time') else ''} · "
                        f"Homework Due: {code(hw['course_id'])}{hw['title']}")
        for ev in events:
            a, b = st.columns([6, 1], vertical_alignment="center")
            a.markdown(f"**{ev['date']}**{' ' + ev['time'] if ev.get('time') else ''} · {code(ev['course_id'])}{ev['title']}")
            if b.button("Remove", key=f"rm_event_{ev['id']}"):
                crud.delete_event(ev["id"]); st.rerun()
