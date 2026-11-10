"""Home: cross-course overview."""
import html
import re
from datetime import date, timedelta

import streamlit as st

import crud
import settings


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _term_stats(today):
    """[(big text, small text)] for the term: current week number (holidays count) and days until winter break.

    Winter break starts the day after the last day of finals (the end of the exam period)."""
    sem = settings.get_semester()
    start, exam_end = date.fromisoformat(sem["start"]), date.fromisoformat(sem["exam_end"])
    break_start = exam_end + timedelta(days=1)
    day = lambda d: f"{d.strftime('%a, %b')} {d.day}"
    if today < start:
        return [(_plural((start - today).days, "Day"), f"Until Classes Start · {day(start)}")]
    if today >= break_start:
        return [("Winter Break", f"Started {day(break_start)}")]
    week = (today - start).days // 7 + 1           # week 1 is the week classes start; holiday weeks are counted
    total = (exam_end - start).days // 7 + 1
    return [(f"Week {week}", f"Of {total}"),
            (_plural((break_start - today).days, "Day"), f"Until Winter Break · {day(break_start)}")]


def render():
    st.title("Home")
    if settings.semester_set():                       # the week and the days to winter break, from the term dates saved in the Calendar
        chips = "".join(f'<div class="home-stat"><b>{big}</b><span>{small}</span></div>' for big, small in _term_stats(date.today()))
        st.markdown(f'<div class="home-stats">{chips}</div>', unsafe_allow_html=True)
    courses = crud.list_courses(active_only=True)
    if not courses:
        st.info("Add a course under Courses to get started. Set the term dates in the Calendar (Edit Schedule) to see the week and the days left in the term."); return

    # Progress = completed homework / total homework of each course
    homework = {c["id"]: crud.list_homework(c["id"]) for c in courses}

    left, right = st.columns([4, 5])
    with left:
        st.subheader("Progress")
        for c in courses:
            total = len(homework[c["id"]])
            done = sum(x["status"] == "verified" for x in homework[c["id"]])
            st.progress(done / total if total else 0.0,
                        text=f"{c['code']}: {c['name']} · {done}/{total} homework" if total
                        else f"{c['code']}: {c['name']} · no homework yet")
    with right:
        st.subheader("Upcoming Homework and Exams")
        _upcoming(courses, homework)


EXAM_RE = re.compile(r"midterm|final|exam", re.I)
SHOWN = 8


def _when(day, time):
    d = date.fromisoformat(day)
    return f"{d.strftime('%a, %b')} {d.day}" + (f" · {time}" if time else "")


def _countdown(day, today):
    n = (date.fromisoformat(day) - today).days
    if n < 0:
        return "Overdue", "late"
    if n == 0:
        return "Today", "late"
    if n == 1:
        return "Tomorrow", "open"
    return f"In {n} Days", "open"


def _upcoming(courses, homework):
    """Unfinished homework (overdue ones first) and coming midterms/finals of the active courses, soonest first."""
    today = date.today()
    by_id = {c["id"]: c for c in courses}
    items = [(h["due_date"], h.get("due_time") or "", h["title"], "Homework", by_id[cid], None, h["id"])
             for cid, rows in homework.items() for h in rows if h["status"] != "verified" and h["due_date"]]
    items += [(e["date"], e.get("time") or "", e["title"], "Exam", by_id[e["course_id"]], e.get("covers"), e["id"])
              for e in crud.list_events(today.isoformat(), "2100-12-31")
              if e["course_id"] in by_id and EXAM_RE.search(e["title"]) and not e.get("done")]
    items.sort(key=lambda x: (x[0], x[1]))
    if not items:
        st.success("Nothing due. Enjoy the free time.")
    else:
        with st.container(key="up_list", border=True):
            for day, time, title, kind, c, covers, item_id in items[:SHOWN]:
                label, css = _countdown(day, today)
                tag = (f'<span class="book-badge tag" style="background:{crud.course_color(c)};'
                       f'border-color:{crud.course_color(c)}">{html.escape(c["code"])}</span>')
                kind_badge = '<span class="book-badge">Exam</span>' if kind == "Exam" else ""
                info, pill, check = st.columns([8, 2.2, 0.9], vertical_alignment="center")
                info.markdown(f'<div><div class="dl-title">{html.escape(title)}</div>'
                              f'<div class="up-meta">{tag}{kind_badge}<span class="dl-when">{html.escape(_when(day, time))}</span></div>'
                              f'{"<div class=dl-sub>Covers " + html.escape(covers) + "</div>" if covers else ""}</div>', unsafe_allow_html=True)
                pill.markdown(f'<span class="dl-pill {css}">{label}</span>', unsafe_allow_html=True)
                check.button("", icon=":material/check:", key=f"up_done_{kind}_{item_id}", type="tertiary",
                             help=f"mark this {kind.lower()} as complete", on_click=_complete, args=(kind, item_id))
        if len(items) > SHOWN:
            st.caption(f"{len(items) - SHOWN} more in the Calendar and on each course page.")
    _completed(courses, homework, today)


def _complete(kind, item_id):
    if kind == "Homework":
        crud.set_homework_status(item_id, "verified")
    else:
        crud.set_event_done(item_id, True)


def _undo(kind, item_id):
    if kind == "Homework":
        crud.set_homework_status(item_id, "todo")
    else:
        crud.set_event_done(item_id, False)


def _completed(courses, homework, today):
    """Recently completed items (due in the last week or still to come), each with a button that puts it back in the list."""
    since = (today - timedelta(days=7)).isoformat()
    by_id = {c["id"]: c for c in courses}
    rows = [(h["due_date"], h["title"], "Homework", by_id[cid], h["id"]) for cid, hs in homework.items() for h in hs
            if h["status"] == "verified" and h["due_date"] and h["due_date"] >= since]
    rows += [(e["date"], e["title"], "Exam", by_id[e["course_id"]], e["id"]) for e in crud.list_events(since, "2100-12-31")
             if e["course_id"] in by_id and EXAM_RE.search(e["title"]) and e.get("done")]
    if not rows:
        return
    with st.expander(f"Completed ({len(rows)})"):
        for day, title, kind, c, item_id in sorted(rows):
            a, b = st.columns([8, 2], vertical_alignment="center")
            a.markdown(f"**{html.escape(title)}** · {html.escape(c['code'])} · {html.escape(_when(day, ''))}")
            b.button("Undo", key=f"up_undo_{kind}_{item_id}", on_click=_undo, args=(kind, item_id), help=f"put this {kind.lower()} back in the list")
