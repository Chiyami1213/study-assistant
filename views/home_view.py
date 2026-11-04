"""Home: cross-course overview."""
import streamlit as st

import crud


def render():
    st.title("Home")
    courses = crud.list_courses(active_only=True)
    if not courses:
        st.info("Add a course under Courses to get started."); return

    stats = {c["id"]: crud.course_stats(c["id"]) for c in courses}
    due = sum(len(crud.due_cards(c["id"])) for c in courses)
    errs = sum(len(crud.list_errata(c["id"], status="open")) for c in courses)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active courses", len(courses))
    m2.metric("Hours studied", f"{sum(s['hours'] for s in stats.values()):.1f}")
    m3.metric("Flashcards due", due)
    m4.metric("Open errata", errs)

    left, right = st.columns(2)
    with left:
        st.subheader("Progress")
        for c in courses:
            st.progress(stats[c["id"]]["pct"], text=f"{c['code']}: {c['name']}")
    with right:
        st.subheader("Upcoming homework")
        rows = [(h, c) for c in courses for h in crud.list_homework(c["id"]) if h["status"] != "verified"]
        for h, c in sorted(rows, key=lambda x: x[0]["due_date"] or "9999")[:6]:
            st.markdown(f"**{h['title']}** · {c['code']} · due {h['due_date'] or '–'}")
        if not rows:
            st.success("All homework verified.")
