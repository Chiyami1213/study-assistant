"""Note Builder: up to three side-by-side windows (Library files to read, and the notes being built). Tabs on top
can be dragged into any order. Each active course has one notebook made of chapters; Export sends a chapter to
the File page under its course. What is open is remembered between sessions."""
import streamlit as st
import streamlit.components.v1 as components

import os
import shutil
import subprocess

import crud
import htmlnotes
import notesfs
import outline
import reader
import settings
from database import BASE_DIR

SECTIONS = [("notes", "Notes"), ("exercises", "Exercises")]
HTML_START = ("<!doctype", "<html", "<div", "<section", "<main", "<body", "<style")
PLACEHOLDER = "Write in Markdown. Use $...$ for math, for example $E = mc^2$."


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

    kind_rank = {"Textbook": 0, "Lecture Notes": 1, "Notes": 2}
    books = sorted(books, key=lambda b: (label(b).split(" · ")[0].lower(), kind_rank.get(b["kind"], 9), b["title"].lower()))
    ids = [b["id"] for b in books]
    by_id = {b["id"]: b for b in books}
    sel_key = f"lab_ref_book_{wid}"
    st.session_state.setdefault(sel_key, win.get("book") if win.get("book") in by_id else ids[0])
    book_id = st.session_state[sel_key] if st.session_state[sel_key] in by_id else ids[0]
    if win.get("book") != book_id:                      # remember which file each window shows
        _save_windows([{**w, "book": book_id} if w["id"] == wid else w for w in _windows()])
        st.rerun()                                      # so the tab title shows the new file
    book = by_id[book_id]
    saved = lab.get("pages", {}).get(str(book_id), 1)
    is_html = book["pdf_path"].lower().endswith((".html", ".htm"))
    with st.container(key=f"lab_refname_{wid}"):     # the file name is the heading; click it to pick another file
        with st.popover(book["title"], width="stretch"):
            st.selectbox("Reference File", ids, key=sel_key, label_visibility="collapsed",
                         format_func=lambda i: label(by_id[i]))
    path = BASE_DIR / book["pdf_path"]
    if not path.exists():
        st.error("The stored file is missing."); return
    if is_html:
        with st.container(key=f"lab_html_{wid}"):          # fills the window (page CSS)
            components.html(htmlnotes.safe_html(path.read_text(encoding="utf-8", errors="replace")), height=600, scrolling=True)
        return

    def remember(page):
        pages = settings.get_lab().get("pages", {})
        if pages.get(str(book_id)) != page:
            _remember(pages={**pages, str(book_id): page})

    reader.pdf_reader(path, f"lab_{wid}_{book_id}", height=None, start=saved, on_page=remember)


# ---------- Notes window: the notes being built ----------
def _dirty(ch):
    cid = ch["id"]
    return (st.session_state.get(f"lab_title_{cid}", ch["title"]) != ch["title"]
            or any(st.session_state.get(f"lab_{f}_{cid}", ch[f] or "") != (ch[f] or "") for f, _ in SECTIONS))


def _autosave(ch):
    cid = ch["id"]
    if _dirty(ch):
        crud.update_chapter(cid, st.session_state.get(f"lab_title_{cid}", ch["title"]).strip() or "Untitled Chapter",
                            {f: st.session_state.get(f"lab_{f}_{cid}", ch[f] or "") for f, _ in SECTIONS})


def _is_html(text):
    return text.lstrip().lower().startswith(HTML_START)


def _show(text, field):
    """A chapter body: Markdown, or a full interactive HTML page (as built with Claude)."""
    with st.container(key=f"lab_view_scroll_{field}"):          # sized by the page CSS to fill the window
        if _is_html(text):
            components.html(htmlnotes.safe_html(text), height=600, scrolling=True)
        else:
            st.markdown(text)


def _html_notes():
    return [b for b in crud.list_books() if b["pdf_path"].lower().endswith((".html", ".htm")) and b["kind"] != "Textbook"]


