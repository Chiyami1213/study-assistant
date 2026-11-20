"""The getting-started tutorial for a new student.

Two parts that belong together:
  * the CHECKLIST at the top of Home (a chain of seven steps with a tick for each one the student has done, counted from their own data), and
  * the GUIDED TOUR: it takes the student to the page, opens the window, dims everything but the thing to click or fill, points at it with a box and an arrow, and explains it in a helper card in
    a corner (views/tour_overlay.js draws it). Back, Next and Skip are in the card; the tour moves on by itself when the student has done what a step asks (a course saved ...).
It starts on the first launch (only when the app has no course yet), it can be skipped at any time, and it can be started again from Home or from Settings > Help."""
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from core import crud, settings

OVERLAY = Path(__file__).resolve().parent / "tour_overlay.js"

# (key, title, what it is for, button label, short name for the chain)
STEPS = [
    ("courses", "Add Your Courses", "Courses hold your files, homework, exams and notes. Add the ones you take this term.", "Add a Course", "Courses"),
    ("term", "Set Up Your Term", "Enter the first and last day of classes, your wake-up time and your breaks. The planner counts your free time from them.", "Set Up the Term", "Term"),
    ("meetings", "Add Your Class Times", "Tell the Calendar when each class meets (Edit Schedule), so study sessions are planned around your classes.", "Add Class Times", "Class Times"),
    ("files", "Add Your Files", "Put slides, textbooks, homework and exams in the Library: one file, a zip or a whole folder. Your own files are only copied, never changed.", "Add Files", "Files"),
    ("guides", "Make Study Guides With AI", "Library > Import > Prompt for AI writes the prompt for Claude, ChatGPT or Gemini. Paste it in a chat with your slides, download the HTML guide it makes and import it here.", "Make a Prompt", "AI Guides"),
    ("tasks", "Add Your Tasks", "Task List > Import From Syllabus reads the homework and exams of your courses, and Import From Calendar brings in Canvas, Brightspace, Google Calendar or Shovel. Or add a task yourself.", "Open the Task List", "Tasks"),
    ("schedule", "Build Your Study Schedule", "Auto-Plan fills your free time with study sessions, earliest deadline first, and the cushion shows whether your work fits before each deadline.", "Open the Calendar", "Schedule"),
]

