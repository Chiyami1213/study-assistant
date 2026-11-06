"""Note Reader: up to three side-by-side windows, each reading a Library file: a PDF, or one of the course's HTML notes. Tabs on
top can be dragged into any order. A note shows one tab for each part it has (notes, mind map, equation sheet, assumptions, quiz,
errata), in the order they appear in the note. What is open is remembered between sessions."""
import streamlit as st
import streamlit.components.v1 as components

import json
import re

import crud
import errata
import htmlnotes
import notesfs
import outline
import reader
import settings
from database import BASE_DIR

SECTIONS = [("notes", "Notes"), ("exercises", "Exercises"), ("errata", "Errata")]
HTML_START = ("<!doctype", "<html", "<div", "<section", "<main", "<body", "<style")


MAX_WINDOWS = 3


def _weights(wins):
    """Relative widths of the windows (dragged by the user; equal by default), by window id."""
    saved = settings.get_lab().get("widths", {})
    return [max(0.1, float(saved.get(w["id"], 1.0))) for w in wins]


def _windows():
    """Open windows in left-to-right order: [{'id', 'type': 'notes' | 'reference', 'book'}]."""
    wins = settings.get_lab().get("windows")
    if not wins:
        old = settings.get_lab()
        wins = [{"id": "r1", "type": "reference", "book": old.get("book")}, {"id": "n1", "type": "notes"}]
    return wins


def _save_windows(wins):
    _remember(windows=wins)


def _remember(**values):
    lab = settings.get_lab()
    if any(lab.get(k) != v for k, v in values.items()):
        settings.set_lab({**lab, **values})


@st.cache_data(show_spinner=False, max_entries=32)
def _placed(path, mtime, items_json):
    return errata.locate(path, mtime, json.loads(items_json))


def _errata_marks(book, path):
    """Errata of the HTML notes open next to this PDF (another window, or the chapter being built), for the same
    course, placed on this PDF's pages. Errata name pages and equations of the course lecture notes, so only a PDF of that
    kind carries marks."""
    if book["kind"] != "Lecture Notes":
        return []
    sources = []                                         # (course ids, html text)
    for w in _windows():
        other = crud.get_book(w["book"]) if w["type"] == "reference" and w.get("book") else None
        if other and other["id"] != book["id"] and other["pdf_path"].lower().endswith((".html", ".htm")):
            f = BASE_DIR / other["pdf_path"]
            if f.exists():
                sources.append((set(other["course_ids"]), f.read_text(encoding="utf-8", errors="replace"), f"book:{other['id']}"))
    lab = settings.get_lab()
    if any(w["type"] == "notes" for w in _windows()) and lab.get("course"):
        ch = crud.get_chapter(lab.get("chapters", {}).get(str(lab["course"])) or 0)
        if ch and notesfs.is_html(ch["notes"]):
            sources.append(({lab["course"]}, ch["notes"], f"book:{ch['source_book_id']}" if ch.get("source_book_id") else f"chapter:{ch['id']}"))
    items, seen = [], set()
    for courses, text, src in sources:
        if courses & set(book["course_ids"]):
            for it in errata.parse(text):
                if (it["where"], it["md"]) not in seen:
                    seen.add((it["where"], it["md"]))
                    items.append({**it, "n": len(items) + 1, "src": src, "idx": it["n"]})
    return _placed(str(path), path.stat().st_mtime, json.dumps(items)) if items else []