def _set_chapter(course_id, chapter_id):
    chapters = {**settings.get_lab().get("chapters", {}), str(course_id): chapter_id}
    _remember(course=course_id, chapters=chapters)
    st.session_state["lab_chapter"] = chapter_id


def _add_blank(course_id):
    """Callback: a new empty chapter, opened for editing."""
    _set_chapter(course_id, crud.add_chapter(course_id, f"Chapter {len(crud.list_chapters(course_id)) + 1}"))
    st.session_state["lab_editing"] = True


def _create_from_library(course_id, book_id, whole=True):
    """Callback: a new chapter that starts from a Library HTML note. `whole` copies the finished note as it is, to
    tailor from there; otherwise only its headings are used, in the standard blank format."""
    book = crud.get_book(book_id)
    if not book:
        return
    source = (BASE_DIR / book["pdf_path"]).read_text(encoding="utf-8", errors="replace")
    title, notes, exercises = outline.outline_from_html(source)
    if whole:
        notes = source
    title = book["title"] if whole else (title or book["title"])
    _set_chapter(course_id, crud.add_chapter(course_id, title, notes, exercises))
    st.session_state["lab_editing"] = False
    st.session_state["lab_flash"] = ("Copied the note. Edit it here or ask Claude in VS Code to tailor it." if whole
                                     else "Outline created. Press Edit to start tailoring it.")


def _remove_chapter(course_id, chapter_id):
    """Callback: remove a chapter (its exported copy stays on the File page until removed there)."""
    crud.delete_chapter(chapter_id)
    for f, _ in SECTIONS:
        st.session_state.pop(f"lab_{f}_{chapter_id}", None)
    st.session_state.pop(f"lab_title_{chapter_id}", None)
    st.session_state.pop("lab_confirm_remove", None)
    left = crud.list_chapters(course_id)
    _set_chapter(course_id, left[0]["id"] if left else None)


def _current_chapter():
    """(course, chapter) the notes window shows. Every active course has one notebook; None if none are active."""
    courses = {c["id"]: c for c in crud.courses_by_status("Active")}
    if not courses:
        return None, None
    lab = settings.get_lab()
    if st.session_state.get("lab_course") not in courses:
        st.session_state["lab_course"] = lab.get("course") if lab.get("course") in courses else next(iter(courses))
    return courses, st.session_state["lab_course"]


