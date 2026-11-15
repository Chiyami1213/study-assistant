"""The planner on the Calendar page: the cushion banner, the task list with cushion badges, the dialogs (new task, new session or event by dragging, details) and the
handler of what a drag or a click in the grid reports. The scheduling logic is in the planner package; this only shows it and calls it."""
import html
import urllib.parse
from datetime import date, datetime, time, timedelta, timezone

import streamlit as st

import crud
import settings
from planner import commit_store, service, session_store, store, task_store, tasks as T, timeutil, track_store, tracking
from planner.models import AwakeTimes, PlannerError
from views import plan_grid

LEVEL_LABEL = {"green": "Comfortable", "yellow": "Tight", "red": "Does Not Fit"}


def _now():
    return datetime.now(timezone.utc)


def _courses():
    return {c["id"]: c for c in crud.list_courses(section=None)}


def _course_name(courses, course_id):
    c = courses.get(course_id)
    return (crud.show_code(c["code"]) or c["name"]) if c else ""


def _fmt_due(due, tz):
    if due is None:
        return "No due date"
    local = timeutil.to_local(due, tz)
    return f"{local:%b} {local.day}, {local:%I:%M %p}".replace(" 0", " ")


def _cushion_text(minutes):
    return ("+" if minutes > 0 else "") + plan_grid.fmt_minutes(minutes)


# ---------------------------------------------------------------- the left panel: blocks to drag into the schedule
def term_courses(courses, term_name):
    """The courses of the active term: active courses whose semester is the term's name. When none matches (the names differ), every active course."""
    active = {cid: c for cid, c in courses.items() if crud.course_status(c) == "Active"}
    named = {cid: c for cid, c in active.items() if term_name and (c.get("semester") or "").strip().lower() == term_name.strip().lower()}
    return named or active


def in_saved_order(items, ref_of, order):
    """The items sorted by the order the user dragged them into; those never dragged keep their own order, after the dragged ones."""
    rank = {r: i for i, r in enumerate(order)}
    return sorted(items, key=lambda x: rank.get(ref_of(x), len(rank)))


def _block(kind, ident, label, sub, color, dot="", hidden=False, selected=None, count=None, minutes=None):
    """One block of the panel: draggable, with the ⋯ button for its menu and a name that can be renamed by double-clicking it."""
    ref = f"{kind}:{ident}"
    more = (f'<button class="pl-show" data-show="{ref}" title="show it in the panel again">Show</button>' if hidden else
            f'<button class="pl-more" data-menu="{ref}" title="more" aria-label="more">&#8943;</button>')
    drag = "" if hidden else f' data-drag="{ref}"' + (f' data-minutes="{minutes}"' if minutes else "")
    handle = "" if hidden else '<span class="pl-handle" title="drag to change the order"><svg viewBox="0 0 12 16" width="12" height="16" fill="currentColor"><circle cx="3.5" cy="3" r="1.7"/><circle cx="3.5" cy="8" r="1.7"/><circle cx="3.5" cy="13" r="1.7"/><circle cx="8.5" cy="3" r="1.7"/><circle cx="8.5" cy="8" r="1.7"/><circle cx="8.5" cy="13" r="1.7"/></svg></span>'
    pick = f' data-pick="{ref}"' if selected is not None else ""
    tally = f'<span class="pl-count">{count}</span>' if count is not None else ""
    fill = f"background:{color}" if selected else f"background:{color}2b"                   # the block that is picked is filled with its color
    return (f'<div class="pl-item pl-{"task" if kind == "task" else "course"}{" pl-selected" if selected else ""}"{drag}{pick} style="border-left-color:{color};{fill}">'
            f'{handle}<div class="pl-main">{dot}<b class="pl-name" data-ref="{ref}" title="double-click to rename">{html.escape(label)}</b>{f"<span>{sub}</span>" if sub else ""}{tally}</div>{more}</div>')


def panel_html(tasks, courses, activities, report, usage_left, term_name=None, hidden=frozenset(), names=None, colors=None, order=()):
    """The blocks on the left of the Calendar. Dragging one onto the grid adds it there: a course or an activity becomes a weekly time, and the Custom Event block opens the
    new-event form. Each block has a ⋯ menu (details, rename, change color, hide, delete). The active term's courses are on top, the other courses in a section that is folded until
    it is opened. Tasks are not listed here: they are in the Task List, and the auto-planner places their study sessions. (`tasks`, `report` and `usage_left` stay in the call for older callers.)"""
    names, colors = names or {}, colors or {}
    in_term = dict(in_saved_order(list(term_courses(courses, term_name).items()), lambda kv: f"course:{kv[0]}", order))
    activities = in_saved_order(activities, lambda a: f"activity:{a['id']}", order)
    out = ['<div class="pl-title">Drag a block into the schedule. Drag the Custom Event block to add an event of your own.</div>',
           '<div class="pl-item pl-event" data-drag="event:0" title="drag it onto the calendar to add an event of your own"><span class="pl-grip">&#10303;</span>Custom Event</div>']

    def course_color(c):
        return colors.get(f"course:{c['id']}") or crud.course_color(c)

    def course_block(c, hide_flag=False):
        ref = f"course:{c['id']}"
        return _block("course", c["id"], names.get(ref) or crud.show_code(c["code"]) or c["name"], "", course_color(c), "", hide_flag)

    out.append(f'<div class="pl-head">Courses{" · " + html.escape(term_name) if term_name else ""}</div>')
    out += [course_block(c) for cid, c in in_term.items() if f"course:{cid}" not in hidden] or ['<div class="pl-empty">No active courses.</div>']
    shown_acts = [a for a in activities if f"activity:{a['id']}" not in hidden]
    if shown_acts:
        out.append('<div class="pl-head">Activities</div>')
        for a in shown_acts:
            ref = f"activity:{a['id']}"
            out.append(_block("activity", a["id"], names.get(ref) or a["name"], "", colors.get(ref) or a["color"] or plan_grid.ACTIVITY_COLOR))
    other_courses = in_saved_order([c for cid, c in courses.items() if cid not in in_term and crud.course_status(c) == "Active" and f"course:{cid}" not in hidden],
                                   lambda c: f"course:{c['id']}", order)
    if other_courses:
        out.append(f'<details class="pl-fold"><summary>Other Courses ({len(other_courses)})</summary>{"".join(course_block(c) for c in other_courses)}</details>')
    hidden_blocks = []
    for ref in sorted(hidden):
        kind, _, raw = ref.partition(":")
        if kind == "course" and raw.isdigit() and int(raw) in courses:
            hidden_blocks.append(course_block(courses[int(raw)], True))
        elif kind == "activity":
            a = next((x for x in activities if f"activity:{x['id']}" == ref), None)
            if a:
                hidden_blocks.append(_block("activity", a["id"], a["name"], "", a["color"] or plan_grid.ACTIVITY_COLOR, "", True))
    if hidden_blocks:
        out.append(f'<details class="pl-fold"><summary>Hidden ({len(hidden_blocks)})</summary>{"".join(hidden_blocks)}</details>')
    return wrap_panel("".join(out), nodrop=False, is_open=settings.get_calendar_panel_open())


def wrap_panel(inner, nodrop, is_open=True):
    """The panel with its splitter (drag it to change the width, double-click to go back to the usual width). When it is folded the column glides shut (see the CSS)."""
    width = settings.get_calendar_panel_width()
    usual = "" if width == settings.PANEL_WIDTH_DEFAULT else f"<style>:root {{--pl-w: {width}px;}}</style>"
    return (f'{usual}<div class="pl-wrap" data-open="{1 if is_open else 0}"><div class="pl-panel{" pl-nodrop" if nodrop else ""}">{inner}</div>'
            f'<div class="pl-split" title="drag to resize, double-click to reset"></div></div>')


