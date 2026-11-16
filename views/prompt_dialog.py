"""Prompt for AI: the student picks a course, the kind of page and the AI assistant (Claude, ChatGPT or Gemini), and gets a prompt to paste into their own chat. The pages Claude writes are imported in the Library and
the app recognizes them (see study/promptgen.py and study/prompts/)."""
import streamlit as st

from core import crud
from study import promptgen as P


def _course_notes(course_id):
    """[{lecture, title}] of the notes the Library has for the course, by lecture number."""
    rows = [b for b in crud.list_books() if course_id in b["course_ids"] and b["kind"] in ("Notes", "Lecture Notes")]
    def key(b):
        lec = (b.get("lecture") or "").strip()
        digits = "".join(ch for ch in lec.split("-")[0] if ch.isdigit())
        return (int(digits) if digits else 10 ** 6, b["title"].lower())
    return [{"lecture": (b.get("lecture") or "").strip(), "title": b["title"]} for b in sorted(rows, key=key)]


@st.dialog("Prompt for AI", width="large")
def prompt_dialog(default_course=None):
    """Make the prompt for one page (a study guide, a homework helper, a grade explanation, an exam reflection or preparation page)."""
    courses = {c["id"]: c for c in crud.list_courses(section=None)}
    if not courses:
        st.info("Add a course first: the prompt carries the course number in the page names.")
        return
    st.caption("Paste the prompt into a chat with your AI assistant together with your course files. The assistant writes the page in the format this app reads; download the file it makes and import it with Library > Import.")
    assistant = st.segmented_control("AI Assistant", list(P.ASSISTANTS), default=st.session_state.get("pg_ai_kept", "Claude"), key="pg_ai", help="the assistant you will paste the prompt into; only the way the page is handed over differs") or "Claude"
    st.session_state["pg_ai_kept"] = assistant
    ids = list(courses)
    left, right = st.columns([3, 2], vertical_alignment="bottom")
    cid = left.selectbox("Course", ids, index=ids.index(default_course) if default_course in ids else 0, format_func=lambda i: crud.label(courses[i]), key="pg_course")
    kind = right.selectbox("Page", list(P.KINDS), format_func=lambda k: P.KINDS[k][0], key="pg_kind")
    number_kind = P.KINDS[kind][1]
    if number_kind == "exam":
        number = st.segmented_control("Exam", P.EXAMS, default=P.EXAMS[0], key="pg_exam") or P.EXAMS[0]
    else:
        number = st.text_input(P.NUMBER_LABEL[number_kind], "1", key=f"pg_num_{number_kind}", placeholder="3 or 3-4" if number_kind == "chapter" else "4")
    course = courses[cid]
    notes = _course_notes(cid)
    textbooks = [b["title"] for b in crud.list_books() if cid in b["course_ids"] and b["kind"] == "Textbook"]
    a, b = st.columns(2)
    rules = a.toggle("Include the style rules", True, key="pg_rules", help="the rules for equations, units, layout and the quiz; switch off when Claude already has them in this chat")
    use_notes = b.toggle("List my notes", bool(notes), key="pg_notes", disabled=not notes, help="the notes of this course that are in the Library, so Claude can link to their sections")
    text = P.build_prompt(kind, course, number, notes=notes if use_notes else [], textbooks=textbooks, include_rules=rules, assistant=assistant)
    name = P.file_name(kind, course, number)
    st.markdown(f"**File name the page must have:** `{name}.html`")
    st.markdown(f"**{P.ASSISTANTS[assistant]['attach'].capitalize()} to the {assistant} chat:** " + "; ".join(P.ATTACH[kind]) + ".")
    st.code(text, language="markdown", height=340, wrap_lines=True)
    st.download_button("Download the Prompt", text, file_name=f"{name} Prompt ({assistant}).md", mime="text/markdown", icon=":material/download:", key="pg_download", help="the same text as a .md file")
    st.caption(f"{len(text):,} characters. Use the copy button at the top right of the box above, or the download.")
