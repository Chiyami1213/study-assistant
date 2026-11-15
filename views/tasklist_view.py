"""The Task List page (inside the Calendar page, next to the Calendar): every task in one table, filtered by course, grouped and sorted by due date, category or course.

The sorting and grouping are plain functions (`sort_tasks`, `group_tasks`, `filter_tasks`) so they can be tested without the page."""
import html
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

import streamlit as st

import crud
import settings
from database import data_path
from planner import commit_store, service, session_store, syllabus_read, task_store, tasks as T, timeutil, track_store
from planner.models import PlannerError
from views import plan_grid, planner_ui

SORTS = ["Due Date", "Category", "Course", "Title", "Time Left", "Cushion"]
GROUPS = ["None", "Course", "Category", "Due Week"]
NO_COURSE = "Personal / No Course"


# ---------------------------------------------------------------- pure: filter, sort, group
def course_label(courses, task):
    if task.personal:
        return "Personal"
    c = courses.get(task.course_id)
    return (crud.show_code(c["code"]) or c["name"]) if c else ""


def filter_tasks(tasks, courses, which="all", query="", show_done=False):
    """`which`: "all", "course:<id>" or "personal" (a personal task, or one with no course). `query`: part of the title, the course or the category."""
    out = []
    q = (query or "").strip().lower()
    for t in tasks:
        if t.is_done and not show_done:
            continue
        if which == "personal" and not (t.personal or t.course_id is None):
            continue
        if which.startswith("course:") and t.course_id != int(which.split(":")[1]):
            continue
        if q and q not in f"{t.title} {course_label(courses, t)} {t.category}".lower():
            continue
        out.append(t)
    return out


def sort_tasks(tasks, key="Due Date", descending=False, courses=None, cushions=None):
    """Sorted by the chosen key (ties by due date, then title). A task without a due date is always last when sorting by date. `cushions`: {task id: minutes of cushion};
    ascending puts the tightest first, a task with no cushion (no due date) last."""
    courses, cushions = courses or {}, cushions or {}
    keys = {"Due Date": None, "Category": lambda t: T.CATEGORIES.index(t.category), "Course": lambda t: course_label(courses, t).lower() or chr(0xFFFF),
            "Title": lambda t: t.title.lower(), "Time Left": lambda t: t.remaining_minutes, "Cushion": lambda t: cushions.get(t.id, 10 ** 9)}
    if key not in keys:
        raise ValueError(f"Sort by one of: {', '.join(SORTS)}.")
    if key == "Due Date":
        dated = sorted((t for t in tasks if t.due is not None), key=lambda t: (t.due, t.title.lower(), t.id), reverse=descending)
        return dated + sorted((t for t in tasks if t.due is None), key=lambda t: (t.title.lower(), t.id))
    tie = lambda t: (t.due is None, t.due.timestamp() if t.due else 0, t.title.lower(), t.id)
    return sorted(tasks, key=lambda t: (keys[key](t),) + tie(t), reverse=False) if not descending else \
        sorted(sorted(tasks, key=tie), key=keys[key], reverse=True)