def filter_panel_html(courses, term_name, counts, selected, hidden=frozenset(), names=None, colors=None, order=()):
    """The left bar of the Task List: the same blocks as the Calendar panel (grip, menu, color), and a click picks the course whose tasks are listed.
    `counts`: {"all": n, "personal": n, <course id>: n} of open tasks."""
    names, colors = names or {}, colors or {}
    in_term = dict(in_saved_order(list(term_courses(courses, term_name).items()), lambda kv: f"course:{kv[0]}", order))

    ICONS = {"all": "M3 5h18v2H3zm0 6h18v2H3zm0 6h12v2H3z", "personal": "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"}

    def plain(ref, label, color):
        icon = f'<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="{ICONS[ref]}"/></svg>'
        return (f'<div class="pl-pick{" pl-selected" if selected == ref else ""}" data-pick="{ref}">{icon}<b>{html.escape(label)}</b><span class="pl-count">{counts.get(ref, 0)}</span></div>')

    def course(cid, c, hide_flag=False):
        ref = f"course:{cid}"
        color = colors.get(ref) or crud.course_color(c)
        return _block("course", cid, names.get(ref) or crud.show_code(c["code"]) or c["name"], "", color, "", hide_flag, selected == ref, counts.get(cid, 0))

    out = [plain("all", "All Tasks", "#8b95a7"), '<div class="pl-rule"></div>', f'<div class="pl-head">Courses{" · " + html.escape(term_name) if term_name else ""}</div>']
    out += [course(cid, c) for cid, c in in_term.items() if f"course:{cid}" not in hidden] or ['<div class="pl-empty">No active courses.</div>']
    others = in_saved_order([c for cid, c in courses.items() if cid not in in_term and f"course:{cid}" not in hidden and (crud.course_status(c) == "Active" or counts.get(cid))],
                            lambda c: f"course:{c['id']}", order)
    if others:
        out.append(f'<details class="pl-fold"{" open" if any(selected == f"course:{c[chr(105)+chr(100)]}" for c in others) else ""}><summary>Other Courses ({len(others)})</summary>'
                   + "".join(course(c["id"], c) for c in others) + "</details>")
    out.append('<div class="pl-rule"></div>')
    out.append(plain("personal", "Personal / No Course", "#6b7280"))
    gone = [course(int(r.split(":")[1]), courses[int(r.split(":")[1])], True) for r in sorted(hidden) if r.startswith("course:") and r.split(":")[1].isdigit() and int(r.split(":")[1]) in courses]
    if gone:
        out.append(f'<details class="pl-fold"><summary>Hidden ({len(gone)})</summary>{"".join(gone)}</details>')
    return wrap_panel("".join(out), nodrop=True)


# ---------------------------------------------------------------- the menu of a block: details, rename, change color, hide
def _ref(ref):
    kind, _, raw = ref.partition(":")
    if kind not in ("course", "task", "activity") or not raw.isdigit():
        raise ValueError(ref)
    return kind, int(raw)


def block_name(ref):
    """(the real name, the name shown) of a block."""
    kind, ident = _ref(ref)
    if kind == "course":
        c = _courses().get(ident)
        real = (crud.show_code(c["code"]) or c["name"]) if c else "Course"
    elif kind == "task":
        real = task_store.get_task(ident).title
    else:
        real = next((a["name"] for a in commit_store.list_activities() if a["id"] == ident), "Activity")
    return real, settings.get_block_names().get(ref) or real


def rename_block(ref, name):
    """Rename a block. A task or an activity is renamed for real; a course only on the Calendar (an empty name gives it back its own). Returns None or the reason."""
    kind, ident = _ref(ref)
    name = " ".join((name or "").replace("|", " ").split())
    try:
        if kind == "course":
            settings.set_block_name(ref, name)
        elif not name:
            return "A name can not be empty."
        elif kind == "task":
            task_store.update_task(ident, title=name)
        else:
            a = next(x for x in commit_store.list_activities() if x["id"] == ident)
            commit_store.update_activity(ident, name, a["color"], a["location"] or "", bool(a["busy"]), bool(a["in_breaks"]))
    except (PlannerError, StopIteration) as e:
        return str(e) if isinstance(e, PlannerError) else "That activity no longer exists."
    return None


def recolor_block(ref, color):
    """Change the color of a block (None goes back to the usual one). A course keeps it everywhere in the app, an activity too; a task only on the Calendar."""
    kind, ident = _ref(ref)
    if kind == "course":
        crud.set_course_color(ident, color)
    elif kind == "task":
        settings.set_block_color(ref, color)
    else:
        a = next((x for x in commit_store.list_activities() if x["id"] == ident), None)
        if a:
            commit_store.update_activity(ident, a["name"], color, a["location"] or "", bool(a["busy"]), bool(a["in_breaks"]))


def switch_term(term_id):
    """Make a term the active one (the Calendar, the planner and the left bars follow it) and show today, or the first day of the term when today is outside it."""
    settings.set_active_term(term_id)
    term = settings.get_active_term()
    if term.get("awake"):                                                      # the wake-up and bedtime chosen for this term
        try:
            store.set_awake(AwakeTimes.uniform(timeutil.parse_hhmm(term["awake"]["wake"]), timeutil.parse_hhmm(term["awake"]["bed"])))
        except (PlannerError, ValueError):
            pass
    today = date.today()
    first, last = date.fromisoformat(term["start"]), date.fromisoformat(term["exam_end"])
    anchor = today if first <= today <= last else first
    st.session_state["cal_anchor"] = anchor
    st.session_state["cal_month"] = (anchor.year, anchor.month)


def _term_changed():
    """The last entry of the list opens the term manager: the list goes back to the active term."""
    if st.session_state.get("cal_term") == 0:
        active = settings.get_active_term()
        st.session_state["cal_term"] = active["id"] if active else None
        st.session_state["_open_terms"] = True


def term_select(box):
    """The drop-down of the terms; choosing one makes it the active term, and the last entry, Manage Terms, opens the term manager (add, change, delete)."""
    terms = settings.list_terms()
    if not terms:
        if box.button("Add a Term", key="cal_term_add", icon=":material/add:", help="the Calendar follows the dates of the term"):
            new_term_dialog()
        return
    active = settings.get_active_term()
    ids = [x["id"] for x in terms] + [0]
    names = {x["id"]: x["name"] for x in terms} | {0: "Manage Terms…"}
    picked = box.selectbox("Term", ids, index=ids.index(active["id"]) if active else 0, format_func=names.get, key="cal_term", label_visibility="collapsed",
                           on_change=_term_changed, help="the term the Calendar and the lists show")
    if st.session_state.pop("_open_new_term", False):
        new_term_dialog()
    elif st.session_state.pop("_open_terms", False):
        terms_dialog()
    elif picked and active and picked != active["id"]:
        switch_term(picked)
        st.rerun()


def _holidays_section(first, last):
    """The holidays and breaks that fall in the chosen term (nothing is planned on those days, except personal tasks), to remove or add. Removing asks first."""
    st.divider()
    st.markdown("**Holidays and Breaks**")
    inside = [h for h in crud.list_holidays() if h["end_date"] >= first.isoformat() and h["start_date"] <= last.isoformat()]
    if not inside:
        st.caption("No holidays in this term yet.")
    for h in inside:
        x, y = st.columns([6, 1.3], vertical_alignment="center")
        same = h["start_date"] == h["end_date"]
        x.markdown(f"**{html.escape(h['name'])}** · {h['start_date']}" + ("" if same else f" to {h['end_date']}"))
        with y.popover("Remove", icon=":material/delete:", key=f"hol_pop_{h['id']}"):
            st.caption(f"Remove {h['name']}?")
            if st.button("Yes, Remove It", key=f"rm_holiday_{h['id']}", type="primary"):
                crud.delete_holiday(h["id"])
                st.rerun()
    n1, n2, n3 = st.columns([2, 1, 1], vertical_alignment="bottom")
    hname = n1.text_input("Holiday Name", key="hol_name", placeholder="Fall Break")
    hstart = n2.date_input("Starts", value=first, key="hol_start")
    hend = n3.date_input("Ends", value=first, key="hol_end")
    if st.button("Add Holiday", key="hol_add", disabled=not hname.strip() or hend < hstart):
        crud.add_holiday(hname.strip(), hstart.isoformat(), hend.isoformat())
        st.rerun()