# ---------- Reference window: a Library file, page by page ----------
def _reference(win):
    wid = win["id"]
    lab = settings.get_lab()
    books = crud.list_books()
    if not books:
        st.info("Add a file in the Library to read it here."); return
    courses = {c["id"]: c for c in crud.list_courses(section=None)}

    def label(b):                    # "AE 6009 · Notes · Adding Angular Momenta"
        codes = " / ".join(courses[i]["code"] or courses[i]["name"] for i in b["course_ids"] if i in courses) or "No Course"
        return f"{codes} · {b['kind']} · {b['title']}"

    kind_rank = {"Textbook": 0, "Lecture Notes": 1, "Notes": 2, "Homework": 3, "Homework Solution": 4, "Exam": 5, "Graded Homework": 6, "Practice Exam": 7, "Exam Solution": 8, "Graded Exam": 9, "Syllabus": 10, "Equation Sheet": 11}
    books = sorted(books, key=lambda b: (label(b).split(" · ")[0].lower(), kind_rank.get(b["kind"], 9), b["title"].lower()))
    ids = [b["id"] for b in books]
    by_id = {b["id"]: b for b in books}
    sel_key = f"lab_ref_book_{wid}"
    ck, kk = f"lab_ref_course_{wid}", f"lab_ref_kind_{wid}"
    st.session_state.setdefault(sel_key, win.get("book") if win.get("book") in by_id else ids[0])
    cur = by_id[st.session_state[sel_key]] if st.session_state[sel_key] in by_id else books[0]
    own_course = lambda b: next((i for i in b["course_ids"] if i in courses), 0)       # 0 = a file with no course
    order = {c["id"]: n for n, c in enumerate(c for s in crud.STATUSES for c in crud.courses_by_status(s))}
    course_ids = sorted({own_course(b) for b in books}, key=lambda i: (order.get(i, 999), i))
    course_name = lambda i: (courses[i]["code"] or courses[i]["name"]) if i in courses else "No Course"
    st.session_state.setdefault(ck, own_course(cur))
    if st.session_state[ck] not in course_ids:
        st.session_state[ck] = own_course(cur)
    in_course = [b for b in books if own_course(b) == st.session_state[ck]]
    kinds = [k for k in ("Textbook", "Lecture Notes", "Notes", "Homework", "Homework Solution", "Exam", "Graded Homework", "Practice Exam", "Exam Solution", "Graded Exam", "Syllabus", "Equation Sheet") if any(b["kind"] == k for b in in_course)] or ["Notes"]
    kinds += sorted({b["kind"] for b in in_course} - set(kinds))
    st.session_state.setdefault(kk, cur["kind"] if cur["kind"] in kinds else kinds[0])
    if st.session_state[kk] not in kinds:
        st.session_state[kk] = kinds[0]

    def lec_order(b):
        return (tuple(int(n) for n in re.findall(r"\d+", b.get("lecture") or "")), b["title"].lower())

    files = sorted((b for b in in_course if b["kind"] == st.session_state[kk]), key=lec_order)
    if st.session_state[sel_key] not in [b["id"] for b in files]:         # the course or category was changed
        st.session_state[sel_key] = files[0]["id"] if files else cur["id"]
    book_id = st.session_state[sel_key] if st.session_state[sel_key] in by_id else ids[0]
    if win.get("book") != book_id:                      # remember which file each window shows
        _save_windows([{**w, "book": book_id} if w["id"] == wid else w for w in _windows()])
        st.rerun()                                      # so the tab title shows the new file

    def file_name(b):
        tag = ("HW " if b["kind"] == "Homework" else "Lec ") + b["lecture"] + " · " if b.get("lecture") else ""
        return tag + b["title"]

    book = by_id[book_id]
    saved = lab.get("pages", {}).get(str(book_id), 1)
    is_html = book["pdf_path"].lower().endswith((".html", ".htm"))
    with st.container(key=f"lab_refname_{wid}"):     # the file name is the heading; click it to pick another file
        with st.popover(book["title"], width="stretch", help=book["title"]):
            c1, c2 = st.columns(2)
            c1.selectbox("Course", course_ids, key=ck, format_func=course_name)
            c2.selectbox("Category", kinds, key=kk)
            st.selectbox("File", [b["id"] for b in files], key=sel_key, format_func=lambda i: file_name(by_id[i]))
    path = BASE_DIR / book["pdf_path"]
    if not path.exists():
        st.error("The stored file is missing."); return
    if is_html:
        with st.container(key=f"lab_html_{wid}"):          # fills the window (page CSS)
            from views import quiz_view                    # the note's Self-check shows the same questions as the course Quiz tab
            components.html(htmlnotes.safe_html(path.read_text(encoding="utf-8", errors="replace"),
                                                questions=quiz_view.book_questions(book), errata_source=f"book:{book['id']}"),
                            height=600, scrolling=True)
        return

    def remember(page):
        pages = settings.get_lab().get("pages", {})
        if pages.get(str(book_id)) != page:
            _remember(pages={**pages, str(book_id): page})

    marks = _errata_marks(book, path)
    active = set()
    clicked = st.session_state.get("lab_errata_active")                # (source, number, stamp) of the erratum clicked in a note
    if clicked:
        hit = [m for m in marks if m.get("src") == clicked[0] and m.get("idx") == clicked[1]]
        active = {m["n"] for m in hit}
        if hit and st.session_state.get(f"_errata_seen_{wid}") != clicked[2]:      # once per click: go to its page
            st.session_state[f"_errata_seen_{wid}"] = clicked[2]
            where = [m for m in hit if not m.get("sentence")] or hit                  # the named place first, then quotes
            st.session_state[f"lab_{wid}_{book_id}_page"] = min(m["page"] for m in where) + 1
            reader._bump(f"lab_{wid}_{book_id}")
            st.session_state["_errata_hit"] = True
    reader.pdf_reader(path, f"lab_{wid}_{book_id}", height=None, start=saved, on_page=remember, marks=marks,
                      active=active or None)