def _notes():
    courses, course_id = _current_chapter()
    if not courses:
        st.info("Notebooks belong to active courses. Add or activate a course first."); return
    lab = settings.get_lab()

    # Row 1: the course notebook and its chapters (add, remove)
    c_col, ch_col, add_col, rm_col = st.columns([1.5, 2.4, 1.4, 1.0], vertical_alignment="center", gap="small")
    course_id = c_col.selectbox("Course", list(courses), key="lab_course", label_visibility="collapsed",
                                format_func=lambda i: courses[i]["code"] or courses[i]["name"])
    chapters = crud.list_chapters(course_id)
    if not chapters:                                     # a notebook always has a first chapter
        crud.add_chapter(course_id, "Chapter 1")
        chapters = crud.list_chapters(course_id)
    ids = [c["id"] for c in chapters]
    by_id = {c["id"]: c for c in chapters}
    wanted = st.session_state.get("lab_chapter")
    if wanted not in by_id:
        wanted = lab.get("chapters", {}).get(str(course_id))
        st.session_state["lab_chapter"] = wanted if wanted in by_id else ids[0]
    prev = st.session_state.get("_lab_active")           # leaving a chapter keeps what was typed in it
    if prev and prev != st.session_state["lab_chapter"] and crud.get_chapter(prev):
        _autosave(crud.get_chapter(prev))
        chapters = crud.list_chapters(course_id); by_id = {c["id"]: c for c in chapters}
    cid = ch_col.selectbox("Chapter", ids, key="lab_chapter", label_visibility="collapsed",
                           format_func=lambda i: by_id[i]["title"] or "Untitled Chapter")
    with add_col.popover("Add Chapter", width="stretch"):
        st.button("Blank Chapter", key="lab_add_blank", width="stretch", on_click=_add_blank, args=(course_id,))
        sources = _html_notes()
        if sources:
            st.caption("Or start from a note already in the Library")
            src = st.selectbox("Library Note", [b["id"] for b in sources], key="lab_src", label_visibility="collapsed",
                               format_func=lambda i: next(b["title"] for b in sources if b["id"] == i))
            st.button("Start From This Note", key="lab_from_lib", type="primary", width="stretch",
                      on_click=_create_from_library, args=(course_id, src, True),
                      help="copies the whole note into a new chapter, ready to tailor")
            st.button("Outline Only", key="lab_from_outline", width="stretch",
                      on_click=_create_from_library, args=(course_id, src, False),
                      help="keeps only its headings in a blank standard page")
    if rm_col.button("Remove", key="lab_remove", width="stretch", disabled=len(ids) < 1,
                     help="remove this chapter"):
        st.session_state["lab_confirm_remove"] = cid
    _remember(course=course_id, chapters={**lab.get("chapters", {}), str(course_id): cid})
    st.session_state["_lab_active"] = cid
    if st.session_state.get("lab_confirm_remove") == cid:
        st.warning(f"Remove “{by_id[cid]['title']}” for good?")
        yes, no, _ = st.columns([1.2, 1, 4])
        yes.button("Yes, Remove", type="primary", key="lab_remove_yes", on_click=_remove_chapter, args=(course_id, cid))
        if no.button("Cancel", key="lab_remove_no"):
            st.session_state.pop("lab_confirm_remove", None)
            st.rerun()
    ch = by_id[cid]
    editing = st.session_state.setdefault("lab_editing", False)
    if st.session_state.get("lab_flash"):
        st.toast(st.session_state.pop("lab_flash"))

    title_key = f"lab_title_{cid}"
    keys = {f: f"lab_{f}_{cid}" for f, _ in SECTIONS}
    if editing:                                          # while typing, the boxes keep what is typed
        st.session_state.setdefault(title_key, ch["title"])
        for f, _ in SECTIONS:
            st.session_state.setdefault(keys[f], ch[f] or "")
    else:                                                # otherwise they follow the files (edited in VS Code, say)
        st.session_state[title_key] = ch["title"]
        for f, _ in SECTIONS:
            st.session_state[keys[f]] = ch[f] or ""
    if _dirty(ch) and editing:                           # typing is saved as it is committed, so nothing is lost
        _autosave(ch)
        ch = crud.get_chapter(cid)

    # Heading, then a slim toolbar on the right (Save Note, Edit, Export)
    if editing:
        st.text_input("Title", key=title_key, label_visibility="collapsed", placeholder="Chapter Title")
    else:
        st.markdown(f"<h3 class='lab-heading'>{_esc(st.session_state[title_key])}</h3>", unsafe_allow_html=True)
    _, save, edit, export = st.columns([2.2, 1.7, 1.0, 1.2], vertical_alignment="center", gap="small")
    if save.button("Save Note", type="primary", key="lab_save", icon=":material/save:", width="stretch"):
        _autosave(ch)
        st.toast("Note saved.")
        st.rerun()
    if edit.button("Done" if editing else "Edit", key="lab_edit", width="stretch"):
        st.session_state["lab_editing"] = not editing
        st.rerun()
    if export.button("Export", key="lab_export", width="stretch", help="send this chapter to the file page"):
        _autosave(ch)
        crud.export_chapter(cid)
        st.toast("Exported to the File page.")

    tabs = st.tabs([label for _, label in SECTIONS] + ["Claude"])
    for tab, (field, label) in zip(tabs, SECTIONS):
        with tab:
            if editing:
                st.text_area(label, key=keys[field], height=400, label_visibility="collapsed", placeholder=PLACEHOLDER)
            elif st.session_state[keys[field]].strip():
                _show(st.session_state[keys[field]], field)
            else:
                st.caption(f"Nothing in {label} yet. Press Edit to start writing.")
    with tabs[-1]:
        course = courses[course_id]
        _vscode_guide(course, ch)
    _watch(course_id, cid)