@st.dialog("Manage Terms", width="large")
def terms_dialog():
    """Choose, change, add and delete the terms (the active one decides the dates and which courses the left panel shows)."""
    terms = settings.list_terms()
    active = settings.get_active_term()
    if terms:
        labels = {x["id"]: x["name"] + (" (Active)" if active and x["id"] == active["id"] else "") for x in terms}
        ids = list(labels)
        tid = st.selectbox("Term", ids, index=ids.index(active["id"]) if active else 0, format_func=labels.get, key="term_pick")
        term = next(x for x in terms if x["id"] == tid)
        name = st.text_input("Name", term["name"], key=f"term_name_{tid}")
        a, b, c = st.columns(3)
        start = a.date_input("Classes Start", date.fromisoformat(term["start"]), key=f"term_start_{tid}")
        end = b.date_input("Classes End", date.fromisoformat(term["end"]), key=f"term_end_{tid}")
        exam_end = c.date_input("End of Exam Period", date.fromisoformat(term["exam_end"]), key=f"term_exam_{tid}")
        s1, s2, s3 = st.columns(3)
        if s1.button("Save Term", key=f"term_save_{tid}", type="primary", disabled=not (start <= end <= exam_end and name.strip())):
            try:
                settings.update_term(tid, name.strip(), start.isoformat(), end.isoformat(), exam_end.isoformat())
            except ValueError as e:
                st.error(str(e))
            else:
                st.rerun()
        if s2.button("Make Active", key=f"term_active_{tid}", disabled=bool(active and active["id"] == tid), help="the Calendar and its left panel show this term"):
            switch_term(tid)
            st.rerun()
        if s3.button("Delete Term", key=f"term_delete_{tid}", disabled=bool(active and active["id"] == tid), help="the active term can not be deleted; no course or task is removed"):
            settings.delete_term(tid)
            st.rerun()
        _holidays_section(start, exam_end)
    else:
        st.caption("No term yet. Add one, and the Calendar follows its dates.")
    st.divider()
    if st.button("Add New Term", key="term_new_open", icon=":material/add:", type="primary" if not terms else "secondary", help="a new term with its dates, wake-up and bedtime and holidays"):
        st.session_state["_open_new_term"] = True                              # a dialog can not open another: this one closes and the new-term form opens
        st.rerun()


@st.dialog("Add New Term", width="large")
def new_term_dialog():
    """A new term with everything that goes with it: the dates, the wake-up and bedtime to plan with, and the holidays."""
    import pandas as pd
    today = date.today()
    st.markdown("**Dates**")
    n1, n2, n3 = st.columns(3)
    nstart = n1.date_input("Classes Start", today, key="nt2_start")
    nend = n2.date_input("Classes End", today + timedelta(days=105), key="nt2_end")
    nexam = n3.date_input("End of Exam Period", today + timedelta(days=115), key="nt2_exam")
    nname = st.text_input("Name", key="nt2_name", placeholder=settings.guess_term_name(nstart))
    st.markdown("**Wake-Up and Bedtime**")
    awake = store.get_awake().for_weekday(0)
    w1, w2 = st.columns(2)
    wake = w1.time_input("Wake-Up Time", awake.wake, step=900, key="nt2_wake", help="study is planned between these two times, on every day of this term")
    bed = w2.time_input("Bedtime", awake.bed, step=900, key="nt2_bed")
    st.markdown("**Holidays and Breaks**")
    st.caption("Add a row for each break (Fall Break, Thanksgiving). Nothing is planned on those days, except personal tasks.")
    frame = pd.DataFrame({"Name": pd.Series([], dtype="string"), "Starts": pd.Series([], dtype="object"), "Ends": pd.Series([], dtype="object")})
    rows = st.data_editor(frame, key="nt2_holidays", num_rows="dynamic", hide_index=True, width="stretch",
                          column_config={"Name": st.column_config.TextColumn("Name", required=True), "Starts": st.column_config.DateColumn("Starts", format="YYYY-MM-DD", required=True),
                                         "Ends": st.column_config.DateColumn("Ends", format="YYYY-MM-DD", required=True)}).to_dict("records")
    make_active = st.checkbox("Make It the Active Term", True, key="nt2_active", help="the Calendar, the planner and the lists follow it, with this wake-up time and bedtime")
    holidays = [r for r in rows if (r.get("Name") or "").strip() and r.get("Starts") and r.get("Ends")]
    problems = []
    if not (nstart <= nend <= nexam):
        problems.append("The dates have to run from the first day of classes to the last day of classes to the end of exams.")
    if not bed > wake:
        problems.append("Bedtime has to be after the wake-up time.")
    for r in holidays:
        if r["Ends"] < r["Starts"]:
            problems.append(f"{r['Name']}: it ends before it starts.")
    for text in problems:
        st.warning(text, icon=":material/warning:")
    if st.button("Add Term", key="nt2_add", type="primary", disabled=bool(problems)):
        try:
            new_id = settings.add_term((nname or settings.guess_term_name(nstart)).strip(), nstart.isoformat(), nend.isoformat(), nexam.isoformat(),
                                       awake={"wake": timeutil.fmt_hhmm(wake), "bed": timeutil.fmt_hhmm(bed)})
        except ValueError as e:
            st.error(str(e))
            return
        for r in holidays:
            crud.add_holiday(r["Name"].strip(), r["Starts"].isoformat() if hasattr(r["Starts"], "isoformat") else str(r["Starts"]),
                             r["Ends"].isoformat() if hasattr(r["Ends"], "isoformat") else str(r["Ends"]))
        if make_active:
            switch_term(new_id)
        st.rerun()


def delete_counts(ref):
    """What deleting a block takes with it, as short phrases for the confirmation."""
    kind, ident = _ref(ref)
    if kind == "task":
        t = task_store.get_task(ident)
        n = len(session_store.list_sessions(task_id=ident))
        return [f"the task and its {n} planned study session{'s' if n != 1 else ''}", f"the {plan_grid.fmt_minutes(t.logged_minutes)} logged on it"] if t.logged_minutes else \
               [f"the task and its {n} planned study session{'s' if n != 1 else ''}"]
    if kind == "activity":
        return ["the activity with all its weekly times"]
    n_tasks = len(task_store.list_tasks(course_id=ident))
    with commit_store._conn() as conn:
        meetings = conn.execute("SELECT COUNT(*) n FROM class_meetings WHERE course_id=?", (ident,)).fetchone()["n"]
    return [f"the course with its {meetings} weekly time{'s' if meetings != 1 else ''}", "its syllabus, notes, homework, exams, quizzes and study log (the files you imported stay in the Library data folder)",
            f"{n_tasks} task{'s' if n_tasks != 1 else ''} stay, but are no longer linked to a course"]


def delete_block(ref):
    """Delete a task, an activity or a course. A course is deleted only after the database is copied to Backups\\Before Delete <time>. Returns None or the reason it failed."""
    kind, ident = _ref(ref)
    try:
        if kind == "task":
            task_store.delete_task(ident)
        elif kind == "activity":
            commit_store.delete_activity(ident)
        else:
            import sqlite3
            from datetime import datetime as _dt
            import database
            target = database.DATA_DIR / "Backups" / f"Before Delete {_dt.now():%Y-%m-%d %H-%M-%S}"
            target.mkdir(parents=True, exist_ok=True)
            src = sqlite3.connect(database.DB_PATH)
            dst = sqlite3.connect(target / "study.db")
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
            crud.delete_course(ident)
    except Exception as e:                                             # say what went wrong instead of a crash
        return str(e)
    settings.forget_block(ref)
    return None


def hide_block(ref, hidden=True):
    _ref(ref)
    settings.set_block_hidden(ref, hidden)


def handle_panel(action, ref, value=""):
    """A choice from a block's menu, a double-click rename, or Show in the hidden list: 'details', 'rename', 'color', 'hide', 'show', 'name' (the new name is in `value`)."""
    try:
        _ref(ref)
    except ValueError:
        st.session_state["cal_toast"] = "That block could not be found."
        return
    if action == "hide":
        hide_block(ref, True)
        st.session_state["cal_toast"] = "Hidden. It is in the Hidden section at the bottom of the panel."
    elif action == "show":
        hide_block(ref, False)
    elif action == "order":
        refs = [r for r in value.split(",") if r.partition(":")[0] in ("course", "task", "activity") and r.partition(":")[2].isdigit()]
        if refs:
            settings.set_block_order(refs)
    elif action == "name":
        problem = rename_block(ref, value)
        if problem:
            st.session_state["cal_toast"] = problem
    elif action in ("details", "rename", "color", "delete"):
        st.session_state["cal_item"] = (action, ref)


