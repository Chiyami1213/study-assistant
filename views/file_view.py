"""File: notes exported from the Note Builder, in one section per active course."""
import html

import streamlit as st

import crud


def _note_card(item):
    with st.expander(f"{item['title']} · {item['exported_at'][:10]}"):
        tabs = st.tabs(["Notes", "Exercises"])
        for tab, field in zip(tabs, ("notes", "exercises")):
            with tab:
                if item[field].strip():
                    st.markdown(item[field])
                else:
                    st.caption("Nothing here yet.")
        text = f"# {item['title']}\n\n## Notes\n\n{item['notes']}\n\n## Exercises\n\n{item['exercises']}\n"
        a, b, _ = st.columns([1.3, 1, 6])
        a.download_button("Download", text, file_name=f"{item['title'] or 'note'}.md", mime="text/markdown",
                          key=f"file_dl_{item['id']}")
        if b.button("Remove", key=f"file_rm_{item['id']}"):
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