# ---------- Notes window: the notes being built ----------
def _is_html(text):
    return text.lstrip().lower().startswith(HTML_START)


def _show_part(text, book, part):
    """One tab of a note: the whole page, opened at that part (so links between its parts keep working)."""
    with st.container(key=f"lab_view_scroll_{part['key']}"):          # sized by the page CSS to fill the window
        from views import quiz_view                          # the Self-check shows the same questions as the course Quiz tab
        own_quiz = 'id="qBox"' in text                       # a note with its own quiz script runs it as it is
        questions = None if own_quiz else quiz_view.book_questions(book)
        components.html(htmlnotes.safe_html(text, part["section"], questions=questions, errata_source=f"book:{book['id']}"),
                        height=600, scrolling=True)


def _html_notes():
    return [b for b in crud.list_books() if b["pdf_path"].lower().endswith((".html", ".htm")) and b["kind"] != "Textbook"]


def _current_chapter():
    """(course, chapter) the notes window shows. Every active course has one notebook; None if none are active."""
    courses = {c["id"]: c for s in crud.STATUSES for c in crud.courses_by_status(s)}      # menu order: Active, Self-Study, Completed
    if not courses:
        return None, None
    lab = settings.get_lab()
    if st.session_state.get("lab_course") not in courses:
        st.session_state["lab_course"] = lab.get("course") if lab.get("course") in courses else next(iter(courses))
    return courses, st.session_state["lab_course"]


def _course_notes(course_id):
    """The course's HTML notes in the Library (type Notes), in lecture order."""
    def order(b):
        nums = [int(n) for n in re.findall(r"\d+", b.get("lecture") or "")]
        return (nums[0] if nums else 999, nums[1:] or [0], b["title"].lower())

    return sorted((b for b in crud.list_books() if course_id in b["course_ids"] and b["kind"] == "Notes"
                   and b["pdf_path"].lower().endswith((".html", ".htm"))), key=order)


def _notes():
    courses, course_id = _current_chapter()
    if not courses:
        st.info("Add a course first."); return
    lab = settings.get_lab()

    c_col, n_col = st.columns([1.5, 4], vertical_alignment="center", gap="small")
    course_id = c_col.selectbox("Course", list(courses), key="lab_course", label_visibility="collapsed",
                                format_func=lambda i: courses[i]["code"] or courses[i]["name"])
    notes = _course_notes(course_id)
    _remember(course=course_id)
    if not notes:
        st.info("This course has no HTML notes yet. Add a note to the Library (type Notes) and it can be read here.")
        return
    ids = [b["id"] for b in notes]
    by_id = {b["id"]: b for b in notes}
    if st.session_state.get("lab_note") not in by_id:
        saved = lab.get("notes", {}).get(str(course_id))
        st.session_state["lab_note"] = saved if saved in by_id else ids[0]
    book_id = n_col.selectbox("Note", ids, key="lab_note", label_visibility="collapsed",
                              format_func=lambda i: (f"Lec {by_id[i]['lecture']} · " if by_id[i].get("lecture") else "") + by_id[i]["title"])
    _remember(notes={**lab.get("notes", {}), str(course_id): book_id})
    book = by_id[book_id]
    path = BASE_DIR / book["pdf_path"]
    if not path.exists():
        st.error("The stored note file is missing."); return
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = outline.parts(text)

    with st.container(key="lab_toolbar"):
        st.markdown(f"<h3 class='lab-heading' title=\"{_attr(book['title'])}\">{_esc(book['title'])}</h3>", unsafe_allow_html=True)
    with st.container(key="lab_tabs_wrap"):
        labels = [p["label"] for p in parts]
        tabs = st.tabs(labels, key=f"lab_tabs_{book_id}", on_change="rerun")
        for tab, part in zip(tabs, parts):
            with tab:
                if tab.open:
                    _show_part(text, book, part)


