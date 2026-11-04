"""Library: reference textbooks / PDFs across all courses."""
import streamlit as st

import crud
from views.notes_view import pdf_viewer


def render():
    st.title("Library")
    courses = {c["id"]: c for c in crud.list_courses()}
    refs = [(r, courses[cid]) for cid in courses for r in crud.list_references(cid)]

    with st.expander("➕ Add reference"):
        with st.form("add_ref", clear_on_submit=True):
            cid = st.selectbox("Course", list(courses), format_func=lambda i: courses[i]["code"])
            title = st.text_input("Title")
            pages = st.number_input("Total pages", 0, 5000, 0)
            if st.form_submit_button("Add") and title:
                crud.add_reference(cid, title, None, pages or None)
                st.rerun()

    if not refs:
        st.info("No references yet."); return
    labels = {r["id"]: f"{r['title']} ({c['code']})" for r, c in refs}
    rid = st.selectbox("Reference", list(labels), format_func=labels.get)
    pdf_viewer(next(r for r, _ in refs if r["id"] == rid))
