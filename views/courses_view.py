"""Course hub & syllabus tracking."""
import streamlit as st

import crud
from views import exam_mode_view, homework_view, notes_view, recall_view


def render():
    st.title("Courses")
    courses = crud.list_courses()

    cols = st.columns(2)
    for i, c in enumerate(courses):
        s = crud.course_stats(c["id"])
        with cols[i % 2]:
            with st.container(border=True):
                st.subheader(crud.label(c))
                st.caption(f"{c['semester']} · {'Active' if c['is_active'] else 'Archived'}")
                st.progress(s["pct"], text=f"Syllabus {s['done']}/{s['topics']} topics")
                tgt = c["target_hours"] or 0
                st.progress(min(s["hours"] / tgt, 1.0) if tgt else 0.0,
                            text=f"Study hours {s['hours']:.1f} / {tgt:.0f}")
                if st.button("Open", key=f"open_{c['id']}"):
                    st.session_state["course_id"] = c["id"]
                    st.rerun()

    st.divider()
    cid = st.session_state.get("course_id")
    if cid and crud.get_course(cid):
        _manage(crud.get_course(cid))

    with st.expander("➕ Add course"):
        with st.form("add_course", clear_on_submit=True):
            a, b = st.columns(2)
            code = a.text_input("Code", placeholder="PHYS102")
            name = b.text_input("Name")
            sem = a.text_input("Semester", value="Fall 2026")
            hrs = b.number_input("Target study hours", 0.0, 1000.0, 60.0)
            if st.form_submit_button("Create") and code and name:
                crud.add_course(code, name, sem, hrs)
                st.rerun()


def _manage(course):
    cid = course["id"]
    st.header(crud.label(course))
    t_syl, t_notes, t_hw, t_exam, t_rec = st.tabs(["Syllabus", "Notes", "Homework", "Exam Hub", "Recall"])
    with t_notes:
        notes_view.render()
    with t_hw:
        homework_view.render()
    with t_exam:
        exam_mode_view.render()
    with t_rec:
        recall_view.render()
    with t_syl:
        _syllabus(course)


def _syllabus(course):
    cid = course["id"]
    left, right = st.columns([3, 2])

    with left:
        for t in crud.list_topics(cid):
            done = st.checkbox(f"Week {t['week'] or '–'}: {t['title']}", value=bool(t["completed"]),
                               key=f"topic_{t['id']}")
            if done != bool(t["completed"]):
                crud.set_topic_done(t["id"], done)
                st.rerun()
        with st.form(f"add_topic_{cid}", clear_on_submit=True):
            a, b = st.columns([1, 4])
            week = a.number_input("Week", 1, 52, 1)
            title = b.text_input("New topic")
            if st.form_submit_button("Add topic") and title:
                crud.add_topic(cid, week, title)
                st.rerun()

    with right:
        st.subheader("Log study time")
        with st.form(f"log_{cid}", clear_on_submit=True):
            h = st.number_input("Hours", 0.25, 12.0, 1.0, 0.25)
            note = st.text_input("What did you study?")
            if st.form_submit_button("Log"):
                crud.log_hours(cid, h, note)
                st.rerun()
        for l in crud.recent_logs(cid):
            st.caption(f"{l['logged_on']} · {l['hours']}h · {l['note'] or ''}")

        active = st.toggle("Active this semester", value=bool(course["is_active"]), key=f"act_{cid}")
        if active != bool(course["is_active"]):
            crud.set_course_active(cid, active)
            st.rerun()