@st.dialog("Details", width="large")
def details_dialog(ref):
    try:
        kind, ident = _ref(ref)
    except ValueError:
        return
    tz = store.get_term().zone
    if kind == "course":
        c = _courses().get(ident)
        if not c:
            st.caption("This course no longer exists.")
            return
        st.markdown(f"### {html.escape(crud.label(c))}")
        rows = [("Semester", c.get("semester") or "(none)"), ("Status", crud.course_status(c)), ("School", c.get("school") or "(none)")]
        for k, v in rows:
            st.markdown(f"**{k}:** {html.escape(str(v))}")
        meetings = crud.list_meetings(ident)
        st.markdown("**Weekly times:** " + (" · ".join(f"{crud.meeting_days_label(m)} {m['start_time']}-{m['end_time']}" + (f" ({m['location']})" if m["location"] else "") for m in meetings) or "none yet"))
        open_tasks = [t for t in task_store.list_tasks(course_id=ident, include_done=False)]
        st.markdown(f"**Open tasks:** {len(open_tasks)}")
        if st.button("Open Course Page", key=f"dt_open_{ident}", icon=":material/open_in_new:"):
            st.session_state["page"] = "Courses"
            st.session_state["open_course"] = ident
            st.rerun()
    elif kind == "task":
        try:
            t = task_store.get_task(ident)
        except PlannerError:
            st.caption("This task no longer exists.")
            return
        use = track_store.usage(ident)
        cushion = service.cushion_report().of(ident)
        courses = _courses()
        st.markdown(f"### {html.escape(t.title)}")
        st.markdown(f"**For:** {'Personal (not school)' if t.personal else (_course_name(courses, t.course_id) or 'No course')} · **Category:** {t.category}")
        st.markdown(f"**Due:** {_fmt_due(t.due, tz)}")
        st.markdown(f"**Estimate:** {plan_grid.fmt_minutes(t.estimate_minutes)} · **Used:** {plan_grid.fmt_minutes(use.used_minutes)} · **Planned:** {plan_grid.fmt_minutes(use.planned_minutes)} · "
                    f"**Left to plan:** {plan_grid.fmt_minutes(use.unplanned_minutes)}")
        if cushion:
            st.markdown(f"**Cushion:** {_cushion_text(cushion.cushion_minutes)} ({LEVEL_LABEL[cushion.level].lower()})")
    else:
        a = next((x for x in commit_store.list_activities() if x["id"] == ident), None)
        if not a:
            st.caption("This activity no longer exists.")
            return
        st.markdown(f"### {html.escape(a['name'])}")
        st.markdown(f"**Location:** {html.escape(a['location'] or '(none)')} · **Blocks study time:** {'yes' if a['busy'] else 'no'} · **Also in breaks:** {'yes' if a['in_breaks'] else 'no'}")
        with commit_store._conn() as conn:
            ms = conn.execute("SELECT * FROM activity_meetings WHERE activity_id=? ORDER BY id", (ident,)).fetchall()
        st.markdown("**Weekly times:** " + (" · ".join(f"{crud.meeting_days_label(dict(m))} {m['start_time']}-{m['end_time']}" for m in ms) or "none yet"))
        st.caption("Click an activity on the calendar to change its weekly times.")


@st.dialog("Delete")
def delete_dialog(ref):
    try:
        kind, _ = _ref(ref)
        real, shown = block_name(ref)
        parts = delete_counts(ref)
    except (ValueError, PlannerError):
        st.caption("That block no longer exists.")
        return
    st.markdown(f"**Delete {html.escape(shown)}?**")
    st.markdown("This removes:\n" + "\n".join(f"- {p}" for p in parts))
    if kind == "course":
        st.warning("A course can not be brought back. A copy of the database is saved first in Backups, under Before Delete.", icon=":material/warning:")
        st.caption("To only take it off the Calendar panel, use Hide instead.")
    else:
        st.caption("This can not be undone. To only take it off the panel, use Hide instead.")
    a, b = st.columns(2)
    if a.button("Delete", key=f"dl_yes_{ref}", type="primary"):
        problem = delete_block(ref)
        if problem:
            st.error(problem)
            return
        st.rerun()
    if b.button("Cancel", key=f"dl_no_{ref}"):
        st.rerun()


@st.dialog("Rename")
def rename_dialog(ref):
    try:
        real, shown = block_name(ref)
    except (ValueError, PlannerError):
        st.caption("That block no longer exists.")
        return
    kind, _ = _ref(ref)
    name = st.text_input("Name", shown, key=f"rn_{ref}")
    st.caption({"course": "A course is renamed only on the Calendar; its real name does not change. Clear the box to go back to it.",
                "task": "The task's title changes everywhere.", "activity": "The activity's name changes everywhere."}[kind])
    if st.button("Rename", key=f"rn_save_{ref}", type="primary", disabled=(kind != "course" and not name.strip())):
        problem = rename_block(ref, name)
        if problem:
            st.error(problem)
            return
        st.rerun()


@st.dialog("Change Color")
def color_dialog(ref):
    try:
        kind, ident = _ref(ref)
        real, shown = block_name(ref)
    except (ValueError, PlannerError):
        st.caption("That block no longer exists.")
        return
    colors = settings.get_block_colors()
    if kind == "course":
        c = _courses().get(ident)
        current = colors.get(ref) or (crud.course_color(c) if c else "#6b7280")
    elif kind == "task":
        t = task_store.get_task(ident)
        c = _courses().get(t.course_id)
        current = colors.get(ref) or (crud.course_color(c) if c else "#6b7280")
    else:
        a = next((x for x in commit_store.list_activities() if x["id"] == ident), None)
        current = (a["color"] if a else None) or plan_grid.ACTIVITY_COLOR
    st.markdown(f"**{html.escape(shown)}**")
    color = st.color_picker("Color", current, key=f"cl_{ref}")
    st.caption({"course": "The course keeps this color everywhere in the app.", "task": "The task has this color on the Calendar; without one it takes its course's color.",
                "activity": "The activity keeps this color everywhere."}[kind])
    a, b = st.columns(2)
    if a.button("Save Color", key=f"cl_save_{ref}", type="primary"):
        recolor_block(ref, color)
        st.rerun()
    if b.button("Use the Usual Color", key=f"cl_reset_{ref}"):
        recolor_block(ref, None)
        st.rerun()


@st.dialog("Add Activity")
def activity_dialog():
    name = st.text_input("Name", key="ac_name", placeholder="Gym")
    where = st.text_input("Location (Optional)", key="ac_loc")
    color = st.color_picker("Color", "#0f766e", key="ac_color")
    busy = st.toggle("Blocks Study Time", True, key="ac_busy", help="off: it shows on the calendar, but study may be planned over it")
    in_breaks = st.toggle("Also Happens in Breaks", False, key="ac_breaks", help="work, for example, goes on during a break")
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
        _apply(lambda force: service.add_session(ident, start, end, force=force), start, end, None, "The study session was added.", task_store.get_task(ident).personal)
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
    """A warning when any task does not fit before its deadline. An x at the right end of the box dismisses it; it comes back when another task stops fitting."""
    if not report.any_negative or not settings.get_fit_warning():
        return
    short = {c.task_id for c in report.negative_items}
    if short <= st.session_state.get("_banner_dismissed", set()):
        return
    tasks = {t.id: t for t in task_store.list_tasks()}
    lines = []
    for c in report.negative_items[:4]:
        t = tasks.get(c.task_id)
        if t:
            lines.append(f"**{t.title}** ({_fmt_due(t.due, tz)}): short by {plan_grid.fmt_minutes(-c.cushion_minutes)}")
    more = len(report.negative_items) - len(lines)
    with st.container(key="cal_banner"):
        st.warning("**Some work does not fit before its deadline.** " + " · ".join(lines) + (f" · and {more} more" if more > 0 else "") +
                   ". Free up time, lower an estimate or move a deadline.", icon=":material/warning:")
        if st.button("", key="cal_banner_x", icon=":material/close:", type="tertiary", help="dismiss this warning"):
            st.session_state["_banner_dismissed"] = set(st.session_state.get("_banner_dismissed", set())) | short
            st.rerun()
        if st.button("Don't Show Again", key="cal_banner_never", type="tertiary", help="turns this warning off; it can be turned on again in Settings > Study Planner"):
            settings.set_fit_warning(False)
            st.rerun()