@st.fragment(run_every=2)
def _watch(course_id, chapter_id):
    """Refresh the page when the chapter's files change outside the app (Claude in VS Code, another editor)."""
    course, ch = crud.get_course(course_id), crud.get_chapter(chapter_id)
    if not course or not ch:
        return
    sig = notesfs.signature(course, ch)
    key = f"_lab_sig_{chapter_id}"
    prev = st.session_state.get(key)
    st.session_state[key] = sig
    if prev is not None and prev != sig and not st.session_state.get("lab_editing"):
        st.rerun()


def _open_folder(folder):
    os.startfile(folder) if hasattr(os, "startfile") else subprocess.Popen(["xdg-open", str(folder)])


def _open_vscode(folder):
    code = shutil.which("code")
    if code:
        main = next((folder / n for n in ("notes.html", "notes.md") if (folder / n).exists()), folder / "notes.html")
        subprocess.Popen([code, str(BASE_DIR), "-g", str(main)], shell=os.name == "nt")
    else:
        st.toast("VS Code's `code` command was not found. Open the folder by hand.")


def _vscode_guide(course, ch):
    """No API needed: the chapter is plain files, so Claude in VS Code can edit them and the app shows the result."""
    folder = notesfs.chapter_dir(course, ch, create=True)
    rel = folder.relative_to(BASE_DIR).as_posix()
    names = [(next((p.name for p in (folder / f"{f}.html", folder / f"{f}.md") if p.exists()), f"{f}.html")) for f in notesfs.FIELDS]
    st.markdown("**Build this chapter with Claude in VS Code.** Each tab is one interactive HTML page (formulas, step-through "
                "derivations, animations). Ask Claude there to edit the files, and this window updates within a couple of seconds.")
    st.code(chr(10).join(f"{rel}/{n}" for n in names), language="text")
    st.caption("Copy a prompt like this into Claude in VS Code:")
    st.code(f'Edit {rel}/{names[0]} for {crud.label(course)}, chapter "{ch["title"]}". '
            f'Keep it one self-contained interactive HTML page like the starter. Fill each section from the reference I have open, '
            f'with MathJax formulas, step-through derivations and an animation that shows the idea.', language="text")
    a, b, _ = st.columns([1.3, 1.6, 4])
    a.button("Open Folder", key="lab_open_folder", width="stretch", on_click=_open_folder, args=(folder,))
    b.button("Open in VS Code", key="lab_open_code", width="stretch", on_click=_open_vscode, args=(folder,))


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
        f'<div class="lab-tab" draggable="true" data-lab-tab="{w["id"]}" title="drag to move this window">'
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


def _dock(win):
    """Callback: bring a separate window back into the main window."""
    lab = settings.get_lab()
    popouts = {k: v for k, v in lab.get("popouts", {}).items() if k != win["id"]}
    wins = [w for w in lab.get("windows", _windows()) if w["id"] != win["id"]] + [win]
    settings.set_lab({**lab, "popouts": popouts, "windows": wins})


def render_detached(wid):
    """A window that was dragged out of the Note Builder tabs: just that window, full size."""
    st.markdown("<style>.stMainBlockContainer {padding: 0.4rem 0.8rem 0 !important; max-width: none !important;}"
                ".stMainBlockContainer > [data-testid='stVerticalBlock'] {gap: 0 !important;}"
                "[data-testid='stHeader'] {height: 0; min-height: 0; visibility: hidden;}"
                "[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'] {display: none !important;}"
                "[class*='st-key-lab_pane_'] {height: calc(100vh - 56px) !important;}"
                "[class*='st-key-lab_html_'], [class*='st-key-lab_html_'] [data-testid='stElementContainer'], "
                "[class*='st-key-lab_html_'] iframe {height: calc(100vh - 130px) !important;}"
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