# The guided tour: one entry for each thing it points at. `main`: the step of the chain it belongs to; `page` (and `cal_page`): where to be; `open`: the window to have open (courses_view,
# planner_ui, calendar_view and library_view ask `wants(name)`); `target`: what to point at (css:..., label:<text of a field>, button:<text>); `advance`: a count of `facts` that moves the tour on
# by itself when it grows.
TOUR = [
    dict(main=None, page="Home", target="", title="Welcome to Study Assistant", text="This short tour shows you where to click for the first things to do: add a course, set up your term, add your files, make study guides with AI and plan your study time. Use Next to go on, or Skip Tutorial at any time."),
    dict(main="courses", page="Courses", target="css:.st-key-add_course_open button", title="Add a Course", text="Courses hold your files, homework, exams and notes. Click Add Course here (or press Next and it opens for you)."),
    dict(main="courses", page="Courses", open="add_course", target="label:Name", title="The Name", text="Type the name of the course, for example Linear Algebra."),
    dict(main="courses", page="Courses", open="add_course", target="label:Course Number", title="The Course Number", text="Type its number, for example MATH 101. A self-study course does not need one."),
    dict(main="courses", page="Courses", open="add_course", target="button:Add Course", advance="courses", title="Save the Course", text="Click Add Course. The tour goes on by itself when the course is saved (or press Next to skip this)."),
    dict(main="term", page="Calendar", cal_page="Calendar", target="css:.st-key-cal_term", title="Your Terms", text="This list switches the term the Calendar shows; its last entry, Manage Terms, adds and changes terms. Press Next and the window to add a term opens."),
    dict(main="term", page="Calendar", cal_page="Calendar", open="new_term", target="label:Classes Start", title="The Dates", text="Enter the first day of classes, the last day of classes and the end of the exam period."),
    dict(main="term", page="Calendar", cal_page="Calendar", open="new_term", target="label:Wake-Up Time", title="Wake-Up Time and Bedtime", text="Study sessions are planned only between these two times, on every day of the term."),
    dict(main="term", page="Calendar", cal_page="Calendar", open="new_term", target="button:Add Term", advance="terms", title="Save the Term", text="Click Add Term. The tour goes on by itself when it is saved."),
    dict(main="meetings", page="Calendar", cal_page="Calendar", target="css:.st-key-edit_schedule_open button", title="Edit Schedule", text="This is where the weekly class times are added. Press Next and the window opens."),
    dict(main="meetings", page="Calendar", cal_page="Calendar", open="schedule", target="label:Course", title="Choose the Course", text="Choose the course this class time is for. (You need an active course first.)"),
    dict(main="meetings", page="Calendar", cal_page="Calendar", open="schedule", target="label:Days", title="Days and Times", text="Pick the days the class meets, then its start and end time and, if you like, the room."),
    dict(main="meetings", page="Calendar", cal_page="Calendar", open="schedule", target="button:Add Class Time", advance="meetings", title="Save the Class Time", text="Click Add Class Time. The Calendar will plan your study around it."),
    dict(main="files", page="Library", target="css:.st-key-lib_import_box button", title="The Import Menu", text="Everything you bring into the Library goes through Import: Add Files (one file, many, or a zip), or Update From Folder (it reads a folder of your files; a file the Library has already is replaced or kept, as you choose), or Remove Files for many at once. Your originals are never changed."),
    dict(main="files", page="Library", open="add_file", target="label:Files", title="Add Files", text="Choose a PDF or an HTML page (or several, or a zip): slides, a textbook, homework, an exam or a note. The app guesses its type and title; check them and add the file."),
    dict(main="guides", page="Library", open="prompt", target="label:AI Assistant", title="Make a Prompt for Your AI", text="Choose the AI assistant you use: Claude, ChatGPT or Gemini. Only the way the finished page is handed over differs."),
    dict(main="guides", page="Library", open="prompt", target="label:Page", title="What to Make", text="Choose a study guide, a homework helper, a grade explanation, or an exam reflection or preparation page, then its number."),
    dict(main="guides", page="Library", open="prompt", target="css:[data-testid=stDialog] [data-testid=stCode]", title="Copy the Prompt", text="Copy this prompt into a chat with your AI together with your slides. Download the HTML page it makes and import it with Add a File."),
    dict(main="tasks", page="Calendar", cal_page="Task List", target="css:.st-key-tk_import_open button", title="Import From Syllabus", text="Reads the homework and exams of your courses (their course pages and syllabus files) and adds them as tasks for you to check."),
    dict(main="tasks", page="Calendar", cal_page="Task List", target="css:.st-key-tk_cal_open button", title="Import From Calendar", text="Paste the private calendar link of Canvas, Brightspace, Google Calendar or Shovel, or import an .ics file; the tasks and events stay up to date."),
    dict(main="schedule", page="Calendar", cal_page="Calendar", target="css:.st-key-cal_autoplan button", title="Auto-Plan", text="Click Auto-Plan and the free time before each deadline is filled with study sessions, earliest deadline first. The banner warns you when work does not fit."),
    dict(main="done", page="Home", target="", title="You Are Ready", text="That is everything to get started. Open the Note Reader to read your study guides next to their slides, and come back to Home to see what is due. You can start this tour again from Home any time."),
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


# ---------------------------------------------------------------- the guided tour
def active_tour():
    return st.session_state.get("_tour")


def start(step_key=None):
    """Start the tour at the first thing of a step of the chain (or at the welcome). The page is shown by `tour_before` on the next run."""
    i = 0 if step_key is None else next((n for n, s in enumerate(TOUR) if s["main"] == step_key), 0)
    st.session_state["_tour"] = {"i": i, "applied": -1, "base": None}


def stop(dismiss=False):
    st.session_state.pop("_tour", None)
    if dismiss:
        settings.set_tutorial(mode="dismissed")


def wants(name):
    """True while the step the tour is on needs the window `name` to be open (the pages ask this when they are drawn)."""
    tour = active_tour()
    return bool(tour and TOUR[tour["i"]].get("open") == name)


def _enter(i):
    """Show the page of step i (and remember how many of what it waits for there were)."""
    ss = st.session_state
    step = TOUR[i]
    tour = ss["_tour"]
    tour["i"], tour["applied"] = i, i
    ss["page"] = step["page"]
    if step["page"] == "Courses":
        ss["open_course"] = None
        ss.pop("course_tab", None)
    if step["page"] == "Library":
        ss["open_book"] = None
        ss.pop("lib_goto", None)
    if step.get("cal_page"):
        ss["cal_page"] = step["cal_page"]
    tour["base"] = facts().get(step["advance"]) if step.get("advance") else None


def tour_before():
    """Called by app.py before the page is drawn: the Back, Next and Skip of the helper card, the move to a step's page, and the step that moves on by itself."""
    ss = st.session_state
    tour = ss.get("_tour")
    if not tour:
        return
    sink = st.text_input("Tour Actions", key="tour_sink", label_visibility="collapsed")      # the helper card writes here (see tour_overlay.js)
    if sink and sink != ss.get("_tour_sink_done"):
        ss["_tour_sink_done"] = sink
        action = sink.split("|")[0]
        if action == "skip":
            stop(dismiss=True)
            return
        if action == "done":
            stop()
            return
        if action in ("next", "back"):
            _enter(max(0, min(len(TOUR) - 1, tour["i"] + (1 if action == "next" else -1))))
            return
    if tour["applied"] != tour["i"]:
        _enter(tour["i"])
        return
    step = TOUR[tour["i"]]
    if step.get("advance") and tour.get("base") is not None and facts().get(step["advance"], 0) > tour["base"]:      # the student did what the step asks
        _enter(min(len(TOUR) - 1, tour["i"] + 1))


def _chain(step):
    """The chain of the card: [{label, state}] with a tick for the steps before the present one."""
    keys = [k for k, *_ in STEPS]
    here = keys.index(step["main"]) if step["main"] in keys else (len(keys) if step["main"] == "done" else -1)
    return [{"label": title, "state": "done" if n < here else "now" if n == here else "todo"} for n, (_k, title, *_r) in enumerate(STEPS)]


def tour_after():
    """Called by app.py after the page is drawn: the overlay for the present step."""
    tour = active_tour()
    if not tour:
        if st.session_state.pop("_tour_drawn", False):                          # the tour ended (Skip, Finish): take its overlay away
            components.html("<script>(function(){var o=window.parent.document.getElementById('sa-tour');if(o){if(o.__stop)o.__stop();o.remove();}})();</script>", height=0)
        return
    st.session_state["_tour_drawn"] = True
    i = tour["i"]
    step = TOUR[i]
    cfg = {"i": i, "n": len(TOUR), "last": i == len(TOUR) - 1, "title": step["title"], "text": step["text"], "target": step.get("target", ""), "chain": _chain(step), "where": "Getting Started"}
    components.html("<script>" + OVERLAY.read_text(encoding="utf-8").replace("__CFG__", json.dumps(cfg)) + "</script>", height=0)


# ---------------------------------------------------------------- the checklist on Home
def _go(key):
    """The button of a step of the checklist: the tour, from that step."""
    start(key)
    st.rerun()


@st.dialog("Welcome to Study Assistant")
def _welcome():
    st.markdown("Study Assistant keeps your courses, files, notes, homework and study schedule in one place. A short guided tour shows you where to click for the first things to do; "
                "it takes a few minutes, and the checklist on this page ticks each step off when you have done it.")
    st.caption("You can skip it now and start it again later from Home or Settings > Help.")
    a, b = st.columns(2)
    if a.button("Start the Tour", key="tut_start", type="primary", width="stretch"):
        start()
        st.rerun()
    if b.button("Skip the Tutorial", key="tut_skip_welcome", width="stretch"):
        settings.set_tutorial(mode="dismissed")
        st.rerun()


def header_button():
    """In the row of the Home title, at the right: the button that opens the tutorial again after it was skipped or finished (Settings > Help has one too)."""
    if ensure_state().get("mode") == "active":
        return
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Show the Tutorial", key="tut_reopen", icon=":material/school:", help="the getting-started checklist and the guided tour"):
            settings.set_tutorial(mode="active", welcomed=True)
            st.rerun()


def _chain_html(flags):
    """The check chain of the checklist: a tick in a green circle for a step that is done, a blue circle for the next one, grey for the rest, joined by lines, with the names under them."""
    first_open = next((k for k, *_ in STEPS if not flags[k]), None)
    parts = []
    for n, (key, _title, _why, _button, short) in enumerate(STEPS, 1):
        state = "done" if flags[key] else "now" if key == first_open else "todo"
        if n > 1:
            parts.append(f"<div class='tc-line{' tc-done' if flags[STEPS[n - 2][0]] else ''}'></div>")
        parts.append(f"<div class='tc-step tc-{state}'><div class='tc-dot'>{'✓' if state == 'done' else n}</div><div class='tc-name'>{n}. {short}</div></div>")
    return f"<div class='tut-chain'>{''.join(parts)}</div>"


def render_card():
    """The checklist at the top of Home (nothing while it is skipped or finished: `header_button` brings it back)."""
    state = ensure_state()
    if state.get("mode") != "active":
        return
    if not state.get("welcomed"):
        settings.set_tutorial(welcomed=True)
        _welcome()
    flags = done_flags(facts())
    done = sum(flags.values())
    with st.container(border=True, key="tutorial_card"):
        head, tour_btn, skip = st.columns([3.2, 1.8, 1.6], vertical_alignment="center")
        head.subheader("Getting Started")
        if tour_btn.button("Start the Tour", key="tut_tour", icon=":material/play_circle:", type="primary", width="stretch", help="the guided tour: it shows you where to click"):
            start()
            st.rerun()
        if skip.button("Skip Tutorial", key="tut_skip", icon=":material/close:", width="stretch", help="hide this checklist; it can be shown again from home or in settings > help"):
            settings.set_tutorial(mode="dismissed")
            st.toast("Tutorial skipped. Click Show the Tutorial on Home to open it again.")
            st.rerun()
        st.markdown(_chain_html(flags), unsafe_allow_html=True)
        st.caption(f"{done} of {len(STEPS)} steps done")
        first_open = next((k for k, *_ in STEPS if not flags[k]), None)
        for number, (key, title, why, button, _short) in enumerate(STEPS, 1):
            mark, text, go = st.columns([0.5, 6.5, 2], vertical_alignment="center")
            mark.markdown(f"<div class='tut-mark{' tut-done' if flags[key] else ''}'>{'✓' if flags[key] else number}</div>", unsafe_allow_html=True)
            text.markdown(f"**{title}**" + ("  \n" if not flags[key] else " · done  \n") + f"<span class='tut-why'>{why}</span>", unsafe_allow_html=True)
            if go.button("Show Me" if not flags[key] else "Show Me Again", key=f"tut_go_{key}", type="primary" if key == first_open else "secondary", width="stretch", help=button.lower()):
                _go(key)
        if done == len(STEPS):
            st.success("Everything is set up. Open the Note Reader to read your guides next to their slides, and use Home to see what is due.", icon=":material/check_circle:")
            if st.button("Close Tutorial", key="tut_close", type="primary"):
                settings.set_tutorial(mode="dismissed")
                st.rerun()