# ---------------------------------------------------------------- dialogs
def add_task_dialog():
    task_dialog()


@st.dialog("Task", width="large")
def task_dialog(task_id=None, default_course=None, default_personal=False):
    """Add a task (task_id None) or change one. A new task starts for `default_course` (or as a personal task) when the list shown is of that."""
    editing = None
    if task_id is not None:
        try:
            editing = task_store.get_task(task_id)
        except PlannerError:
            st.caption("This task no longer exists.")
            return
    p = f"tk{task_id or 0}_"
    courses = _courses()
    choices = {0: "No Course"} | {cid: crud.label(c) for cid, c in courses.items() if crud.course_status(c) != "Completed" or (editing and editing.course_id == cid)}
    title = st.text_input("Title", editing.title if editing else "", key=p + "title", placeholder="Homework 6")
    personal = st.toggle("Personal (Not for School)", bool(editing.personal) if editing else bool(default_personal), key=p + "personal",
                         help="a personal task has no course, and it can be planned in a break and outside the term")
    a, b = st.columns(2)
    course_id = a.selectbox("Course", list(choices), index=list(choices).index(editing.course_id if editing else default_course) if (editing.course_id if editing else default_course) in choices else 0,
                            format_func=choices.get, key=p + "course", disabled=personal)
    course_id = 0 if personal else course_id
    category = b.selectbox("Category", list(T.CATEGORIES), index=T.CATEGORIES.index(editing.category) if editing else 0, key=p + "category")
    default = task_store.estimate_for(course_id or None, category)
    est_key = f"{p}est_{course_id}_{category}"
    if not editing:
        suggestion = track_store.suggestion(category, course_id or None)
        if suggestion and suggestion.minutes != default:
            where = "this course" if suggestion.scope == "course" else "all your courses"
            s1, s2 = st.columns([4, 1.4], vertical_alignment="center")
            s1.caption(f"Suggestion: **{suggestion.minutes} minutes**, from your {suggestion.samples} finished {category.lower()} tasks in {where} "
                       f"(they took {suggestion.low} to {suggestion.high} minutes).")
            s2.button("Use It", key="nt_use_suggestion", on_click=lambda: st.session_state.__setitem__(est_key, suggestion.minutes))
    tz = store.get_term().zone
    due_local = timeutil.to_local(editing.due, tz) if editing and editing.due else None
    c1, c2 = st.columns(2)
    has_due = c1.checkbox("Has a Due Date", bool(due_local) if editing else True, key=p + "has_due")
    due_date = c1.date_input("Due Date", due_local.date() if due_local else date.today() + timedelta(days=7), key=p + "due_date", disabled=not has_due)
    due_time = c2.time_input("Due Time", due_local.time().replace(second=0, microsecond=0) if due_local else time(23, 59), step=300, key=p + "due_time", disabled=not has_due)
    e1, e2 = st.columns(2)
    estimate = e1.number_input("Estimate (Minutes)", T.ESTIMATE_RANGE[0], T.ESTIMATE_RANGE[1], editing.estimate_minutes if editing else default, 5,
                               key=est_key if not editing else p + "est",
                               help=f"the default for this course and category is {default} minutes; change it for this task only")
    ahead_on = e2.checkbox("Start Ahead", bool(editing and editing.start_ahead_days is not None), key=p + "ahead_on", disabled=not has_due,
                           help="plan work only from this many days before the due date")
    ahead = e2.number_input("Days Before the Due Date", 0, T.MAX_START_AHEAD, editing.start_ahead_days if editing and editing.start_ahead_days is not None else 3, 1,
                            key=p + "ahead", disabled=not (has_due and ahead_on))
    if st.button("Save Task" if editing else "Add Task", key=p + "save", type="primary", disabled=not title.strip()):
        due = timeutil.to_utc(due_date, due_time, tz) if has_due else None
        days = int(ahead) if (has_due and ahead_on) else None
        try:
            if editing:
                task_store.update_task(task_id, title=title.strip(), course_id=course_id or None, category=category, due=due, estimate=int(estimate),
                                       start_ahead_days=days, personal=personal)
            else:
                task_store.add_task(title.strip(), course_id or None, category, due, None if estimate == default else int(estimate), days, personal=personal)
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
    all_day = kind == "Event" and st.toggle("All Day", False, key="cr_allday", help="the event has no time of day: it shows in the all-day row")
    if all_day:
        s_utc, e_utc = timeutil.day_bounds_utc(day, tz)
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
            _apply(lambda force: service.add_session(task_id, s_utc, e_utc, force=force), s_utc, e_utc, None, "The study session was added.", task_store.get_task(task_id).personal)
        return
    courses = _courses()
    title = st.text_input("Title", key="cr_title", placeholder="Dentist")
    where = st.text_input("Location (Optional)", key="cr_loc")
    ch = {0: "No Course"} | {cid: crud.label(c) for cid, c in courses.items()}
    course_id = st.selectbox("Course (Optional)", list(ch), format_func=ch.get, key="cr_course")
    busy = st.toggle("Blocks Study Time", True, key="cr_busy", help="off: it shows on the calendar, but study may be planned over it") and not all_day
    c2, c3 = st.columns(2)
    before = c2.number_input("Travel Time Before (Minutes)", 0, 240, 0, 5, key="cr_before")
    after = c3.number_input("Travel Time After (Minutes)", 0, 240, 0, 5, key="cr_after")
    if st.button("Add Event", key="cr_add_event", type="primary", disabled=not title.strip() or e_utc <= s_utc):
        try:
            commit_store.add_event(title.strip(), s_utc, e_utc, all_day, where.strip(), 0 if all_day else int(before), 0 if all_day else int(after), busy, course_id or None)
        except PlannerError as e:
            st.error(str(e))
            return
        st.session_state["cal_anchor"] = day
        st.rerun()


# ---------------------------------------------------------------- the compact dialogs of a tile on the schedule
def _banner(name, color):
    """The title bar of a dialog, in the color of the course, the activity or the task."""
    st.markdown(f'<div class="dlg-banner" style="--c:{color}">{html.escape(name)}</div>', unsafe_allow_html=True)


def _title_box(label, value, key, color):
    """The title as a text box that looks like the colored title bar."""
    st.markdown(f"<style>.st-key-{key} input {{border-left: 4px solid {color}; background: {color}30; font-weight: 700; color: {color};}}</style>", unsafe_allow_html=True)
    return st.text_input(label, value, key=key, label_visibility="collapsed", placeholder="Title")


def _footer(key, delete_label="Delete", save_label="Save", save_disabled=False, delete_disabled=False):
    """Delete at the left, Cancel and Save at the right. Returns (delete pressed, save pressed); Cancel closes the dialog."""
    d, _gap, c, s = st.columns([1.5, 1.6, 1, 1.1], vertical_alignment="center")
    delete = d.button(delete_label, key=f"{key}_del", icon=":material/delete:", type="tertiary", disabled=delete_disabled)
    if c.button("Cancel", key=f"{key}_cancel", type="tertiary"):
        st.rerun()
    save = s.button(save_label, key=f"{key}_save", type="primary", disabled=save_disabled)
    return delete, save


def _color_for(course_id=None, ref=None, default="#6b7280"):
    prefs = settings.get_block_colors()
    if ref and prefs.get(ref):
        return prefs[ref]
    c = _courses().get(course_id)
    return crud.course_color(c) if c else default


