"""File: notes exported from the Note Builder, in one section per active course."""
import html

import streamlit as st
import streamlit.components.v1 as components

import crud
import htmlnotes
import notesfs


def _note_card(item):
    with st.expander(f"{item['title']} · {item['exported_at'][:10]}"):
        text = item["notes"]
        if not text.strip():
            st.caption("Nothing here yet.")
        elif notesfs.is_html(text):               # an interactive page, with its animations and its exercises
            components.html(htmlnotes.safe_html(text), height=680, scrolling=True)
        else:
            st.markdown(text)
        if text.strip():
            html_page = notesfs.is_html(text)
            st.download_button("Download", text, file_name=f"{item['title'] or 'note'}.{'html' if html_page else 'md'}",
                               mime="text/html" if html_page else "text/markdown", key=f"file_dl_{item['id']}")
        if st.button("Remove", key=f"file_rm_{item['id']}"):
            crud.delete_exported_note(item["id"])
            st.rerun()


def render():
    st.title("File")
    courses = crud.courses_by_status("Active")
    if not courses:
        st.info("Active courses appear here with the notes you export from the Note Builder."); return
    for c in courses:
        items = crud.list_exported_notes(c["id"])
        color = crud.course_color(c)
        st.markdown(f'<h3 class="file-head"><span class="file-dot" style="background:{color}"></span>'
                    f'{html.escape(crud.label(c))} <span class="file-count">({len(items)})</span></h3>',
                    unsafe_allow_html=True)
        if not items:
            st.caption("No exported notes yet.")
        for item in items:
            _note_card(item)
