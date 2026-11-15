"""The planner on the Calendar page: the cushion banner, the task list with cushion badges, the dialogs (new task, new session or event by dragging, details) and the
handler of what a drag or a click in the grid reports. The scheduling logic is in the planner package; this only shows it and calls it."""
import html
from datetime import date, datetime, time, timedelta, timezone

import streamlit as st

import crud
from planner import commit_store, service, session_store, store, task_store, tasks as T, timeutil, track_store, tracking
from planner.models import PlannerError
from views import plan_grid

LEVEL_LABEL = {"green": "Comfortable", "yellow": "Tight", "red": "Does Not Fit"}


def _now():
    return datetime.now(timezone.utc)


def _courses():
    return {c["id"]: c for c in crud.list_courses(section=None)}


def _course_name(courses, course_id):
    c = courses.get(course_id)
    return (c["code"] or c["name"]) if c else ""


def _fmt_due(due, tz):
    if due is None:
        return "No due date"
    local = timeutil.to_local(due, tz)
    return f"{local:%b} {local.day}, {local:%I:%M %p}".replace(" 0", " ")


def _cushion_text(minutes):
    return ("+" if minutes > 0 else "") + plan_grid.fmt_minutes(minutes)


# ---------------------------------------------------------------- the left panel: blocks to drag into the schedule
def panel_html(tasks, courses, activities, report, usage_left):
    """The blocks on the left of the Calendar. Dragging one onto the grid adds it there: a task becomes a study session, a course or an activity a weekly time,
    and the custom event block opens the new-event form. `usage_left`: {task id: minutes not yet in a session}."""
    levels = {c.task_id: c.level for c in report.items}
    out = ['<div class="pl-title">Drag a block into the schedule</div>', '<div class="pl-item pl-event" data-drag="event:0" title="drag it onto the calendar to add an event">Drag a custom event</div>']
    out.append('<div class="pl-head">Tasks</div>')
    shown = 0
    for t in tasks:
        color = crud.course_color(courses[t.course_id]) if t.course_id in courses else "#6b7280"
        dot = f'<span class="wk-dot" style="background:{plan_grid.LEVEL_COLORS[levels[t.id]]}" title="cushion: {levels[t.id]}"></span>' if t.id in levels else ""
        left = usage_left.get(t.id, t.remaining_minutes)
        out.append(f'<div class="pl-item pl-task" data-drag="task:{t.id}" style="border-left-color:{color};background:{color}2b" '
                   f'title="drag it onto the calendar to add a study session">{dot}<b>{html.escape(t.title)}</b>'
                   f'<span>{html.escape(_course_name(courses, t.course_id))}{" · " if t.course_id in courses else ""}{plan_grid.fmt_minutes(left)} to plan</span></div>')
        shown += 1
    if not shown:
        out.append('<div class="pl-empty">No tasks to plan.</div>')
    out.append('<div class="pl-head">Courses</div>')
    for cid, c in courses.items():
        if crud.course_status(c) == "Completed":
            continue
        color = crud.course_color(c)
        out.append(f'<div class="pl-item pl-course" data-drag="course:{cid}" style="border-left-color:{color};background:{color}2b" '
                   f'title="drag it onto the calendar to add a weekly class time"><b>{html.escape(c["code"] or c["name"])}</b></div>')
    if activities:
        out.append('<div class="pl-head">Activities</div>')
        for a in activities:
            color = a["color"] or plan_grid.ACTIVITY_COLOR
            out.append(f'<div class="pl-item pl-course" data-drag="activity:{a["id"]}" style="border-left-color:{color};background:{color}2b" '
                       f'title="drag it onto the calendar to add a weekly time"><b>{html.escape(a["name"])}</b></div>')
    return '<div class="pl-panel">' + "".join(out) + "</div>"


