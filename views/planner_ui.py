"""The planner on the Calendar page: the cushion banner, the task list with cushion badges, the dialogs (new task, new session or event by dragging, details) and the
handler of what a drag or a click in the grid reports. The scheduling logic is in the planner package; this only shows it and calls it."""
import html
from datetime import date, datetime, time, timedelta, timezone

import streamlit as st

import crud
from planner import commit_store, service, session_store, store, task_store, tasks as T, timeutil
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
    name, due, plan, badge, actions = st.columns([4, 2.4, 1.8, 1.7, 2.6], vertical_alignment="center")
    where = _course_name(courses, t.course_id)
    name.markdown(f"**{html.escape(t.title)}**  \n{where + ' · ' if where else ''}{t.category}", unsafe_allow_html=False)
    due.markdown(_fmt_due(t.due, tz))
    planned = sum(s.minutes for s in sessions if s.task_id == t.id and s.end > _now())
    plan.markdown(f"{plan_grid.fmt_minutes(t.remaining_minutes)} left" + (f"  \n{plan_grid.fmt_minutes(planned)} planned" if planned else ""))
    if cushion is not None:
        color = plan_grid.LEVEL_COLORS[cushion.level]
        badge.markdown(f'<span class="cu-pill" style="background:{color}" title="{LEVEL_LABEL[cushion.level].lower()}: the free time left before the deadline, '
                       f'after the work that is due by then">{_cushion_text(cushion.cushion_minutes)}</span>', unsafe_allow_html=True)
    else:
        badge.caption("")
    done, unplan, delete = actions.columns(3)
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
    c1, c2 = st.columns(2)
    has_due = c1.checkbox("Has a Due Date", True, key="nt_has_due")
    due_date = c1.date_input("Due Date", value=date.today() + timedelta(days=7), key="nt_due_date", disabled=not has_due)
    due_time = c2.time_input("Due Time", value=time(23, 59), step=300, key="nt_due_time", disabled=not has_due)
    e1, e2 = st.columns(2)
    estimate = e1.number_input("Estimate (Minutes)", T.ESTIMATE_RANGE[0], T.ESTIMATE_RANGE[1], default, 5, key=f"nt_est_{course_id}_{category}",
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
def create_dialog(day, a, b):
    tz = store.get_term().zone
    kind = st.segmented_control("What", ["Study Session", "Event"], default="Study Session", key="cr_kind", label_visibility="collapsed") or "Study Session"
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
    a, b = st.columns(2)
    if a.button("Delete Session", key="sd_delete", type="primary"):
        service.delete_session(session_id)
        st.rerun()
    if b.button("Close", key="sd_close"):
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
        day, a, b = st.session_state.pop("cal_create")
        create_dialog(day, a, b)
    elif st.session_state.get("cal_open"):
        kind, _, raw = st.session_state.pop("cal_open").partition(":")
        (session_dialog if kind == "session" else event_dialog)(int(raw))
