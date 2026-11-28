"""Home: cross-course overview."""
import html
import re
from datetime import date, timedelta

import streamlit as st

from core import crud
from core import settings
from library import homedata
from library.homedata import (_plural, _term_stats, _tasks, _when, _countdown, _complete, _undo, EXAM_RE, SHOWN, TASK_KINDS)      # the pure part of Home: shared with the native interface






def render():
    from views import tutorial
    head, tutorial_col = st.columns([5, 2], vertical_alignment="center")
    head.title("Home")
    with tutorial_col:
        tutorial.header_button()                        # right-aligned in the row of the title, once the tutorial was skipped or finished
    tutorial.render_card()                              # the getting-started checklist of a new student (it can be skipped)
    if settings.semester_set():                       # the week and the days to winter break, from the term dates saved in the Calendar
        chips = "".join(f'<div class="home-stat"><b>{big}</b><span>{small}</span></div>' for big, small in _term_stats(date.today()))
        st.markdown(f'<div class="home-stats">{chips}</div>', unsafe_allow_html=True)
    courses = crud.list_courses(active_only=True)
    exams = homedata.exam_countdowns(courses) if courses else []
    if exams:                                           # a tile for each exam that is near (Settings > Home: how near), in the course's color
        st.subheader("Exam Countdown")
        tiles = "".join(f'<div class="home-stat" style="background: {html.escape(f["color"])}; border-color: transparent; color: #fff;"><b>{html.escape(f["big"])}</b><span>{html.escape(f["small"])}</span><span>{html.escape(f["when"])}</span></div>' for f in exams)
        st.markdown(f'<div class="home-stats" style="flex-wrap: wrap;">{tiles}</div>', unsafe_allow_html=True)
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
        st.subheader("Upcoming Work")
        _upcoming(courses, homework)










def _upcoming(courses, homework):
    """Unfinished homework (overdue ones first) and coming midterms/finals of the active courses, soonest first."""
    today = date.today()
    by_id = {c["id"]: c for c in courses}
    items = homedata.upcoming_items(courses, homework, today)
    if not items:
        st.success("Nothing due. Enjoy the free time.")
    else:
        with st.container(key="up_list", border=True):
            for day, time, title, kind, c, covers, item_id in items[:SHOWN]:
                label, css = _countdown(day, today)
                tag = (f'<span class="book-badge tag" style="background:{crud.course_color(c)};'
                       f'border-color:{crud.course_color(c)}">{html.escape(crud.show_code(c["code"]))}</span>')
                kind_badge = f'<span class="book-badge">{kind}</span>' if kind != "Homework" else ""
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






def _completed(courses, homework, today):
    """Recently completed items (due in the last week or still to come), each with a button that puts it back in the list."""
    rows = homedata.completed_items(courses, homework, today)
    if not rows:
        return
    with st.expander(f"Completed ({len(rows)})"):
        for day, title, kind, c, item_id in sorted(rows):
            a, b = st.columns([8, 2], vertical_alignment="center")
            a.markdown(f"**{html.escape(title)}** · {html.escape(c['code'])} · {html.escape(_when(day, ''))}")
            b.button("Undo", key=f"up_undo_{kind}_{item_id}", on_click=_undo, args=(kind, item_id), help=f"put this {kind.lower()} back in the list")