@st.dialog("Study Session", width="medium")
def session_dialog(session_id):
    try:
        s = session_store.get_session(session_id)
        t = task_store.get_task(s.task_id)
    except PlannerError:
        st.caption("This session no longer exists.")
        return
    tz = store.get_term().zone
    local, local_end = timeutil.to_local(s.start, tz), timeutil.to_local(s.end, tz)
    k = f"sd_{session_id}"
    _banner(t.title, _color_for(t.course_id, f"task:{t.id}"))
    c1, c2, c3 = st.columns([1.7, 1, 1], vertical_alignment="center")
    day = c1.date_input("Date", local.date(), key=f"{k}_date", label_visibility="collapsed")
    start = c2.time_input("Start", local.time().replace(second=0, microsecond=0), step=300, key=f"{k}_s", label_visibility="collapsed")
    end = c3.time_input("End", local_end.time().replace(second=0, microsecond=0), step=300, key=f"{k}_e", label_visibility="collapsed")
    st.caption(("Placed by hand" if s.source == "manual" else "Placed by the auto-planner") + f" · {plan_grid.fmt_minutes(s.minutes)}")
    use = track_store.usage(s.task_id)
    mine = next((u for u in use.sessions if u.session_id == session_id), None)
    if mine:
        label = {"done": "done", "partial": "partly used", "missed": "not used", "running": "the timer is running", "now": "now", "upcoming": "still to come"}[mine.status]
        st.progress(mine.progress, text=f"Planned {plan_grid.fmt_minutes(mine.planned_minutes)} · used {plan_grid.fmt_minutes(mine.used_minutes)} ({label})")
    st.caption(f"The task: {plan_grid.fmt_minutes(use.used_minutes)} used of {plan_grid.fmt_minutes(use.estimate_minutes)} estimated"
               + (" (over the estimate)" if use.over_estimate else "") + f" · {plan_grid.fmt_minutes(use.unplanned_minutes)} not planned yet.")
    running = track_store.running_timer()
    if st.button("Start Timer", key=f"{k}_timer", icon=":material/play_arrow:", disabled=running is not None or t.is_done, help="studies this task now and counts the time to this session"):
        _start(s.task_id, session_id)
        st.rerun()
    new_start, new_end = timeutil.to_utc(day, start, tz), timeutil.to_utc(day, end, tz)
    delete, save = _footer(k, save_disabled=new_end <= new_start)
    if delete:
        service.delete_session(session_id)
        st.rerun()
    if save:
        _apply(lambda force: service.update_session(session_id, new_start, new_end, force=force), new_start, new_end, session_id, "The study session was changed.", t.personal)


def event_times(when, all_day, start, end, tz):
    """The UTC start and end of an event on the local day `when`: the whole day, or from `start` to `end` (an hour when the end is empty or not after the start)."""
    if all_day or start is None:
        return timeutil.day_bounds_utc(when, tz)
    s = timeutil.to_utc(when, start, tz)
    e = timeutil.to_utc(when, end, tz) if end and end > start else s + timedelta(hours=1)
    return s, e


def save_event(event_id, title, when, all_day, start, end, where, before, after, busy, course_id):
    """Change an event (any event, also the older dated ones). Returns None or the reason it was refused."""
    s, e = event_times(when, all_day, start, end, store.get_term().zone)
    try:
        commit_store.update_event(event_id, title.strip(), s, e, all_day, where.strip(), 0 if all_day else int(before), 0 if all_day else int(after),
                                  busy and not all_day, course_id or None)
    except PlannerError as err:
        return str(err)
    return None


@st.dialog("Event", width="medium")
def event_dialog(event_id):
    try:
        ev = _find_event(event_id)
    except PlannerError:
        st.caption("This event no longer exists.")
        return
    tz = store.get_term().zone
    local, local_end = timeutil.to_local(ev.start, tz), timeutil.to_local(ev.end, tz)
    k = f"ev_{event_id}_"
    choices = {0: "No Course"} | {cid: crud.label(c) for cid, c in _courses().items()}
    course_id = st.selectbox("Course", list(choices), index=list(choices).index(ev.course_id) if ev.course_id in choices else 0, format_func=choices.get, key=k + "course",
                             label_visibility="collapsed", help="the course of the event (it gives the event its color)")
    title = _title_box("Title", ev.title, k + "title", _color_for(course_id or None, default="#4c8dff"))
    c1, c2, c3, c4 = st.columns([1.7, 1, 1, 1.1], vertical_alignment="center")
    when = c1.date_input("Date", local.date(), key=k + "date", label_visibility="collapsed")
    all_day = c4.checkbox("All day", ev.all_day, key=k + "allday")
    start = c2.time_input("Start", local.time().replace(second=0, microsecond=0), step=300, key=k + "start", disabled=all_day, label_visibility="collapsed")
    end = c3.time_input("End", local_end.time().replace(second=0, microsecond=0) if not ev.all_day else time(min(local.hour + 1, 23), 0), step=300, key=k + "end",
                        disabled=all_day, label_visibility="collapsed")
    b2, b3 = st.columns(2)
    before = b2.number_input("Commute Before (Minutes)", 0, 240, ev.commute_before, 5, key=k + "before", disabled=all_day)
    after = b3.number_input("Commute After (Minutes)", 0, 240, ev.commute_after, 5, key=k + "after", disabled=all_day)
    where = st.text_input("Location", ev.location, key=k + "loc", icon=":material/location_on:", label_visibility="collapsed", placeholder="Location")
    free = st.toggle("Free", not ev.busy or ev.all_day, key=k + "free", disabled=all_day, help="on: it shows on the calendar, but study may be planned over it")
    delete, save = _footer(k, save_disabled=not title.strip())
    if delete:
        commit_store.delete_event(event_id)
        st.rerun()
    if save:
        problem = save_event(event_id, title, when, all_day, start, end, where, before, after, not free, course_id)
        if problem:
            st.error(problem)
            return
        st.session_state["cal_anchor"] = when
        st.rerun()


# ---------------------------------------------------------------- a class or an activity: this time only, or every week
OWNER_WORD = {"course": "class", "activity": "activity"}


def skip_this(owner, meeting_id, day):
    """This occurrence does not happen. Returns None or the reason it was refused."""
    try:
        commit_store.skip_occurrence(owner, meeting_id, day)
    except PlannerError as e:
        return str(e)
    return None


def move_this(owner, meeting_id, day, start, end, location=None):
    """This occurrence happens at another time (and place); the rest of the series does not change."""
    try:
        commit_store.override_occurrence(owner, meeting_id, day, start, end, location or None)
    except PlannerError as e:
        return str(e)
    return None


def restore_this(owner, meeting_id, day):
    commit_store.restore_occurrence(owner, meeting_id, day)


def save_series(owner, meeting_id, days, start, end, location="", end_date=None):
    """Change every occurrence of the weekly meeting (the days, the time, the place, the last day)."""
    try:
        commit_store.update_meeting(owner, meeting_id, set(days), start, end, location, end_date)
    except PlannerError as e:
        return str(e)
    return None


def remove_series(owner, meeting_id):
    """Remove the weekly meeting with all its exceptions."""
    commit_store.delete_meeting(owner, meeting_id)


def save_activity(activity_id, name, color, location, busy, in_breaks):
    try:
        commit_store.update_activity(activity_id, name, color, location, busy, in_breaks)
    except PlannerError as e:
        return str(e)
    return None