@st.dialog("Add Activity")
def activity_dialog():
    name = st.text_input("Name", key="ac_name", placeholder="Gym")
    where = st.text_input("Location (Optional)", key="ac_loc")
    c1, c2, c3 = st.columns([1, 1, 1])
    color = c1.color_picker("Colour", "#0f766e", key="ac_color")
    busy = c2.toggle("Blocks Study Time", True, key="ac_busy", help="off: it shows on the calendar, but study may be planned over it")
    in_breaks = c3.toggle("Also in Breaks", False, key="ac_breaks", help="work, for example, goes on during a break")
    st.caption("Then drag the activity from the left onto the calendar to add its weekly time.")
    if st.button("Add Activity", key="ac_save", type="primary", disabled=not name.strip()):
        try:
            commit_store.add_activity(name.strip(), color, where.strip(), busy, in_breaks)
        except PlannerError as e:
            st.error(str(e))
            return
        st.rerun()


@st.dialog("Add Weekly Time")
def meeting_dialog(owner, owner_id, day, start_minutes):
    """Weekly class time of a course, or weekly time of an activity, from a block dropped on the calendar (the day and time it landed on are the start)."""
    courses = _courses()
    if owner == "course":
        c = courses.get(owner_id)
        name = crud.label(c) if c else "Course"
    else:
        a = next((x for x in commit_store.list_activities() if x["id"] == owner_id), None)
        name = a["name"] if a else "Activity"
    st.markdown(f"**{html.escape(name)}**")
    days = st.multiselect("Days", list(range(7)), default=[day.weekday()], format_func=lambda d: crud.DAY_ABBR[d], key=f"mt2_days_{owner}_{owner_id}")
    t1, t2 = st.columns(2)
    start = t1.time_input("Start", time(min(start_minutes, 1439) // 60, min(start_minutes, 1439) % 60), step=300, key=f"mt2_start_{owner}_{owner_id}_{start_minutes}")
    end_default = min(start_minutes + 75 if owner == "course" else start_minutes + 60, 1439)
    end = t2.time_input("End", time(end_default // 60, end_default % 60), step=300, key=f"mt2_end_{owner}_{owner_id}_{start_minutes}")
    where = st.text_input("Location (Optional)", key=f"mt2_loc_{owner}_{owner_id}")
    last = st.checkbox("Ends on a Date", False, key=f"mt2_last_on_{owner}_{owner_id}")
    end_date = st.date_input("Last Day", value=day + timedelta(days=84), key=f"mt2_last_{owner}_{owner_id}", disabled=not last)
    if st.button("Add to Schedule", key=f"mt2_save_{owner}_{owner_id}", type="primary", disabled=not days or end <= start):
        problem = save_meeting(owner, owner_id, days, start, end, where.strip(), end_date if last else None)
        if problem:
            st.error(problem)
            return
        st.session_state["cal_toast"] = "Added to the schedule."
        st.rerun()


def save_meeting(owner, owner_id, days, start, end, location="", end_date=None):
    """Add a weekly time to a course or an activity. Returns None, or the reason it was refused."""
    try:
        if owner == "course":
            commit_store.add_course_meeting(owner_id, set(days), start, end, location, end_date)
        else:
            commit_store.add_activity_meeting(owner_id, set(days), start, end, location, end_date)
    except PlannerError as e:
        return str(e)
    return None


def _drop_duration(task_id):
    """How long a study session dropped for a task is: what is left to plan for it, at least the minimum block, at most two hours, in 15 minute steps."""
    config = store.load_config()
    t = task_store.get_task(task_id)
    planned = sum(s.minutes for s in session_store.list_sessions(task_id=task_id) if s.end > _now())
    need = max(0, t.remaining_minutes - planned)
    minutes = min(max(need, config.min_block_minutes), 120)
    return int(-(-minutes // 15) * 15)


def handle_drop(what, day, minutes):
    """A block from the left panel dropped on the grid at a day and a time (minutes after local midnight)."""
    tz = store.get_term().zone
    kind, _, raw = what.partition(":")
    ident = int(raw)
    if kind == "task":
        start = _local(tz, day, minutes)
        end = start + timedelta(minutes=_drop_duration(ident))
        _apply(lambda force: service.add_session(ident, start, end, force=force), start, end, None, "The study session was added.")
    elif kind == "event":
        st.session_state["cal_create"] = (day, minutes, min(minutes + 60, 24 * 60), "Event")
    elif kind in ("course", "activity"):
        st.session_state["cal_meeting"] = (kind, ident, day, minutes)


# ---------------------------------------------------------------- the study timer
def _clock(seconds):
    s = int(max(0, seconds))
    return f"{s // 3600:d}:{s % 3600 // 60:02d}:{s % 60:02d}"


@st.fragment(run_every=1)
def _timer_ticker(started_iso):
    """The running time, redrawn every second without redrawing the page."""
    started = timeutil.parse_utc(started_iso)
    st.markdown(f"**{_clock((_now() - started).total_seconds())}**")


def timer_bar():
    """While the study timer runs: what is being studied, the running time, and the buttons to stop (and log the time) or to throw it away."""
    timer = track_store.running_timer()
    if not timer:
        return
    try:
        task = task_store.get_task(timer.task_id)
    except PlannerError:
        track_store.cancel_timer()
        return
    with st.container(border=True, key="timer_bar"):
        a, b, c, d = st.columns([4, 2, 1.6, 1.4], vertical_alignment="center")
        a.markdown(f":material/timer: **Studying {html.escape(task.title)}**")
        with b:
            _timer_ticker(timeutil.utc_iso(timer.started))
        if c.button("Stop and Log", key="timer_stop", type="primary", icon=":material/stop_circle:", help="stops the timer and adds the time to the task"):
            result, _ = service.stop_timer()
            if result.discarded:
                st.session_state["cal_toast"] = "Under half a minute: nothing was logged."
            else:
                st.session_state["cal_toast"] = (f"Logged {plan_grid.fmt_minutes(result.minutes)} on {task.title}." +
                                                 (f" The timer had run longer than {tracking.MAX_TIMER_HOURS} hours; the time was cut there." if result.capped else ""))
            st.rerun()
        if d.button("Cancel", key="timer_cancel", help="throws the timer away without logging anything"):
            service.cancel_timer()
            st.rerun()


def _start(task_id, session_id=None):
    try:
        service.start_timer(task_id, session_id)
    except PlannerError as e:
        st.session_state["cal_toast"] = str(e)


@st.dialog("Log Time")
def log_dialog(task_id):
    try:
        task = task_store.get_task(task_id)
    except PlannerError:
        st.caption("This task no longer exists.")
        return
    use = track_store.usage(task_id)
    st.markdown(f"**{html.escape(task.title)}**")
    st.caption(f"{plan_grid.fmt_minutes(use.used_minutes)} logged of an estimated {plan_grid.fmt_minutes(use.estimate_minutes)}.")
    minutes = st.number_input("Minutes Worked", 1, track_store.MAX_LOG_MINUTES, 30, 5, key=f"lg_min_{task_id}")
    if st.button("Log Time", key=f"lg_save_{task_id}", type="primary"):
        try:
            service.log_time(task_id, int(minutes))
        except PlannerError as e:
            st.error(str(e))
            return
        st.rerun()
    logs = track_store.list_logs(task_id=task_id)
    if logs:
        st.markdown("**Logged so far**")
        tz = store.get_term().zone
        for log in reversed(logs[-8:]):
            x, y = st.columns([5, 1], vertical_alignment="center")
            local = timeutil.to_local(log.start, tz)
            x.markdown(f"{local:%b} {local.day}, {local:%I:%M %p} · {plan_grid.fmt_minutes(log.minutes)} · {'timer' if log.source == 'timer' else 'typed in'}")
            if y.button("", key=f"lg_del_{log.id}", icon=":material/delete:", help="remove this log"):
                service.delete_log(log.id)
                st.rerun()


# ---------------------------------------------------------------- the banner
def banner(report, courses, tz):
    """A warning when any task does not fit before its deadline."""
    if not report.any_negative:
        return
    tasks = {t.id: t for t in task_store.list_tasks()}
    lines = []
    for c in report.negative_items[:4]:
        t = tasks.get(c.task_id)
        if t:
            lines.append(f"**{t.title}** ({_fmt_due(t.due, tz)}): short by {plan_grid.fmt_minutes(-c.cushion_minutes)}")
    more = len(report.negative_items) - len(lines)
    st.warning("**Some work does not fit before its deadline.** " + " · ".join(lines) + (f" · and {more} more" if more > 0 else "") +
               ". Free up time, lower an estimate or move a deadline.", icon=":material/warning:")


# ---------------------------------------------------------------- the task list
def _task_row(t, cushion, courses, tz, sessions):
    name, due, plan, badge, actions = st.columns([3.6, 2.2, 1.8, 1.6, 3.6], vertical_alignment="center")
    where = _course_name(courses, t.course_id)
    name.markdown(f"**{html.escape(t.title)}**  \n{where + ' · ' if where else ''}{t.category}", unsafe_allow_html=False)
    due.markdown(_fmt_due(t.due, tz))
    planned = sum(s.minutes for s in sessions if s.task_id == t.id and s.end > _now())
    plan.markdown(f"{plan_grid.fmt_minutes(t.remaining_minutes)} left" + (f"  \n{plan_grid.fmt_minutes(planned)} planned" if planned else "") +
                  (f"  \n{plan_grid.fmt_minutes(t.logged_minutes)} used" if t.logged_minutes else ""))
    if cushion is not None:
        color = plan_grid.LEVEL_COLORS[cushion.level]
        badge.markdown(f'<span class="cu-pill" style="background:{color}" title="{LEVEL_LABEL[cushion.level].lower()}: the free time left before the deadline, '
                       f'after the work that is due by then">{_cushion_text(cushion.cushion_minutes)}</span>', unsafe_allow_html=True)
    else:
        badge.caption("")
    start, log, done, unplan, delete = actions.columns(5)
    running = track_store.running_timer() is not None
    if start.button("", key=f"tk_start_{t.id}", icon=":material/play_arrow:", disabled=running, help="start the study timer on this task" if not running else "a timer is already running"):
        _start(t.id)
        st.rerun()
    if log.button("", key=f"tk_log_{t.id}", icon=":material/more_time:", help="log time you worked on it"):
        log_dialog(t.id)
    if done.button("", key=f"tk_done_{t.id}", icon=":material/check:", help="mark done"):
        task_store.set_done(t.id, True)
        st.rerun()
    if unplan.button("", key=f"tk_unplan_{t.id}", icon=":material/event_busy:", disabled=not planned, help="remove its planned sessions that have not started"):
        service.unplan_task(t.id)
        st.rerun()
    if delete.button("", key=f"tk_del_{t.id}", icon=":material/delete:", help="delete the task"):
        task_store.delete_task(t.id)
        st.rerun()


def task_panel(report, courses, tz):
    now = _now()
    lists = task_store.task_lists(now)
    sessions = session_store.list_sessions()
    st.subheader("Tasks")
    top = st.columns([1.4, 1.4, 5])
    if top[0].button("Add Task", key="tk_add_open", type="primary", icon=":material/add_task:"):
        add_task_dialog()
    if top[1].button("Default Estimates", key="tk_defaults_open", icon=":material/timer:", help="the time a new task of each category gets, for each course"):
        defaults_dialog()
    cushions = {c.task_id: c for c in report.items}
    open_tasks = [t for t in lists.todo]
    if not open_tasks:
        st.caption("No tasks yet. Add one with a due date and an estimate, and the planner shows how much room each deadline has.")
    overdue_ids = {t.id for t in lists.overdue}
    for title, group in (("Overdue", [t for t in open_tasks if t.id in overdue_ids]), ("To Do", [t for t in open_tasks if t.id not in overdue_ids and t.due]),
                         ("No Due Date", [t for t in open_tasks if t.due is None])):
        if not group:
            continue
        st.markdown(f"**{title} ({len(group)})**")
        for t in group:
            _task_row(t, cushions.get(t.id), courses, tz, sessions)
    if lists.completed:
        with st.expander(f"Completed ({len(lists.completed)})"):
            for t in lists.completed:
                a, b = st.columns([6, 1], vertical_alignment="center")
                a.markdown(f"~~{t.title}~~ · {_course_name(courses, t.course_id)} · {plan_grid.fmt_minutes(t.logged_minutes)} logged")
                if b.button("", key=f"tk_reopen_{t.id}", icon=":material/undo:", help="open it again"):
                    task_store.set_done(t.id, False)
                    st.rerun()


# ---------------------------------------------------------------- dialogs
@st.dialog("Add Task", width="large")
def add_task_dialog():
    courses = _courses()
    choices = {0: "No Course"} | {cid: crud.label(c) for cid, c in courses.items() if crud.course_status(c) != "Completed"}
    title = st.text_input("Title", key="nt_title", placeholder="Homework 6")
    a, b = st.columns(2)
    course_id = a.selectbox("Course", list(choices), format_func=choices.get, key="nt_course")
    category = b.selectbox("Category", list(T.CATEGORIES), key="nt_category")
    default = task_store.estimate_for(course_id or None, category)
    suggestion = track_store.suggestion(category, course_id or None)
    est_key = f"nt_est_{course_id}_{category}"
    if suggestion and suggestion.minutes != default:
        where = "this course" if suggestion.scope == "course" else "all your courses"
        s1, s2 = st.columns([4, 1.4], vertical_alignment="center")
        s1.caption(f"Suggestion: **{suggestion.minutes} minutes**, from your {suggestion.samples} finished {category.lower()} tasks in {where} "
                   f"(they took {suggestion.low} to {suggestion.high} minutes).")
        s2.button("Use It", key="nt_use_suggestion", on_click=lambda: st.session_state.__setitem__(est_key, suggestion.minutes))
    c1, c2 = st.columns(2)
    has_due = c1.checkbox("Has a Due Date", True, key="nt_has_due")
    due_date = c1.date_input("Due Date", value=date.today() + timedelta(days=7), key="nt_due_date", disabled=not has_due)
    due_time = c2.time_input("Due Time", value=time(23, 59), step=300, key="nt_due_time", disabled=not has_due)
    e1, e2 = st.columns(2)
    estimate = e1.number_input("Estimate (Minutes)", T.ESTIMATE_RANGE[0], T.ESTIMATE_RANGE[1], default, 5, key=est_key,
                               help=f"the default for this course and category is {default} minutes; change it for this task only")
    ahead_on = e2.checkbox("Start Ahead", False, key="nt_ahead_on", disabled=not has_due, help="plan work only from this many days before the due date")
    ahead = e2.number_input("Days Before the Due Date", 0, T.MAX_START_AHEAD, 3, 1, key="nt_ahead", disabled=not (has_due and ahead_on))
    if st.button("Add Task", key="nt_save", type="primary", disabled=not title.strip()):
        tz = store.get_term().zone
        due = timeutil.to_utc(due_date, due_time, tz) if has_due else None
        try:
            task_store.add_task(title.strip(), course_id or None, category, due, None if estimate == default else int(estimate), int(ahead) if (has_due and ahead_on) else None)
        except PlannerError as e:
            st.error(str(e))
            return
        st.rerun()


@st.dialog("Default Estimates", width="large")
def defaults_dialog():
    courses = {cid: c for cid, c in _courses().items() if crud.course_status(c) != "Completed"}
    if not courses:
        st.caption("Add a course first.")
        return
    cid = st.selectbox("Course", list(courses), format_func=lambda i: crud.label(courses[i]), key="de_course")
    st.caption("A new task of this course gets the time below for its category, unless you give it another estimate. Tasks that exist keep their own.")
    saved = task_store.get_defaults(cid)
    cols = st.columns(3)
    values = {}
    for i, cat in enumerate(T.CATEGORIES):
        values[cat] = cols[i % 3].number_input(f"{cat} (Minutes)", T.ESTIMATE_RANGE[0], T.ESTIMATE_RANGE[1], saved.get(cat, T.DEFAULT_ESTIMATES[cat]), 5, key=f"de_{cid}_{cat}")
    if st.button("Save Defaults", key="de_save", type="primary"):
        for cat, v in values.items():
            if int(v) == T.DEFAULT_ESTIMATES[cat] and cat not in saved:
                continue
            task_store.set_default(cid, cat, int(v))
        st.rerun()


def _local(tz, day, minutes):
    """The UTC moment of `minutes` after local midnight of `day` (1440 is the next midnight)."""
    if minutes >= 24 * 60:
        return timeutil.to_utc(day + timedelta(days=1), time(0, 0), tz)
    return timeutil.to_utc(day, time(minutes // 60, minutes % 60), tz)


@st.dialog("New", width="large")
def create_dialog(day, a, b, start_kind=None):
    tz = store.get_term().zone
    kind = st.segmented_control("What", ["Study Session", "Event"], default=start_kind or "Study Session", key="cr_kind", label_visibility="collapsed") or "Study Session"
    t1, t2 = st.columns(2)
    start = t1.time_input("Start", value=time(a // 60, a % 60), step=300, key=f"cr_start_{day}_{a}_{b}")
    end = t2.time_input("End", value=time(min(b, 24 * 60 - 1) // 60, min(b, 24 * 60 - 1) % 60), step=300, key=f"cr_end_{day}_{a}_{b}")
    s_utc, e_utc = _local(tz, day, start.hour * 60 + start.minute), _local(tz, day, end.hour * 60 + end.minute)
    if kind == "Study Session":
        tasks = task_store.list_tasks(include_done=False)
        if not tasks:
            st.caption("Add a task first (Add Task below the calendar), then give it a study session here.")
            return
        report = service.cushion_report()
        names = {t.id: f"{t.title} ({plan_grid.fmt_minutes(t.remaining_minutes)} left)" for t in tasks}
        task_id = st.selectbox("Task", list(names), format_func=names.get, key="cr_task")
        for p in session_store.check_session(s_utc, e_utc):
            st.warning(p.message) if not p.hard else st.error(p.message)
        if st.button("Add Study Session", key="cr_add_session", type="primary", disabled=e_utc <= s_utc):
            _apply(lambda force: service.add_session(task_id, s_utc, e_utc, force=force), s_utc, e_utc, None, "The study session was added.")
        return
    courses = _courses()
    title = st.text_input("Title", key="cr_title", placeholder="Dentist")
    where = st.text_input("Location (Optional)", key="cr_loc")
    ch = {0: "No Course"} | {cid: crud.label(c) for cid, c in courses.items()}
    course_id = st.selectbox("Course (Optional)", list(ch), format_func=ch.get, key="cr_course")
    c1, c2, c3 = st.columns(3)
    busy = c1.toggle("Blocks Study Time", True, key="cr_busy", help="off: it shows on the calendar, but study may be planned over it")
    before = c2.number_input("Travel Before (Minutes)", 0, 240, 0, 5, key="cr_before")
    after = c3.number_input("Travel After (Minutes)", 0, 240, 0, 5, key="cr_after")
    if st.button("Add Event", key="cr_add_event", type="primary", disabled=not title.strip() or e_utc <= s_utc):
        try:
            commit_store.add_event(title.strip(), s_utc, e_utc, False, where.strip(), int(before), int(after), busy, course_id or None)
        except PlannerError as e:
            st.error(str(e))
            return
        st.rerun()


@st.dialog("Study Session")
def session_dialog(session_id):
    try:
        s = session_store.get_session(session_id)
        t = task_store.get_task(s.task_id)
    except PlannerError:
        st.caption("This session no longer exists.")
        return
    tz = store.get_term().zone
    local = timeutil.to_local(s.start, tz)
    st.markdown(f"**{html.escape(t.title)}**")
    st.caption(f"{local:%A, %b} {local.day} · {timeutil.to_local(s.start, tz):%I:%M %p} to {timeutil.to_local(s.end, tz):%I:%M %p} · {plan_grid.fmt_minutes(s.minutes)} · "
               + ("placed by hand" if s.source == "manual" else "placed by the auto-planner"))
    use = track_store.usage(s.task_id)
    mine = next((u for u in use.sessions if u.session_id == session_id), None)
    if mine:
        label = {"done": "done", "partial": "partly used", "missed": "not used", "running": "the timer is running", "now": "now", "upcoming": "still to come"}[mine.status]
        st.progress(mine.progress, text=f"Planned {plan_grid.fmt_minutes(mine.planned_minutes)} · used {plan_grid.fmt_minutes(mine.used_minutes)} ({label})")
    st.caption(f"The task: {plan_grid.fmt_minutes(use.used_minutes)} used of {plan_grid.fmt_minutes(use.estimate_minutes)} estimated"
               + (" (over the estimate)" if use.over_estimate else "") + f" · {plan_grid.fmt_minutes(use.unplanned_minutes)} not planned yet.")
    running = track_store.running_timer()
    a, b, c = st.columns(3)
    if a.button("Start Timer", key="sd_start", icon=":material/play_arrow:", disabled=running is not None or t.is_done,
                help="studies this task now and counts the time to this session"):
        _start(s.task_id, session_id)
        st.rerun()
    if b.button("Delete Session", key="sd_delete", type="primary"):
        service.delete_session(session_id)
        st.rerun()
    if c.button("Close", key="sd_close"):
        st.rerun()


@st.dialog("Event")
def event_dialog(event_id):
    ev = next((e for e in commit_store.list_events(date.today() - timedelta(days=400), date.today() + timedelta(days=400)) if e.id == event_id and e.source != "legacy"), None)
    if ev is None:
        st.caption("This event no longer exists.")
        return
    tz = store.get_term().zone
    local = timeutil.to_local(ev.start, tz)
    title = st.text_input("Title", ev.title, key=f"ev_title_{event_id}")
    where = st.text_input("Location", ev.location, key=f"ev_loc_{event_id}")
    c1, c2, c3 = st.columns(3)
    busy = c1.toggle("Blocks Study Time", ev.busy, key=f"ev_busy_{event_id}")
    before = c2.number_input("Travel Before (Minutes)", 0, 240, ev.commute_before, 5, key=f"ev_before_{event_id}")
    after = c3.number_input("Travel After (Minutes)", 0, 240, ev.commute_after, 5, key=f"ev_after_{event_id}")
    st.caption(f"{local:%A, %b} {local.day} · {local:%I:%M %p} to {timeutil.to_local(ev.end, tz):%I:%M %p}. Drag it on the calendar to move it.")
    a, b, c = st.columns(3)
    if a.button("Save", key=f"ev_save_{event_id}", type="primary", disabled=not title.strip()):
        try:
            commit_store.update_event(event_id, title.strip(), ev.start, ev.end, ev.all_day, where.strip(), int(before), int(after), busy, ev.course_id)
        except PlannerError as e:
            st.error(str(e))
            return
        st.rerun()
    if b.button("Delete", key=f"ev_delete_{event_id}"):
        commit_store.delete_event(event_id)
        st.rerun()
    if c.button("Close", key=f"ev_close_{event_id}"):
        st.rerun()


@st.dialog("Place It Anyway?")
def confirm_dialog():
    pending = st.session_state.get("cal_confirm")
    if not pending:
        return
    st.warning(pending["message"])
    a, b = st.columns(2)
    if a.button("Place It Anyway", key="cf_yes", type="primary"):
        st.session_state.pop("cal_confirm", None)
        try:
            pending["run"](True)
        except PlannerError as e:
            st.session_state["cal_toast"] = str(e)
        st.rerun()
    if b.button("Cancel", key="cf_no"):
        st.session_state.pop("cal_confirm", None)
        st.rerun()


def _apply(run, start, end, ignore_id, ok_message):
    """Run a change (run(force) raises PlannerError when refused). Only soft problems ask the student whether to go ahead; hard ones just say why."""
    try:
        run(False)
        st.session_state["cal_toast"] = ok_message
        st.rerun()
    except PlannerError as e:
        problems = session_store.check_session(start, end, ignore_id) if start and end else []
        if problems and not any(p.hard for p in problems):
            st.session_state["cal_confirm"] = {"message": str(e), "run": run}
            st.rerun()
        st.session_state["cal_toast"] = str(e)
        st.rerun()


# ---------------------------------------------------------------- what the grid reports
def handle_action(text):
    """A drag or a click in the grid: 'move|session:12|2026-09-08|600', 'resize|event:4|2026-09-08|720', 'create|2026-09-08|540|600', 'click|session:12'."""
    parts = text.split("|")[:-1]                                   # the last part is a time stamp that makes every report different
    if not parts:
        return
    tz = store.get_term().zone
    try:
        action = parts[0]
        if action == "create":
            st.session_state["cal_create"] = (date.fromisoformat(parts[1]), int(parts[2]), int(parts[3]))
        elif action == "drop":
            handle_drop(parts[1], date.fromisoformat(parts[2]), int(parts[3]))
        elif action == "click":
            st.session_state["cal_open"] = parts[1]
        elif action in ("move", "resize"):
            kind, _, raw = parts[1].partition(":")
            item_id = int(raw)
            if action == "move":
                day, minutes = date.fromisoformat(parts[2]), int(parts[3])
                new_start = _local(tz, day, minutes)
                if kind == "session":
                    cur = session_store.get_session(item_id)
                    new_end = new_start + (cur.end - cur.start)
                    _apply(lambda force: service.move_session(item_id, new_start, force=force), new_start, new_end, item_id, "The study session was moved.")
                else:
                    ev = _find_event(item_id)
                    new_end = new_start + (ev.end - ev.start)
                    commit_store.update_event(item_id, ev.title, new_start, new_end, ev.all_day, ev.location, ev.commute_before, ev.commute_after, ev.busy, ev.course_id)
                    st.session_state["cal_toast"] = "The event was moved."
            else:
                day, end_minutes = date.fromisoformat(parts[2]), int(parts[3])
                new_end = _local(tz, day, end_minutes)
                if kind == "session":
                    cur = session_store.get_session(item_id)
                    _apply(lambda force: service.resize_session(item_id, new_end=new_end, force=force), cur.start, new_end, item_id, "The study session was resized.")
                else:
                    ev = _find_event(item_id)
                    commit_store.update_event(item_id, ev.title, ev.start, new_end, ev.all_day, ev.location, ev.commute_before, ev.commute_after, ev.busy, ev.course_id)
                    st.session_state["cal_toast"] = "The event was resized."
    except PlannerError as e:
        st.session_state["cal_toast"] = str(e)
    except (ValueError, StopIteration, IndexError):
        st.session_state["cal_toast"] = "That change could not be read."


def _find_event(event_id):
    with commit_store._conn() as conn:
        row = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if row is None:
        raise PlannerError("That event no longer exists.")
    return commit_store._event_from_row(row, store.get_term())


def show_pending():
    """Open what the last drag or click asked for (a dialog), and show the message of the last change."""
    if st.session_state.get("cal_toast"):
        st.toast(st.session_state.pop("cal_toast"))
    if st.session_state.get("cal_confirm"):
        confirm_dialog()
    elif st.session_state.get("cal_create"):
        day, a, b, *kind = st.session_state.pop("cal_create")
        create_dialog(day, a, b, kind[0] if kind else None)
    elif st.session_state.get("cal_meeting"):
        owner, ident, day, minutes = st.session_state.pop("cal_meeting")
        meeting_dialog(owner, ident, day, minutes)
    elif st.session_state.get("cal_open"):
        kind, _, raw = st.session_state.pop("cal_open").partition(":")
        (session_dialog if kind == "session" else event_dialog)(int(raw))
