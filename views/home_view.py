"""Home: cross-course overview."""
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
    chips = "".join(f'<div class="home-stat"><b>{big}</b><span>{small}</span></div>' for big, small in _term_stats(date.today()))
    st.markdown(f'<div class="home-stats">{chips}</div>', unsafe_allow_html=True)
    courses = crud.list_courses(active_only=True)
    if not courses:
        st.info("Add a course under Courses to get started."); return

    # Progress = completed homework / total homework of each course
    homework = {c["id"]: crud.list_homework(c["id"]) for c in courses}

    left, right = st.columns(2)
    with left:
        st.subheader("Progress")
        for c in courses:
            total = len(homework[c["id"]])
            done = sum(x["status"] == "verified" for x in homework[c["id"]])
            st.progress(done / total if total else 0.0,
                        text=f"{c['code']}: {c['name']} · {done}/{total} homework" if total
                        else f"{c['code']}: {c['name']} · no homework yet")
    with right:
        st.subheader("Upcoming Homework")
        rows = [(h, c) for c in courses for h in crud.list_homework(c["id"]) if h["status"] != "verified"]
        for h, c in sorted(rows, key=lambda x: x[0]["due_date"] or "9999")[:6]:
            st.markdown(f"**{h['title']}** · {c['code']} · Due {h['due_date'] or '–'}")
        if not rows:
            st.success("All homework verified.")