@st.dialog("Class or Activity", width="medium")
def occurrence_dialog(owner, meeting_id, day):
    try:
        m = commit_store.get_meeting(owner, meeting_id)
    except PlannerError:
        st.caption("This weekly time no longer exists.")
        return
    word = OWNER_WORD[owner]
    courses = _courses()
    activity = None
    if owner == "course":
        course = courses.get(m["course_id"])
        name = crud.label(course) if course else "Course"
        color = _color_for(m["course_id"], f"course:{m['course_id']}")
    else:
        activity = next((a for a in commit_store.list_activities() if a["id"] == m["activity_id"]), None)
        name = activity["name"] if activity else "Activity"
        color = (activity["color"] if activity else None) or plan_grid.ACTIVITY_COLOR
    exc = commit_store.exception_on(owner, meeting_id, day)
    usual_start, usual_end = timeutil.parse_hhmm(m["start_time"]), timeutil.parse_hhmm(m["end_time"])
    key = f"oc_{owner}_{meeting_id}_{day.isoformat()}"
    _banner(name, color)
    scope = st.segmented_control("Changes Apply To", ["This Day Only", "Every Week"], default="This Day Only", key=f"{key}_scope", label_visibility="collapsed") or "This Day Only"
    if exc and exc.kind == "override":
        st.caption(f"This {word} was changed for this day only (usually {m['start_time']} to {m['end_time']}).")
    elif exc and exc.kind == "skip":
        st.caption(f"This {word} is skipped on this day.")
    if scope == "This Day Only":
        cur_start = exc.start if exc and exc.kind == "override" else usual_start
        cur_end = exc.end if exc and exc.kind == "override" else usual_end
        c1, c2, c3 = st.columns([1.7, 1, 1], vertical_alignment="center")
        c1.date_input("Date", day, key=f"{key}_date", disabled=True, label_visibility="collapsed", help="to move it to another day, change the whole series or drag it")
        start = c2.time_input("Start", cur_start, step=300, key=f"{key}_s", label_visibility="collapsed")
        end = c3.time_input("End", cur_end, step=300, key=f"{key}_e", label_visibility="collapsed")
        where = st.text_input("Location", (exc.location if exc and exc.kind == "override" and exc.location is not None else m["location"]) or "", key=f"{key}_l",
                              icon=":material/location_on:", label_visibility="collapsed", placeholder="Location")
        st.caption(f"Only {day:%A, %b} {day.day} changes; the other weeks stay as they are.")
        if exc is not None and st.button("Back to Usual", key=f"{key}_restore", type="tertiary", icon=":material/undo:", help="drops the change or the skip of this day"):
            restore_this(owner, meeting_id, day)
            st.rerun()
        delete, save = _footer(key, delete_label="Delete", save_disabled=end <= start)
        if delete:
            st.session_state["cal_delete"] = f"occ:{owner}:{meeting_id}:{day.isoformat()}"            # asks what to delete, in its own window
            st.rerun()
        if save:
            problem = move_this(owner, meeting_id, day, start, end, where.strip() if where.strip() != (m["location"] or "") else None)
            if problem:
                st.error(problem)
            else:
                st.session_state["cal_toast"] = f"The {word} was changed for {day:%b} {day.day}."
                st.rerun()
    else:
        c1, c2 = st.columns(2)
        s2 = c1.time_input("Start", usual_start, step=300, key=f"{key}_s2", label_visibility="collapsed")
        e2 = c2.time_input("End", usual_end, step=300, key=f"{key}_e2", label_visibility="collapsed")
        days = st.multiselect("Weekly On", list(range(7)), default=[int(d) for d in m["days"].split(",") if d != ""], format_func=lambda d: crud.DAY_ABBR[d], key=f"{key}_days",
                              help="the days of the week it happens")
        u1, u2 = st.columns([1.2, 1.6], vertical_alignment="center")
        has_end = u1.checkbox("Until", bool(m["end_date"]), key=f"{key}_has_end")
        end_date = u2.date_input("Until", date.fromisoformat(m["end_date"]) if m["end_date"] else day + timedelta(days=84), key=f"{key}_end", disabled=not has_end, label_visibility="collapsed")
        where2 = st.text_input("Location", m["location"] or "", key=f"{key}_l2", icon=":material/location_on:", label_visibility="collapsed", placeholder="Location")
        if activity:
            free = st.toggle("Free", not bool(activity["busy"]), key=f"{key}_free", help="on: it shows on the calendar, but study may be planned over it")
        st.caption("Every week changes, from the first to the last one.")
        delete, save = _footer(key, delete_label="Delete", save_disabled=not days or e2 <= s2)
        if delete:
            st.session_state["cal_delete"] = f"occ:{owner}:{meeting_id}:{day.isoformat()}"
            st.rerun()
        if save:
            problem = save_series(owner, meeting_id, days, s2, e2, where2.strip(), end_date if has_end else None)
            if not problem and activity and free != (not bool(activity["busy"])):
                problem = save_activity(activity["id"], activity["name"], activity["color"] or plan_grid.ACTIVITY_COLOR, activity["location"] or "", not free, bool(activity["in_breaks"]))
            if problem:
                st.error(problem)
            else:
                st.session_state["cal_toast"] = "The weekly time was changed."
                st.rerun()
    if activity:
        with st.expander("The Activity Itself"):
            n1, n2 = st.columns([3, 1])
            new_name = n1.text_input("Name", activity["name"], key=f"{key}_an")
            color2 = n2.color_picker("Color", activity["color"] or plan_grid.ACTIVITY_COLOR, key=f"{key}_ac")
            where_a = st.text_input("Usual Location", activity["location"] or "", key=f"{key}_al")
            busy = st.toggle("Blocks Study Time", bool(activity["busy"]), key=f"{key}_ab")
            in_breaks = st.toggle("Also Happens in Breaks", bool(activity["in_breaks"]), key=f"{key}_abr")
            p, q = st.columns(2)
            if p.button("Save Activity", key=f"{key}_asave", disabled=not new_name.strip()):
                problem = save_activity(activity["id"], new_name, color2, where_a.strip(), busy, in_breaks)
                if problem:
                    st.error(problem)
                else:
                    st.rerun()
            sure = q.checkbox("Delete the whole activity", False, key=f"{key}_adel_on")
            if q.button("Delete Activity", key=f"{key}_adel", disabled=not sure):
                commit_store.delete_activity(activity["id"])
                st.session_state["cal_toast"] = "The activity was deleted."
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


def _apply(run, start, end, ignore_id, ok_message, personal=False):
    """Run a change (run(force) raises PlannerError when refused). Only soft problems ask the student whether to go ahead; hard ones just say why."""
    try:
        run(False)
        st.session_state["cal_toast"] = ok_message
        st.rerun()
    except PlannerError as e:
        problems = session_store.check_session(start, end, ignore_id, personal) if start and end else []
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
        elif action == "tl":
            if parts[1] == "pick" and (parts[2] in ("all", "personal") or _ref(parts[2])[0] == "course"):
                st.session_state["tl_which"] = parts[2]
        elif action == "zoom":
            settings.set_calendar_hour_px(int(parts[1]))
        elif action == "panelw":
            settings.set_calendar_panel_width(int(parts[1]))
        elif action == "panel":
            handle_panel(parts[1], parts[2], urllib.parse.unquote(parts[3]) if len(parts) > 3 else "")
        elif action == "drop":
            handle_drop(parts[1], date.fromisoformat(parts[2]), int(parts[3]))
        elif action == "click":
            st.session_state["cal_open"] = parts[1]
        elif action == "delete":
            st.session_state["cal_delete"] = parts[1]
        elif action in ("move", "resize", "resizetop") and parts[1].startswith("occ:"):
            plan = occurrence_plan(action, parts[1], date.fromisoformat(parts[2]), int(parts[3]))
            if isinstance(plan, dict):
                st.session_state["cal_change"] = plan                                       # asks what to change, in its own window
            elif plan:
                st.session_state["cal_toast"] = plan
        elif action in ("move", "resize", "resizetop"):
            kind, _, raw = parts[1].partition(":")
            item_id = int(raw)
            if action == "move":
                day, minutes = date.fromisoformat(parts[2]), int(parts[3])
                new_start = _local(tz, day, minutes)
                if kind == "session":
                    cur = session_store.get_session(item_id)
                    new_end = new_start + (cur.end - cur.start)
                    _apply(lambda force: service.move_session(item_id, new_start, force=force), new_start, new_end, item_id, "The study session was moved.", task_store.get_task(cur.task_id).personal)
                else:
                    ev = _find_event(item_id)
                    new_end = new_start + (ev.end - ev.start)
                    commit_store.update_event(item_id, ev.title, new_start, new_end, ev.all_day, ev.location, ev.commute_before, ev.commute_after, ev.busy, ev.course_id)
                    st.session_state["cal_toast"] = "The event was moved."
            elif action == "resizetop":
                day, start_minutes = date.fromisoformat(parts[2]), int(parts[3])
                new_start = _local(tz, day, start_minutes)
                if kind == "session":
                    cur = session_store.get_session(item_id)
                    _apply(lambda force: service.update_session(item_id, new_start, cur.end, force=force), new_start, cur.end, item_id, "The study session was changed.",
                           task_store.get_task(cur.task_id).personal)
                else:
                    ev = _find_event(item_id)
                    commit_store.update_event(item_id, ev.title, new_start, ev.end, ev.all_day, ev.location, ev.commute_before, ev.commute_after, ev.busy, ev.course_id)
                    st.session_state["cal_toast"] = "The event was changed."
            else:
                day, end_minutes = date.fromisoformat(parts[2]), int(parts[3])
                new_end = _local(tz, day, end_minutes)
                if kind == "session":
                    cur = session_store.get_session(item_id)
                    _apply(lambda force: service.resize_session(item_id, new_end=new_end, force=force), cur.start, new_end, item_id, "The study session was resized.", task_store.get_task(cur.task_id).personal)
                else:
                    ev = _find_event(item_id)
                    commit_store.update_event(item_id, ev.title, ev.start, new_end, ev.all_day, ev.location, ev.commute_before, ev.commute_after, ev.busy, ev.course_id)
                    st.session_state["cal_toast"] = "The event was resized."
    except PlannerError as e:
        st.session_state["cal_toast"] = str(e)
    except (ValueError, StopIteration, IndexError):
        st.session_state["cal_toast"] = "That change could not be read."