def _week_start(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def group_tasks(tasks, group="None", courses=None, tz=None, today=None):
    """[(heading, [tasks])] in the order of `tasks` inside each group; the groups are ordered by course, category or week. "None": one group with no heading."""
    courses = courses or {}
    if group == "None":
        return [("", list(tasks))]
    buckets = {}
    for t in tasks:
        if group == "Course":
            label = course_label(courses, t) or NO_COURSE
            order = (label == NO_COURSE or label == "Personal", label.lower())
        elif group == "Category":
            label, order = t.category, T.CATEGORIES.index(t.category)
        elif group == "Due Week":
            if t.due is None:
                label, order = "No Due Date", (1, "")
            else:
                first = _week_start(timeutil.local_day(t.due, tz))
                this = _week_start(today) if today else None
                last = first + timedelta(days=6)
                label = ("This Week · " if first == this else "") + f"{first:%b} {first.day} – {last:%b} {last.day}"
                order = (0, first.isoformat())
        else:
            raise ValueError(f"Group by one of: {', '.join(GROUPS)}.")
        buckets.setdefault(label, (order, []))[1].append(t)
    return [(label, rows) for label, (order, rows) in sorted(buckets.items(), key=lambda kv: kv[1][0])]


# ---------------------------------------------------------------- import from a syllabus
def file_text(path):
    """The text of a syllabus file in the Library (PDF, HTML or plain text); "" when it can not be read. A file is read again only when it changed."""
    p = Path(path)
    try:
        return _file_text(str(p), p.stat().st_mtime_ns)
    except OSError:
        return ""


@st.cache_data(show_spinner=False, max_entries=64)
def _file_text(path, mtime):
    p = Path(path)
    try:
        if p.suffix.lower() == ".pdf":
            import pymupdf
            return "\n".join(page.get_text() for page in pymupdf.open(str(p)))
        raw = p.read_text(encoding="utf-8", errors="ignore")
        if p.suffix.lower() in (".html", ".htm"):
            raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
            raw = re.sub(r"(?i)</?(p|div|tr|li|br|h\d|section|table)[^>]*>", "\n", raw)
            raw = html.unescape(re.sub(r"<[^>]+>", " ", raw))
        return raw
    except Exception:
        return ""


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_days(text):
    """Day numbers (Monday = 0) from text such as "Mon, Wed" or "Tuesday Thursday"."""
    return sorted({DAY_NAMES.index(w[:3].capitalize()) for w in re.findall(r"[A-Za-z]+", text or "") if w[:3].capitalize() in DAY_NAMES})


EXAM_WORDS = re.compile(r"midterm|final|exam|test", re.I)


def course_work(course_id, today=None):
    """The homework and the exams that are already in a course page (Homework with a due date, and the exam events), as rows for the import. A graded homework, or an exam
    that has passed, is a finished task. An exam is already on the Calendar, so it is not put there again."""
    today = (today or date.today()).isoformat()
    course = next((c for c in crud.list_courses(section=None) if c["id"] == course_id), None)
    code = (crud.show_code(course["code"]) or course["name"]) if course else ""
    rows = []
    for h in crud.list_homework(course_id):
        if not h["due_date"]:
            continue
        done = h.get("score") is not None or h["status"] == "verified"
        rows.append({"Add": True, "Title": h["title"].strip(), "Category": "Homework", "Due Date": date.fromisoformat(h["due_date"]), "Due Time": time.fromisoformat(h["due_time"] or "23:59"),
                     "Estimate (Minutes)": None, "On Calendar": False, "Done": done})
    events = crud._all("SELECT * FROM events WHERE course_id=? ORDER BY date, id", (course_id,))
    for e in events:
        if not EXAM_WORDS.search(e["title"]):
            continue
        title = e["title"].strip()
        if code and title.lower().startswith(code.lower()):
            title = title[len(code):].strip(" -:") or title
        rows.append({"Add": True, "Title": title, "Category": "Exam", "Due Date": date.fromisoformat(e["date"]), "Due Time": time.fromisoformat(e.get("time") or "09:00"),
                     "Estimate (Minutes)": None, "On Calendar": False, "Done": e.get("score") is not None or e["date"] < today})
    return rows


def syllabus_files(course_id):
    return [b for b in crud.list_books() if course_id in b["course_ids"] and b["kind"] == "Syllabus"]


def syllabus_items(course_id, text=None):
    """What the course's syllabus file in the Library says (or the given text): ([ImportItem], [MeetingGuess])."""
    if text is None:
        text = "\n".join(file_text(data_path(b["pdf_path"])) for b in syllabus_files(course_id))
    if not text.strip():
        return [], []
    bounds = settings.get_semester()
    first, last = date.fromisoformat(bounds["start"]), date.fromisoformat(bounds["exam_end"])
    return syllabus_read.find_items(text, first, last), syllabus_read.find_meetings(text)


def _norm(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def import_rows(course_id, items, own=()):
    """The rows of the table the student checks: the work in the course page (`own`), then what the syllabus adds to it, with Already Added marked (a task of that course with
    the same title). A syllabus item that is the same work as one in the course page (same title, or same kind of work on the same day) is not listed twice."""
    have = {_norm(t.title) for t in task_store.list_tasks(course_id=course_id)}
    rows = [dict(r) for r in own]
    seen_title = {_norm(r["Title"]) for r in rows}
    seen_day = {(r["Category"], r["Due Date"]) for r in rows}
    for x in items:
        if _norm(x.title) in seen_title or (x.category, x.due) in seen_day:
            continue
        rows.append({"Add": True, "Title": x.title, "Category": x.category, "Due Date": x.due, "Due Time": time.fromisoformat(x.due_time),
                     "Estimate (Minutes)": None, "On Calendar": x.category == "Exam", "Done": False})
    for r in rows:
        dup = _norm(r["Title"]) in have
        r["Add"] = r["Add"] and not dup
        r["Status"] = "Already Added" if dup else "Done" if r.get("Done") else "New"
    rows.sort(key=lambda r: (r["Due Date"], r["Title"]))
    return rows


def apply_import(course_id, rows, meetings, tz):
    """Save the checked rows: a task each (finished when the row says so), and an event on the Calendar when asked, and the checked class times.
    Returns (tasks added, events added, class times added, problems)."""
    course = next((c for c in crud.list_courses(section=None) if c["id"] == course_id), None)
    code = (crud.show_code(course["code"]) or course["name"]) if course else ""
    tasks_n = events_n = meetings_n = 0
    problems = []
    for r in rows:
        title, day = (r.get("Title") or "").strip(), r.get("Due Date")
        if not r.get("Add") or not title or not day:
            continue
        category = r.get("Category") if r.get("Category") in T.CATEGORIES else "Other"
        at = r.get("Due Time") or time(23, 59)
        estimate = r.get("Estimate (Minutes)")
        try:
            due = timeutil.to_utc(day, at, tz)
            new_id = task_store.add_task(title, course_id, category, due, int(estimate) if estimate and estimate == estimate else None, None, source="syllabus")
            if r.get("Done"):
                task_store.set_done(new_id, True)
            tasks_n += 1
            if r.get("On Calendar"):
                exam = category == "Exam"
                commit_store.add_event(f"{code} {title}".strip(), due, due + timedelta(minutes=120 if exam else 30), False, "", 0, 0, exam, course_id)
                events_n += 1
        except (PlannerError, ValueError, TypeError) as e:
            problems.append(f"{title}: {e}")
    for m in meetings:
        days = parse_days(m.get("Days"))
        if not m.get("Add") or not days or not m.get("Start") or not m.get("End"):
            continue
        try:
            commit_store.add_course_meeting(course_id, set(days), m["Start"], m["End"], (m.get("Location") or "").strip())
            meetings_n += 1
        except (PlannerError, ValueError, TypeError) as e:
            problems.append(f"Class time {m.get('Days')}: {e}")
    return tasks_n, events_n, meetings_n, problems


def course_plan(course_id):
    """(rows, class time guesses) for one course: its own homework and exams, plus what its syllabus file adds."""
    items, guesses = syllabus_items(course_id)
    return import_rows(course_id, items, course_work(course_id)), (guesses if not crud.list_meetings(course_id) else [])


def auto_import(course_ids, tz):
    """Read each course (its page and its syllabus file) and add every new task, without asking. Class times are added only for a course that has none.
    Returns [(course id, tasks added, events added, class times added, problems)]."""
    out = []
    for cid in course_ids:
        rows, guesses = course_plan(cid)
        meetings = [{"Add": True, "Days": ", ".join(DAY_NAMES[d] for d in g.days), "Start": time.fromisoformat(g.start), "End": time.fromisoformat(g.end), "Location": g.location} for g in guesses]
        out.append((cid, *apply_import(cid, rows, meetings, tz)))
    return out


def _term_course_ids():
    all_courses = {c["id"]: c for c in crud.list_courses(section=None) if crud.course_status(c) != "Completed"}
    term = settings.get_active_term()
    in_term = planner_ui.term_courses(all_courses, term["name"] if term else None)
    return all_courses, list(in_term)


@st.dialog("Import From Syllabus", width="large")
def import_dialog():
    """Reads the homework, quizzes and exams of each course of the term (what its course page has and what its syllabus in the Library says) and adds every new one to the
    Task List at once. Everything added can be changed or deleted in the list afterwards; one course can also be checked row by row before it is added."""
    import pandas as pd
    all_courses, term_ids = _term_course_ids()
    if not all_courses:
        st.caption("Add a course first.")
        return
    tz = planner_ui.store.get_term().zone
    others = [i for i in all_courses if i not in term_ids]
    picked, plans = [], {}

    def course_line(cid, default):
        """A tick box for a course; the ticked ones are read and counted."""
        if st.checkbox(crud.label(all_courses[cid]), default, key=f"si_pick_{cid}"):
            picked.append(cid)
            plans[cid] = course_plan(cid)
            rows, guesses = plans[cid]
            files = len(syllabus_files(cid))
            fresh = sum(1 for r in rows if r["Add"])
            st.caption(f"{fresh} new task{'s' if fresh != 1 else ''} · {sum(1 for r in rows if r['Status'] == 'Already Added')} already added · "
                       + (f"{files} syllabus file{'s' if files != 1 else ''} in the Library" if files else "no syllabus in the Library")
                       + (f" · {len(guesses)} class time{'s' if len(guesses) != 1 else ''} found" if guesses else ""))

    st.markdown("**Active Courses of This Term**")
    if not term_ids:
        st.caption("No active course in this term.")
    for cid in term_ids:
        course_line(cid, True)
    if others:
        with st.expander(f"Other Courses, Self-Study Included ({len(others)}, Not Ticked Unless You Choose Them)"):
            for cid in others:
                course_line(cid, False)
    total = sum(1 for cid in picked for r in plans[cid][0] if r["Add"])
    if st.button(f"Import {total} New Task{'s' if total != 1 else ''}", key="si_all", type="primary", disabled=not picked or (total == 0 and not any(plans[c][1] for c in picked))):
        results = auto_import(picked, tz)
        n, ev, mt = sum(r[1] for r in results), sum(r[2] for r in results), sum(r[3] for r in results)
        bad = [p for r in results for p in r[4]]
        st.session_state["cal_toast"] = (f"Imported {n} task{'s' if n != 1 else ''}" + (f", {ev} exam{'s' if ev != 1 else ''} on the Calendar" if ev else "") + (f", {mt} class time{'s' if mt != 1 else ''}" if mt else "")
                                         + ". Change or delete any of them in the list." + (f" Not added: {'; '.join(bad[:3])}" if bad else ""))
        st.rerun()
    st.caption("Only the ticked courses are read. A syllabus file is read from the Library (type Syllabus). A task that is already in the list is never added twice.")
    with st.expander("Check One Course First, or Paste a Schedule"):
        ids = term_ids + [i for i in all_courses if i not in term_ids]
        cid = st.selectbox("Course", ids, format_func=lambda i: crud.label(all_courses[i]), key="si_course")
        pasted = st.text_area("Schedule Text (Optional)", key=f"si_paste_{cid}", height=110, placeholder="Paste the course schedule from a syllabus here to read it as well")
        rows, guesses = course_plan(cid)
        if pasted.strip():
            items, g2 = syllabus_items(cid, pasted)
            rows = import_rows(cid, items, [r for r in rows if r["Status"] != "New" or True])
            guesses = g2 if not crud.list_meetings(cid) else []
        st.markdown(f"**Found {len(rows)} dated item{'s' if len(rows) != 1 else ''}**" + (f" and {len(guesses)} class time{'s' if len(guesses) != 1 else ''}" if guesses else "")
                    + ". Change anything, add rows with the plus at the bottom of the table, and uncheck what you do not want.")
        frame = pd.DataFrame(rows, columns=["Add", "Title", "Category", "Due Date", "Due Time", "Estimate (Minutes)", "On Calendar", "Done", "Status"])
        edited = st.data_editor(
            frame, key=f"si_items_{cid}_{len(rows)}_{bool(pasted.strip())}", num_rows="dynamic", hide_index=True, width="stretch",
            column_config={"Add": st.column_config.CheckboxColumn("Add", default=True), "Title": st.column_config.TextColumn("Title", required=True),
                           "Category": st.column_config.SelectboxColumn("Category", options=list(T.CATEGORIES), default="Homework", required=True),
                           "Due Date": st.column_config.DateColumn("Due Date", format="YYYY-MM-DD", required=True), "Due Time": st.column_config.TimeColumn("Due Time", format="HH:mm", step=300),
                           "Estimate (Minutes)": st.column_config.NumberColumn("Estimate (Minutes)", min_value=5, max_value=6000, step=5, help="empty: the default of the course and category"),
                           "On Calendar": st.column_config.CheckboxColumn("On Calendar", default=False, help="also put it on the Calendar as an event"),
                           "Done": st.column_config.CheckboxColumn("Done", default=False, help="add it as a finished task"),
                           "Status": st.column_config.TextColumn("Status", disabled=True)})
        meeting_rows = []
        if guesses:
            st.markdown("**Class times** (this course has none yet)")
            mframe = pd.DataFrame([{"Add": True, "Days": ", ".join(DAY_NAMES[d] for d in g.days), "Start": time.fromisoformat(g.start), "End": time.fromisoformat(g.end), "Location": g.location} for g in guesses])
            medited = st.data_editor(mframe, key=f"si_meet_{cid}_{len(guesses)}", num_rows="dynamic", hide_index=True, width="stretch",
                                     column_config={"Add": st.column_config.CheckboxColumn("Add", default=True), "Days": st.column_config.TextColumn("Days", help="for example Mon, Wed, Fri"),
                                                    "Start": st.column_config.TimeColumn("Start", format="HH:mm", step=300), "End": st.column_config.TimeColumn("End", format="HH:mm", step=300)})
            meeting_rows = medited.to_dict("records")
        chosen_rows = edited.to_dict("records")
        for r in chosen_rows:
            r["Due Date"] = r["Due Date"].date() if isinstance(r.get("Due Date"), (datetime, pd.Timestamp)) else r.get("Due Date")
            r["Add"] = bool(r.get("Add"))
            r["Done"] = bool(r.get("Done"))
        chosen = sum(1 for r in chosen_rows if r["Add"] and (r.get("Title") or "").strip() and r.get("Due Date")) + sum(1 for m in meeting_rows if m.get("Add"))
        if st.button(f"Add {chosen} Selected", key="si_apply", disabled=chosen == 0):
            n, ev, mt, problems = apply_import(cid, chosen_rows, meeting_rows, tz)
            st.session_state["cal_toast"] = (f"Added {n} task{'s' if n != 1 else ''}" + (f", {ev} on the Calendar" if ev else "") + (f" and {mt} class time{'s' if mt != 1 else ''}" if mt else "") + "."
                                             + (f" Not added: {'; '.join(problems[:3])}" if problems else ""))
            st.rerun()


# ---------------------------------------------------------------- the page
def _menu(t, planned):
    """The ⋯ menu of a row: edit, start the timer, log time, remove the planned sessions, delete."""
    running = track_store.running_timer() is not None
    with st.popover("", icon=":material/more_horiz:", help="more"):
        if st.button("Edit", key=f"tl_edit_{t.id}", icon=":material/edit:", width="stretch"):
            planner_ui.task_dialog(t.id)
        if st.button("Start Timer", key=f"tl_start_{t.id}", icon=":material/play_arrow:", disabled=running or t.is_done, width="stretch",
                     help="a timer is already running" if running else "studies this task now"):
            planner_ui._start(t.id)
            st.rerun()
        if st.button("Log Time", key=f"tl_log_{t.id}", icon=":material/more_time:", width="stretch"):
            planner_ui.log_dialog(t.id)
        if st.button("Remove Planned Sessions", key=f"tl_unplan_{t.id}", icon=":material/event_busy:", disabled=not planned, width="stretch",
                     help="removes the sessions of this task that have not started"):
            service.unplan_task(t.id)
            st.rerun()
        if st.button("Delete", key=f"tl_del_{t.id}", icon=":material/delete:", width="stretch"):
            task_store.delete_task(t.id)
            st.rerun()


# the columns of the table: (key, width); the Course column is left out when the list is of one course
COLUMNS = [("done", 0.45), ("name", 3.4), ("course", 1.6), ("category", 1.2), ("due", 1.5), ("time", 1.5), ("cushion", 1.5), ("menu", 0.6)]
HEADER_SORT = {"name": ("Name", "Title"), "course": ("Course", "Course"), "category": ("Category", "Category"), "due": ("Due", "Due Date"), "time": ("Time", "Time Left"),
               "cushion": ("Cushion", "Cushion")}


def _columns(show_course):
    return [c for c in COLUMNS if show_course or c[0] != "course"]


def _row(t, courses, colors, cushions, sessions, tz, now, show_course=True):
    spec = _columns(show_course)
    cols = dict(zip([k for k, _ in spec], st.columns([w for _, w in spec], vertical_alignment="center")))
    done = cols["done"].checkbox("Done", t.is_done, key=f"tl_done_{t.id}_{int(t.is_done)}", label_visibility="collapsed", help="mark it done" if not t.is_done else "open it again")
    if done != t.is_done:
        task_store.set_done(t.id, done)
        st.rerun()
    color = colors.get(f"task:{t.id}") or (crud.course_color(courses[t.course_id]) if t.course_id in courses else "#6b7280")
    title = html.escape(t.title)
    cols["name"].markdown(f'<span style="color:{color};font-size:1.1em">&#9679;</span> ' + (f"<s>{title}</s>" if t.is_done else f"<b>{title}</b>"), unsafe_allow_html=True)
    if "course" in cols:
        cols["course"].markdown(f'<span style="color:{color}">&#9679;</span> {html.escape(course_label(courses, t) or "–")}', unsafe_allow_html=True)
    cols["category"].markdown(t.category)
    cols["due"].markdown(planner_ui._fmt_due(t.due, tz) if t.due else "No due date")
    planned = sum(s.minutes for s in sessions if s.task_id == t.id and s.end > now)
    left = plan_grid.fmt_minutes(t.remaining_minutes) + " left"
    extra = (f"  \n{plan_grid.fmt_minutes(planned)} planned" if planned else "") + (f"  \n{plan_grid.fmt_minutes(t.logged_minutes)} used" if t.logged_minutes else "")
    cols["time"].markdown(left + extra)
    c = cushions.get(t.id)
    if c is not None and not t.is_done:
        cols["cushion"].markdown(f'<span class="cu-pill" style="background:{plan_grid.LEVEL_COLORS[c.level]}" title="the free time left before the deadline, after the work that is due by then">'
                                 f'{planner_ui._cushion_text(c.cushion_minutes)}</span>', unsafe_allow_html=True)
    else:
        cols["cushion"].markdown(f"{t.start_ahead_days} days ahead" if t.start_ahead_days is not None else "")
    with cols["menu"]:
        _menu(t, planned)


def _header(show_course):
    """The heads of the columns are buttons: a click sorts by that column, a second click reverses it. The arrows: up (ascending), down (descending), both (not sorted by it)."""
    spec = _columns(show_course)
    cols = dict(zip([k for k, _ in spec], st.columns([w for _, w in spec], vertical_alignment="center")))
    for key, (label, sort_key) in HEADER_SORT.items():
        if key not in cols:
            continue
        active = st.session_state["tl_sort"] == sort_key
        icon = (":material/arrow_downward:" if st.session_state["tl_desc"] else ":material/arrow_upward:") if active else ":material/swap_vert:"
        if cols[key].button(label, key=f"tl_h_{key}", icon=icon, type="tertiary", help=f"sort by {label.lower()}: tap again to reverse"):
            st.session_state["tl_desc"] = (not st.session_state["tl_desc"]) if active else False
            st.session_state["tl_sort"] = sort_key
            st.rerun()


def render(report, courses, tz):
    now = planner_ui._now()
    tasks = task_store.list_tasks()
    sessions = session_store.list_sessions()
    cushions = {c.task_id: c for c in report.items}
    cushion_minutes = {c.task_id: c.cushion_minutes for c in report.items}
    prefs = settings.get_block_colors()
    for key, value in (("tl_sort", "Due Date"), ("tl_group", "None"), ("tl_desc", False), ("tl_which", "all")):
        st.session_state.setdefault(key, value)

    top = st.columns([1.2, 1.7, 1.7, 2.4, 1.6])
    planner_ui.term_select(top[4])
    if top[1].button("Default Estimates", key="tk_defaults_open", icon=":material/timer:", help="the time a new task of each category gets, for each course"):
        planner_ui.defaults_dialog()
    if top[2].button("Import From Syllabus", key="tk_import_open", icon=":material/upload_file:", help="reads the homework, quizzes and exams of each course of the term, from its course page and its syllabus, and adds them to the list"):
        import_dialog()

    side, main = st.columns([1.2, 6], gap="medium")
    open_tasks = [t for t in tasks if not t.is_done]
    term = settings.get_active_term()
    with side:
        counts = {"all": len(open_tasks), "personal": sum(1 for t in open_tasks if t.personal or t.course_id is None)}
        for cid in courses:
            counts[cid] = sum(1 for t in open_tasks if t.course_id == cid)
        if st.session_state["tl_which"] not in ("all", "personal") and not (st.session_state["tl_which"].startswith("course:") and int(st.session_state["tl_which"].split(":")[1]) in courses):
            st.session_state["tl_which"] = "all"
        st.markdown(planner_ui.filter_panel_html(courses, term["name"] if term else None, counts, st.session_state["tl_which"], settings.get_hidden_blocks(),
                                                 settings.get_block_names(), prefs, settings.get_block_order()), unsafe_allow_html=True)
    which = st.session_state["tl_which"]
    course_id = int(which.split(":")[1]) if which.startswith("course:") else None
    with main:
        # the title is the picked course in its own color (or All Tasks), with the button that adds a task to it
        if course_id:
            c = courses[course_id]
            name = prefs.get(f"course:{course_id}") and settings.get_block_names().get(f"course:{course_id}") or crud.show_code(c["code"]) or c["name"]
            color = prefs.get(f"course:{course_id}") or crud.course_color(c)
        else:
            name, color = ("Personal / No Course" if which == "personal" else "All Tasks"), "var(--text)"
        title_col, add_col, group_col, search_col = st.columns([2.2, 1.5, 1.4, 2], vertical_alignment="bottom")
        title_col.markdown(f'<h2 class="tl-title" style="color:{color}">{html.escape(name)}</h2>', unsafe_allow_html=True)
        if add_col.button("Add New Task", key="tk_add_open", type="primary", icon=":material/add_task:"):
            planner_ui.task_dialog(None, default_course=course_id, default_personal=which == "personal")
        group = group_col.selectbox("Group By", GROUPS, key="tl_group")
        query = search_col.text_input("Search", key="tl_query", placeholder="Search Tasks", icon=":material/search:")
        shown = sort_tasks(filter_tasks(tasks, courses, which, query, False), st.session_state["tl_sort"], st.session_state["tl_desc"], courses, cushion_minutes)
        finished = sort_tasks([t for t in filter_tasks(tasks, courses, which, query, True) if t.is_done], "Due Date", True, courses)
        if not shown and not finished:
            st.caption("No tasks here. Add one with Add New Task, or read them from a course syllabus with Import From Syllabus." if not tasks else "No task matches." if (query or "").strip() else "No task here yet.")
            return
        if shown:
            _header(course_id is None)
            for heading, rows in group_tasks(shown, group, courses, tz, timeutil.local_day(now, tz)):
                if heading:
                    st.markdown(f"**{heading}** · {len(rows)}")
                for t in rows:
                    _row(t, courses, prefs, cushions, sessions, tz, now, show_course=course_id is None)
        else:
            st.caption("Nothing left to do here.")
        if finished:                                                                  # the finished tasks wait in a section at the bottom, newest due date first
            with st.expander(f"Completed ({len(finished)} task{'s' if len(finished) != 1 else ''})"):
                for t in finished:
                    _row(t, courses, prefs, cushions, sessions, tz, now, show_course=course_id is None)
