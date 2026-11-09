"""Homework & solution pairing viewer."""
import streamlit as st

import crud
from database import BASE_DIR, PDF_DIR, data_path, stored_path

ICON = {"todo": "⚪", "attempted": "🟡", "verified": "🟢"}


def _show(md, file_path):
    if md:
        st.markdown(md)
    if file_path:
        p = data_path(file_path)
        if p.exists():
            st.download_button("Download file", p.read_bytes(), file_name=p.name, key=f"dl_{file_path}")


def render():
    cid = st.session_state.get("course_id")
    if not cid:
        st.warning("Select or create a course first."); return
    course = crud.get_course(cid)

    hws = crud.list_homework(cid)
    if hws:
        labels = {h["id"]: f"{ICON[h['status']]} {h['title']} (Due {h['due_date'] or '–'})" for h in hws}
        hid = st.selectbox("Assignment", list(labels), format_func=labels.get)
        hw = next(h for h in hws if h["id"] == hid)

        reveal = st.toggle("Show Solution", value=st.session_state["mode"] == "Exam" and hw["status"] != "todo")
        left, right = st.columns(2) if reveal else (st.container(), None)
        with left:
            st.markdown("### Problems")
            _show(hw["problem_md"], hw["problem_file"])
        if right is not None:
            with right:
                st.markdown("### Solutions")
                _show(hw["solution_md"], hw["solution_file"])

        st.divider()
        a, b = st.columns([2, 1])
        status = a.radio("Status", list(ICON), index=list(ICON).index(hw["status"]), horizontal=True,
                         format_func=lambda s: {"todo": "To Do"}.get(s, s.title()))
        if status != hw["status"]:
            crud.set_homework_status(hid, status); st.rerun()
        if b.button("Delete Assignment"):
            crud.delete_homework(hid); st.rerun()
    else:
        st.info("No homework yet.")

    with st.expander("Add Homework / Solution Pair"):
        with st.form("add_hw", clear_on_submit=True):
            title = st.text_input("Title")
            due = st.date_input("Due Date")
            prob = st.text_area("Problems (Markdown + LaTeX)")
            sol = st.text_area("Solutions (Markdown + LaTeX)")
            pf, sf = st.file_uploader("Problem File (Optional)"), st.file_uploader("Solution File (Optional)")
            if st.form_submit_button("Save") and title:
                def store(f, tag):
                    if not f:
                        return None
                    dest = PDF_DIR / f"hw_{cid}_{tag}_{f.name}"
                    dest.write_bytes(f.getvalue())
                    return stored_path(dest)
                crud.add_homework(cid, title, due.isoformat(), prob, sol, store(pf, "p"), store(sf, "s"))
                st.rerun()
