"""File: notes exported from the Note Builder, in one section per active course."""
import html

import streamlit as st
import streamlit.components.v1 as components

import crud
import htmlnotes
import notesfs
import quizhtml
from views import quiz_view


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


def _files_signature():
    """Changes whenever a note, a quiz file or the database is saved, so cached quiz lists are rebuilt only then."""
    import os
    from database import BASE_DIR
    stamp = []
    for folder in ("notes", "quizzes"):
        for root, _dirs, names in os.walk(BASE_DIR / folder):
            stamp += [os.stat(os.path.join(root, n)).st_mtime_ns for n in names]
    for path in (BASE_DIR / "data").glob("*.db"):
        stamp.append(path.stat().st_mtime_ns)
    return hash(tuple(stamp))


@st.cache_data(show_spinner=False, max_entries=16)
def _chapters_cached(course_id, signature):
    return quiz_view.course_chapters(crud.get_course(course_id))


def _quiz_exports(course):
    """Each chapter's quiz as a standalone HTML page (HTML only), ready to open in any browser."""
    chapters = _chapters_cached(course["id"], _files_signature())
    if not chapters:
        return
    with st.expander(f"Quizzes ({len(chapters)}) · export as HTML"):
        for c in chapters:
            name, btn = st.columns([6, 1.6], vertical_alignment="center")
            name.markdown(f"{c['name']} · {len(c['questions'])} questions")
            safe = "".join(ch for ch in c["name"] if ch.isalnum() or ch in " ._-") or "quiz"
            btn.download_button("Download", quizhtml.build(c["name"], c["questions"]), file_name=f"{safe} - Quiz.html",
                                mime="text/html", key=f"quizdl_{course['id']}_{c['book']['id']}", width="stretch")


def render():
    st.title("File")
    courses = crud.courses_by_status("Active") + [c for s in crud.STATUSES if s != "Active" for c in crud.courses_by_status(s)
                                                  if crud.list_exported_notes(c["id"])]      # others show once they have exports
    if not courses:
        st.info("Courses appear here with the notes you export from the Note Builder."); return
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
        _quiz_exports(c)
