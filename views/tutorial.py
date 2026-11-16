"""The getting-started tutorial for a new student: a checklist at the top of Home that walks through the first things to do (a course, the term, class times, files, a study guide made with an AI
assistant, tasks, the schedule). Each step has a button that goes to the right place and opens the right window, and ticks itself off when the student has done it. It is shown on the first start
(only when the app has no course yet), it can be skipped at any time, and Settings > Help brings it back."""
import streamlit as st

from core import crud, settings

# (key, title, what it is for, button label, the place it goes to)
STEPS = [
    ("courses", "Add Your Courses", "Courses hold your files, homework, exams and notes. Add the ones you take this term.", "Add a Course"),
    ("term", "Set Up Your Term", "Enter the first and last day of classes, your wake-up time and your breaks. The planner counts your free time from them.", "Set Up the Term"),
    ("meetings", "Add Your Class Times", "Tell the Calendar when each class meets (Edit Schedule), so study sessions are planned around your classes.", "Add Class Times"),
    ("files", "Add Your Files", "Put slides, textbooks, homework and exams in the Library: one file, a zip or a whole folder. Your own files are only copied, never changed.", "Add a File"),
    ("guides", "Make Study Guides With AI", "Library > Import > Prompt for AI writes the prompt for Claude, ChatGPT or Gemini. Paste it in a chat with your slides, download the HTML guide it makes and import it here.", "Make a Prompt"),
    ("tasks", "Add Your Tasks", "Task List > Import From Syllabus reads the homework and exams of your courses, and Import From Calendar brings in Canvas, Brightspace or Google Calendar. Or add a task yourself.", "Open the Task List"),
    ("schedule", "Build Your Study Schedule", "Auto-Plan fills your free time with study sessions, earliest deadline first, and the cushion shows whether your work fits before each deadline.", "Open the Calendar"),
]


def facts():
    """What the student has done so far, counted from their own data."""
    from planner import session_store, task_store
    books = crud.list_books()
    return {"courses": len(crud.list_courses(section=None)), "terms": len(settings.list_terms()) + (1 if settings.semester_set() and not settings.list_terms() else 0),
            "meetings": len(crud.list_meetings()), "books": len(books),
            "guides": sum(1 for b in books if b["kind"] in ("Notes", "Lecture Notes") and str(b["pdf_path"]).lower().endswith((".html", ".htm"))),
            "tasks": len(task_store.list_tasks()), "sessions": len(session_store.list_sessions())}


def done_flags(f):
    """{step key: done} from the counts of `facts`."""
    return {"courses": f["courses"] > 0, "term": f["terms"] > 0, "meetings": f["meetings"] > 0, "files": f["books"] > 0, "guides": f["guides"] > 0, "tasks": f["tasks"] > 0, "schedule": f["sessions"] > 0}


def ensure_state():
    """The first time: a student with no course is new (the tutorial starts); one who already has data is not (it stays off). Returns the state."""
    state = settings.get_tutorial()
    if state is None:
        settings.set_tutorial(mode="active" if not crud.list_courses(section=None) else "dismissed", welcomed=False)
        state = settings.get_tutorial()
    return state


def _go(key):
    """Go to the place of a step and open its window there."""
    ss = st.session_state
    if key == "courses":
        ss["page"], ss["open_course"], ss["_tut_add_course"] = "Courses", None, True
    elif key == "term":
        ss["page"], ss["cal_page"] = "Calendar", "Calendar"
        ss["_open_new_term"] = True
    elif key == "meetings":
        ss["page"], ss["cal_page"], ss["_tut_schedule"] = "Calendar", "Calendar", True
    elif key == "files":
        ss["page"], ss["open_book"], ss["_tut_add_file"] = "Library", None, True
    elif key == "guides":
        ss["page"], ss["open_book"], ss["_tut_prompt"] = "Library", None, True
    elif key == "tasks":
        ss["page"], ss["cal_page"] = "Calendar", "Task List"
    elif key == "schedule":
        ss["page"], ss["cal_page"] = "Calendar", "Calendar"
    st.rerun()


@st.dialog("Welcome to Study Assistant")
def _welcome():
    st.markdown("Study Assistant keeps your courses, files, notes, homework and study schedule in one place. A short checklist on this page shows the first steps: it takes a few minutes, "
                "and it ticks each step off when you have done it.")
    st.caption("You can skip it now and bring it back later in Settings > Help.")
    a, b = st.columns(2)
    if a.button("Start the Tutorial", key="tut_start", type="primary", width="stretch"):
        st.rerun()
    if b.button("Skip the Tutorial", key="tut_skip_welcome", width="stretch"):
        settings.set_tutorial(mode="dismissed")
        st.rerun()


def render_card():
    """The checklist at the top of Home. When it was skipped or finished, only a small button is left that brings it back (Settings > Help has one too)."""
    state = ensure_state()
    if state.get("mode") != "active":
        if st.button("Show the Tutorial", key="tut_reopen", icon=":material/school:", type="tertiary", help="the getting-started checklist"):
            settings.set_tutorial(mode="active", welcomed=True)
            st.rerun()
        return
    if not state.get("welcomed"):
        settings.set_tutorial(welcomed=True)
        _welcome()
    flags = done_flags(facts())
    done = sum(flags.values())
    with st.container(border=True, key="tutorial_card"):
        head, skip = st.columns([5, 1.6], vertical_alignment="center")
        head.subheader("Getting Started")
        if skip.button("Skip Tutorial", key="tut_skip", icon=":material/close:", help="hide this checklist; it can be shown again in settings > help"):
            settings.set_tutorial(mode="dismissed")
            st.toast("Tutorial skipped. You can open it again in Settings > Help.")
            st.rerun()
        st.progress(done / len(STEPS), text=f"{done} of {len(STEPS)} steps done")
        first_open = next((k for k, *_ in STEPS if not flags[k]), None)
        for number, (key, title, why, button) in enumerate(STEPS, 1):
            mark, text, go = st.columns([0.5, 6.5, 2], vertical_alignment="center")
            mark.markdown(f"<div class='tut-mark{' tut-done' if flags[key] else ''}'>{'✓' if flags[key] else number}</div>", unsafe_allow_html=True)
            text.markdown(f"**{title}**" + ("  \n" if not flags[key] else " · done  \n") + f"<span class='tut-why'>{why}</span>", unsafe_allow_html=True)
            if go.button(button if not flags[key] else "Open Again", key=f"tut_go_{key}", type="primary" if key == first_open else "secondary", width="stretch"):
                _go(key)
        if done == len(STEPS):
            st.success("Everything is set up. Open the Note Reader to read your guides next to their slides, and use Home to see what is due.", icon=":material/check_circle:")
            if st.button("Close Tutorial", key="tut_close", type="primary"):
                settings.set_tutorial(mode="dismissed")
                st.rerun()