@st.dialog("Deleting a Repeating Event")
def occurrence_delete_dialog(owner, meeting_id, day):
    """What to delete of a repeating class or activity: only this day, this and the following ones on this weekday, this and everything after it, or the whole series."""
    try:
        meeting = commit_store.get_meeting(owner, meeting_id)
    except PlannerError:
        st.caption("This weekly time no longer exists.")
        return
    weekdays = [d for d in meeting["days"].split(",") if d != ""]
    choices = [("this", "This Event", "primary")]
    if len(weekdays) > 1:
        choices.append(("weekday", f"This and Following {day:%A} Events", "secondary"))
    choices += [("following", "This and All Following Events", "secondary"), ("all", "All Events", "secondary")]
    for scope, label, kind in choices:
        if st.button(label, key=f"od_{scope}_{owner}_{meeting_id}_{day.isoformat()}", type=kind, width="stretch"):
            try:
                st.session_state["cal_toast"] = commit_store.delete_occurrences(owner, meeting_id, day, scope)
            except PlannerError as e:
                st.session_state["cal_toast"] = str(e)
            st.rerun()
    if st.button("Cancel", key=f"od_cancel_{owner}_{meeting_id}_{day.isoformat()}", type="tertiary", width="stretch"):
        st.rerun()


@st.dialog("Delete?")
def confirm_delete_dialog(kind, item_id):
    """The bin of an event or a study session asks first."""
    try:
        if kind == "event":
            name = _find_event(item_id).title
        else:
            s = session_store.get_session(item_id)
            name = task_store.get_task(s.task_id).title + " (study session)"
    except PlannerError:
        st.caption("That no longer exists.")
        return
    st.markdown(f"**Delete {html.escape(name)}?**")
    st.caption("This can not be undone.")
    a, b = st.columns(2)
    if a.button("Delete", key=f"cd_yes_{kind}_{item_id}", type="primary", width="stretch"):
        if kind == "event":
            commit_store.delete_event(item_id)
        else:
            service.delete_session(item_id)
        st.session_state["cal_toast"] = "Deleted."
        st.rerun()
    if b.button("Cancel", key=f"cd_no_{kind}_{item_id}", width="stretch"):
        st.rerun()


def open_delete(ref):
    """Open the right question for a tile's bin: the choices for a repeating class or activity, a plain question for an event or a study session."""
    try:
        if ref.startswith("occ:"):
            _, owner, mid, day = ref.split(":")
            occurrence_delete_dialog(owner, int(mid), date.fromisoformat(day))
        else:
            kind, _, raw = ref.partition(":")
            if kind not in ("event", "session"):
                raise ValueError(ref)
            confirm_delete_dialog(kind, int(raw))
    except ValueError:
        st.toast("That could not be deleted.")


def occurrence_plan(action, ref, target_day, minutes):
    """A class or an activity dragged on the grid: moved up or down, or its top or bottom edge dragged. Returns what was asked as a dict (owner, meeting id, day, the new start and end), or the
    text of why it can not be done. A repeating class stays on its day: to put it on another day, change the weekly time."""
    try:
        _, owner, mid, day_text = ref.split(":")
        mid, day = int(mid), date.fromisoformat(day_text)
        meeting = commit_store.get_meeting(owner, mid)
    except (ValueError, PlannerError):
        return "That could not be changed."
    exc = commit_store.exception_on(owner, mid, day)
    cur_start = exc.start if exc and exc.kind == "override" else timeutil.parse_hhmm(meeting["start_time"])
    cur_end = exc.end if exc and exc.kind == "override" else timeutil.parse_hhmm(meeting["end_time"])
    clock = lambda m: time(min(m, 24 * 60 - 1) // 60, min(m, 24 * 60 - 1) % 60)
    minutes_of = lambda t: t.hour * 60 + t.minute
    if action == "move":
        if target_day != day:
            return "A class repeats every week. To put it on another day, change its weekly time (click it, then Every Week)."
        length = minutes_of(cur_end) - minutes_of(cur_start)
        start, end = clock(minutes), clock(minutes + length)
    elif action == "resizetop":
        start, end = clock(minutes), cur_end
    else:
        start, end = cur_start, clock(minutes)
    if minutes_of(end) <= minutes_of(start):
        return "The end has to be after the start."
    if (start, end) == (cur_start, cur_end):
        return ""
    return {"owner": owner, "meeting": mid, "day": day, "start": start, "end": end, "weekdays": len([d for d in meeting["days"].split(",") if d != ""])}


@st.dialog("Changing a Repeating Event")
def occurrence_change_dialog(plan):
    """After a class or an activity was dragged: change only this event, this and the following ones on this weekday, this and all following, or all of them."""
    day = plan["day"]
    st.caption(f"New time: {plan['start']:%H:%M} to {plan['end']:%H:%M}")
    choices = [("this", "This Event", "primary")]
    if plan["weekdays"] > 1:
        choices.append(("weekday", f"This and Following {day:%A} Events", "secondary"))
    choices += [("following", "This and All Following Events", "secondary"), ("all", "All Events", "secondary")]
    tag = f"{plan['owner']}_{plan['meeting']}_{day.isoformat()}"
    for scope, label, kind in choices:
        if st.button(label, key=f"oc_{scope}_{tag}", type=kind, width="stretch"):
            try:
                st.session_state["cal_toast"] = commit_store.change_occurrences(plan["owner"], plan["meeting"], day, scope, plan["start"], plan["end"])
            except PlannerError as e:
                st.session_state["cal_toast"] = str(e)
            st.rerun()
    if st.button("Cancel", key=f"oc_cancel_{tag}", type="tertiary", width="stretch"):
        st.rerun()


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
    if st.session_state.get("cal_change"):
        occurrence_change_dialog(st.session_state.pop("cal_change"))
    elif st.session_state.get("cal_delete"):
        open_delete(st.session_state.pop("cal_delete"))
    elif st.session_state.get("cal_confirm"):
        confirm_dialog()
    elif st.session_state.get("cal_create"):
        day, a, b, *kind = st.session_state.pop("cal_create")
        create_dialog(day, a, b, kind[0] if kind else None)
    elif st.session_state.get("cal_item"):
        action, ref = st.session_state.pop("cal_item")
        {"details": details_dialog, "rename": rename_dialog, "color": color_dialog, "delete": delete_dialog}[action](ref)
    elif st.session_state.get("cal_meeting"):
        owner, ident, day, minutes = st.session_state.pop("cal_meeting")
        meeting_dialog(owner, ident, day, minutes)
    elif st.session_state.get("cal_open"):
        what = st.session_state.pop("cal_open")
        try:
            if what.startswith("occ:"):
                _, owner, mid, day = what.split(":")
                if owner not in OWNER_WORD:
                    raise ValueError(owner)
                occurrence_dialog(owner, int(mid), date.fromisoformat(day))
            else:
                kind, _, raw = what.partition(":")
                (session_dialog if kind == "session" else event_dialog)(int(raw))
        except ValueError:
            st.toast("That could not be opened.")