def _attr(text):
    """Text for an HTML attribute (the full name shown when the mouse rests on a shortened one)."""
    return (text or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _esc(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


ICONS = {"notes": '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M4 4h12l4 4v12H4z" opacity=".35"/>'
                  '<path d="M7 11h10v1.6H7zm0 3.4h10V16H7zM7 7.6h6v1.6H7z"/></svg>',
         "reference": '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M5 3h12a2 2 0 0 1 2 2v16l-8-3-8 3V5a2 2 0 0 1 2-2z" '
                      'opacity=".9"/></svg>'}


def _tab_title(win):
    if win["type"] == "notes":
        lab = settings.get_lab()
        ch = crud.get_chapter(lab["chapters"].get(str(lab.get("course")))) if lab.get("chapters") and lab.get("course") else None
        course = crud.get_course(lab["course"]) if lab.get("course") else None
        return f"{course['code'] or course['name']} · {ch['title']}" if ch and course else "Notes"
    book = crud.get_book(win["book"]) if win.get("book") else None
    return book["title"] if book else "Reference"


def _handle_tab_action(wins):
    """The tab strip writes 'order:id,id|stamp', 'close:id|stamp' or 'add:|stamp' into a hidden box."""
    sink = st.text_input("Window Order", key="lab_tab_sink", label_visibility="collapsed")
    if not sink or sink == st.session_state.get("_lab_tab_done"):
        return
    st.session_state["_lab_tab_done"] = sink
    action, _, rest = sink.split("|")[0].partition(":")
    ids = [w["id"] for w in wins]
    if action == "order" and sorted(rest.split(",")) == sorted(ids) and rest.split(",") != ids:
        by = {w["id"]: w for w in wins}
        _save_windows([by[i] for i in rest.split(",")])
        st.rerun()
    elif action == "detach" and rest in ids and len(wins) > 1:       # the tab was dragged out into its own window
        lab = settings.get_lab()
        popouts = {**lab.get("popouts", {}), rest: next(w for w in wins if w["id"] == rest)}
        settings.set_lab({**lab, "popouts": popouts, "windows": [w for w in wins if w["id"] != rest]})
        st.rerun()
    elif action == "errata":                                         # "errata:book:16:3": erratum 3 of note 16 was clicked
        src, _, idx = rest.rpartition(":")
        if idx.isdigit():
            st.session_state["lab_errata_active"] = (src, int(idx), sink.split("|")[-1])
            st.session_state["_errata_hit"] = False
            st.rerun()
    elif action == "widths":                                         # a divider was dragged: "id=0.4,id=0.6"
        try:
            pairs = [item.split("=") for item in rest.split(",")]
            widths = {k: min(5.0, max(0.1, float(v))) for k, v in pairs if k in ids}
        except ValueError:
            return
        if widths:
            _remember(widths={**settings.get_lab().get("widths", {}), **widths})
            st.rerun()
    elif action == "close" and rest in ids and len(wins) > 1:
        _save_windows([w for w in wins if w["id"] != rest])
        st.rerun()
    elif action == "add" and len(wins) < MAX_WINDOWS:
        used = {w["id"] for w in wins}
        if not any(w["type"] == "notes" for w in wins):
            new = {"id": "n1", "type": "notes"}
        else:
            n = next(i for i in range(1, 10) if f"r{i}" not in used)
            new = {"id": f"r{n}", "type": "reference", "book": None}
        _save_windows(wins + [new])
        st.rerun()


def _tab_strip(wins):
    """Browser-style tabs above the windows. Drag a tab to any place in the row to reorder; x closes; + adds."""
    _handle_tab_action(wins)
    tabs = "".join(
        f'<div class="lab-tab" draggable="true" data-lab-tab="{w["id"]}" title="{_attr(_tab_title(w))}">'
        f'{ICONS[w["type"]]}<span>{_esc(_tab_title(w))}</span>'
        f'{"<b class=lab-x data-lab-close=" + w["id"] + " title=&quot;close this window&quot;>×</b>" if len(wins) > 1 else ""}</div>'
        for w in wins)
    plus = ('<div class="lab-add" data-lab-add="1" title="add a window">+</div>' if len(wins) < MAX_WINDOWS else "")
    st.markdown(f'<style>.stMainBlockContainer {{padding: 0.5rem 2.8rem 0 0.8rem !important; max-width: none !important;}}'
                f'.stMainBlockContainer > [data-testid="stVerticalBlock"] {{gap: 0.25rem;}}'
                f'[data-testid="stHeader"] {{height: 0; min-height: 0; visibility: hidden;}}</style>'
                f'<div class="lab-tabs" style="grid-template-columns: {" ".join(f"minmax(0, {w:g}fr)" for w in _weights(wins))}">{tabs}{plus}</div>',
                unsafe_allow_html=True)


def render():
    wins = _windows()
    _tab_strip(wins)
    for col, win in zip(st.columns(_weights(wins), gap="small"), wins):
        with col, st.container(key=f"lab_pane_{win['id']}"):
            if win["type"] == "notes":
                _notes()
            else:
                _reference(win)
    clicked = st.session_state.get("lab_errata_active")
    if clicked and st.session_state.get("_errata_toasted") != clicked[2]:
        st.session_state["_errata_toasted"] = clicked[2]
        if not st.session_state.get("_errata_hit"):
            lecture_notes_open = any(
                w["type"] == "reference" and (crud.get_book(w.get("book") or 0) or {}).get("kind") == "Lecture Notes" for w in wins)
            st.toast("This erratum is about text that is not in the open lecture notes (it names slides of another handout). Open that handout in a window to see it marked."
                     if lecture_notes_open else "Open the course's lecture notes PDF in another window to see where this erratum is.")


def _dock(win):
    """Callback: bring a separate window back into the main window."""
    lab = settings.get_lab()
    popouts = {k: v for k, v in lab.get("popouts", {}).items() if k != win["id"]}
    wins = [w for w in lab.get("windows", _windows()) if w["id"] != win["id"]] + [win]
    settings.set_lab({**lab, "popouts": popouts, "windows": wins})


def render_detached(wid):
    """A window that was dragged out of the Note Reader tabs: just that window, full size."""
    st.markdown("<style>.stMainBlockContainer {padding: 0.4rem 0.8rem 0 !important; max-width: none !important;}"
                ".stMainBlockContainer > [data-testid='stVerticalBlock'] {gap: 0 !important;}"
                "[data-testid='stHeader'] {height: 0; min-height: 0; visibility: hidden;}"
                "[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'] {display: none !important;}"
                "[class*='st-key-lab_pane_'] {height: calc(100vh - 56px) !important;}"
                "[class*='st-key-lab_html_'], [class*='st-key-lab_html_'] [data-testid='stElementContainer'], "
                "[class*='st-key-lab_html_'] iframe {height: calc(100vh - 120px) !important;}"
                ".rd-scroll.rd-fill {height: calc(100vh - 150px) !important;}"
                "[class*='st-key-lab_view_scroll'], [class*='st-key-lab_view_scroll'] iframe {height: calc(100vh - 270px) !important;}"
                "</style>", unsafe_allow_html=True)
    win = settings.get_lab().get("popouts", {}).get(wid)
    if not win:
        st.info("This window was moved back to the main window. You can close it."); return
    top, dock = st.columns([6, 1.6], vertical_alignment="center")
    top.markdown(f"<div class='lab-detached-title'>{_esc(_tab_title(win))}</div>", unsafe_allow_html=True)
    dock.button("Move Back", key=f"lab_dock_{wid}", width="stretch", on_click=_dock, args=(win,),
                help="put this window back into the main window")
    with st.container(key=f"lab_pane_{wid}"):
        _notes() if win["type"] == "notes" else _reference(win)
