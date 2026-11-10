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
import outline
import reader
import settings
from database import BASE_DIR, data_path

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
    """Errata of the HTML notes open next to this PDF (another window, or the note the Notes window shows), for the same
    course, placed on this PDF's pages. Errata name pages and equations of the course lecture notes, so only a PDF of that
    kind carries marks."""
    if book["kind"] != "Lecture Notes":
        return []
    sources = []                                         # (course ids, html text)
    for w in _windows():
        other = crud.get_book(w["book"]) if w["type"] == "reference" and w.get("book") else None
        if other and other["id"] != book["id"] and other["pdf_path"].lower().endswith((".html", ".htm")):
            f = data_path(other["pdf_path"])
            if f.exists():
                sources.append((set(other["course_ids"]), f.read_text(encoding="utf-8", errors="replace"), f"book:{other['id']}"))
    lab = settings.get_lab()
    if any(w["type"] == "notes" for w in _windows()) and lab.get("course"):          # the note the Notes window shows
        shown = crud.get_book(lab.get("notes", {}).get(str(lab["course"])) or 0)
        if shown and shown["pdf_path"].lower().endswith((".html", ".htm")) and data_path(shown["pdf_path"]).exists():
            sources.append(({lab["course"]}, data_path(shown["pdf_path"]).read_text(encoding="utf-8", errors="replace"), f"book:{shown['id']}"))
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

    def label(b):                    # "MATH 101 · Notes · Eigenvalues"
        codes = " / ".join(courses[i]["code"] or courses[i]["name"] for i in b["course_ids"] if i in courses) or "No Course"
        return f"{codes} · {b['kind']} · {b['title']}"

    kind_rank = {"Textbook": 0, "Lecture Notes": 1, "Notes": 2, "Homework": 3, "Homework Solution": 4, "Exam": 5, "Graded Homework": 6, "Practice Exam": 7, "Exam Solution": 8, "Graded Exam": 9, "Exam Preparation": 10, "Exam Reflection": 10.5, "Syllabus": 11, "Equation Sheet": 12}
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
    kinds = [k for k in ("Textbook", "Lecture Notes", "Notes", "Homework", "Homework Solution", "Exam", "Graded Homework", "Practice Exam", "Exam Solution", "Graded Exam", "Exam Preparation", "Exam Reflection", "Syllabus", "Equation Sheet") if any(b["kind"] == k for b in in_course)] or ["Notes"]
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
    path = data_path(book["pdf_path"])
    if not path.exists():
        st.error("The stored file is missing."); return
    if is_html:
        with st.container(key=f"lab_html_{wid}"):          # fills the window (page CSS)
            from views import quiz_view                    # the note's Self-check shows the same questions as the course Quiz tab
            components.html(htmlnotes.safe_html(path.read_text(encoding="utf-8", errors="replace"),
                                                questions=quiz_view.book_questions(book), errata_source=f"book:{book['id']}",
                                                resume="reference", slides=book["id"]), height=600, scrolling=True)
        return

    pdf_key = f"lab_{wid}_{book_id}"
    seen = lab.get("view", {}).get(str(book_id), {})
    if seen.get("zoom"):
        st.session_state.setdefault(f"{pdf_key}_zoom", seen["zoom"])
    if seen.get("mode"):
        st.session_state.setdefault(f"{pdf_key}_view", seen["mode"])

    def remember(page):
        now = settings.get_lab()
        pages = now.get("pages", {})
        if pages.get(str(book_id)) != page:
            _remember(pages={**pages, str(book_id): page})
        view = {"zoom": st.session_state.get(f"{pdf_key}_zoom", 100), "mode": st.session_state.get(f"{pdf_key}_view", "page")}
        if now.get("view", {}).get(str(book_id)) != view:
            _remember(view={**now.get("view", {}), str(book_id): view})

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
        components.html(htmlnotes.safe_html(text, part["section"], questions=questions, errata_source=f"book:{book['id']}",
                                            resume=f"reader:{part['key']}", slides=book["id"], anchor="win"), height=600, scrolling=True)


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

    c_col, n_col, f_col = st.columns([1.5, 4, 0.5], vertical_alignment="center", gap="small")
    f_col.button("", icon=":material/fullscreen:", key="lab_full_open", help="show the notes full screen", width="stretch",
                 on_click=lambda: st.session_state.update(lab_full=True))
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
    path = data_path(book["pdf_path"])
    if not path.exists():
        st.error("The stored note file is missing."); return
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = outline.parts(text)

    with st.container(key="lab_toolbar"):
        st.markdown(f"<h3 class='lab-heading' title=\"{_attr(book['title'])}\">{_esc(book['title'])}</h3>", unsafe_allow_html=True)
    with st.container(key="lab_tabs_wrap"):
        labels = [p["label"] for p in parts]
        last = lab.get("tabs", {}).get(str(book_id))                       # the tab this note was left on
        first_run = f"_lab_tabs_seen_{book_id}" not in st.session_state       # the saved tab is applied once, then the user's clicks rule
        st.session_state[f"_lab_tabs_seen_{book_id}"] = True
        tabs = st.tabs(labels, key=f"lab_tabs_{book_id}", on_change="rerun", default=last if (first_run and last in labels) else None)
        for tab, part in zip(tabs, parts):
            with tab:
                if tab.open:
                    _show_part(text, book, part)
                    if lab.get("tabs", {}).get(str(book_id)) != part["label"]:
                        _remember(tabs={**lab.get("tabs", {}), str(book_id): part["label"]})


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
        course = crud.get_course(lab["course"]) if lab.get("course") else None
        return f"{course['code'] or course['name']} · Notes" if course else "Notes"
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
    elif action == "slide":                                          # "slide:<note id>:<lecture>:<page>": a slide number in a note was clicked
        note_id, _, tail = rest.partition(":")
        lecture, _, page = tail.partition(":")
        if note_id.isdigit() and page.isdigit():
            _show_slide(wins, crud.get_book(int(note_id)), lecture, int(page))
    elif action == "eq":                                             # "eq:<json>": an equation of a note was clicked
        import urllib.parse
        try:
            _show_equation(wins, json.loads(urllib.parse.unquote(rest)))
        except (ValueError, KeyError):
            pass
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


def _lecture_numbers(text):
    """Lecture numbers a Library lecture field covers: '5' -> {5}, '4-5' -> {4, 5}, '8-10' -> {8, 9, 10}."""
    nums = [int(n) for n in re.findall(r"\d+", text or "")]
    return set(range(nums[0], nums[-1] + 1)) if len(nums) > 1 and nums[0] <= nums[-1] else set(nums)


def _slides_book(note, lecture):
    """The lecture slides (Library type Lecture Notes) of the course of `note` that hold lecture `lecture` (the note's own lecture if empty)."""
    want = int(lecture) if str(lecture).isdigit() else None
    if want is None:
        mine = sorted(_lecture_numbers(note.get("lecture")))
        want = mine[0] if mine else None
    decks = [b for b in crud.list_books() if b["kind"] == "Lecture Notes" and set(b["course_ids"]) & set(note["course_ids"])
             and b["pdf_path"].lower().endswith(".pdf")]
    key = lambda b: ([int(n) for n in re.findall(r"\d+", b.get("lecture") or "")], b["title"].lower())
    decks.sort(key=key)
    firsts = [(key(b)[0] or [None])[0] for b in decks]
    if want is not None:
        if len(set(firsts)) < len(firsts):                     # "1-1", "1-2", "2-1" ...: chapter and lecture of the chapter, not a range
            decks = [b for b, f in zip(decks, firsts) if f == want]
        else:
            decks = [b for b in decks if want in _lecture_numbers(b.get("lecture"))]
    return decks[0] if decks else None


def _open_pdf(wins, deck, page):
    """Show page `page` of a Library PDF: in the window that already shows it; else in a new window beside the others (all windows share
    the width equally); with three windows already, in the first reference window."""
    wid = next((w["id"] for w in wins if w["type"] == "reference" and w.get("book") == deck["id"]), None)
    if wid is None:
        if len(wins) < MAX_WINDOWS:
            used = {w["id"] for w in wins}
            wid = next(f"r{i}" for i in range(1, 10) if f"r{i}" not in used)
            new = wins + [{"id": wid, "type": "reference", "book": deck["id"]}]
        else:
            wid = next((w["id"] for w in wins if w["type"] == "reference"), wins[-1]["id"])
            new = [{**w, "type": "reference", "book": deck["id"]} if w["id"] == wid else w for w in wins]
        st.session_state[f"lab_ref_book_{wid}"] = deck["id"]            # the window starts on this file (not on what the id showed before)
        st.session_state[f"lab_ref_course_{wid}"] = next(iter(deck["course_ids"]), 0)
        st.session_state[f"lab_ref_kind_{wid}"] = deck["kind"]
        lab = settings.get_lab()
        _remember(windows=new, widths={**lab.get("widths", {}), **{w["id"]: 1.0 for w in new}})
    lab = settings.get_lab()
    _remember(pages={**lab.get("pages", {}), str(deck["id"]): page})
    st.session_state[f"lab_{wid}_{deck['id']}_page"] = page
    reader._bump(f"lab_{wid}_{deck['id']}")
    st.rerun()


def _show_slide(wins, note, lecture, page):
    """Take the reader to a slide of the lecture slides."""
    deck = _slides_book(note, lecture) if note else None
    if not deck:
        st.toast("These slides are not in the Library.", icon=":material/info:")
        return
    _open_pdf(wins, deck, page)


def _words(text):
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower())}


def _best_page(path, first, last, context, candidates=None, heading=""):
    """The page (1-based) among `candidates` (default first..last) whose text shares most words with the text around the equation, the words of the
    heading counting three times; the first candidate when none does."""
    import pymupdf
    pages = list(candidates) if candidates else list(range(first, last + 1))
    want, head = _words(context), _words(heading)
    if not pages or (not want and not head) or len(pages) == 1:
        return pages[0] if pages else first
    best, score = pages[0], 0
    with pymupdf.open(str(path)) as doc:
        for pg in pages:
            if pg > doc.page_count:
                break
            words = _words(doc[pg - 1].get_text())
            hit = len(want & words) + 3 * len(head & words)
            if hit > score:
                best, score = pg, hit
    return best


_SETS = {}


def _slide_sets(path):
    """The slide sets inside one lecture PDF, from the page headers ('3 Diatomic Properties-5 School of ...': the slide set's title and the number of its
    first slide on that page): [{'title', 'pages': [(pdf page, slide number), ...]}]. Empty when the pdf has no such headers."""
    import pymupdf
    key = (str(path), path.stat().st_mtime)
    if key in _SETS:
        return _SETS[key]
    sets = []
    try:
        with pymupdf.open(str(path)) as doc:
            for i in range(min(doc.page_count, 600)):
                head = " ".join(doc[i].get_text()[:400].split())
                m = re.match(r"\d+\s+(.+?)-(\d+)\s+School of", head)
                if not m:
                    continue
                title, n = m.group(1).strip(), int(m.group(2))
                if not sets or sets[-1]["title"] != title:
                    sets.append({"title": title, "pages": []})
                sets[-1]["pages"].append((i + 1, n))
    except Exception:
        sets = []
    _SETS[key] = sets
    return sets


def _set_pages(path, title, first, last):
    """PDF pages of the slide set whose title shares a word with `title` ('Diatomic Molecules' ~ 'Diatomic Properties') that carry slides first..last
    (a page holds two slides: n and n+1); None when the pdf has no slide sets or none matches."""
    want = _words(title)
    sets = _slide_sets(path)
    if not want or not sets:
        return None
    scored = sorted(((len(want & _words(s["title"])), -i, s) for i, s in enumerate(sets)), reverse=True)
    if not scored or scored[0][0] == 0:
        return None
    pages = scored[0][2]["pages"]
    inside = [pg for pg, n in pages if n <= last and n + 1 >= first]
    return inside or [pages[0][0]]


def _printed_offset(path):
    """PDF page number minus the page number printed on the page (the front matter of a textbook shifts them)."""
    import collections
    import pymupdf
    votes = collections.Counter()
    with pymupdf.open(str(path)) as doc:
        for i in range(min(doc.page_count, 120)):
            lines = [l.strip() for l in doc[i].get_text().split("\n") if l.strip()]
            for l in lines[:2] + lines[-2:]:
                if l.isdigit() and 1 <= int(l) <= 1500 and i + 1 - int(l) >= 0:
                    votes[i + 1 - int(l)] += 1
    return votes.most_common(1)[0][0] if votes else 0


def _lecture_source(note, src, ctx, heading=""):
    """(book, page) for a source line like 'Lec 14, slides 2-3', 'Lec 3-1, Perfect Gases 1-14' or 'Notes Eqs. (427)-(433)'; None if it names none."""
    import errata
    m = re.match(r"\s*Lec(?:ture)?\s*(\d+(?:-\d+)?)\s*,?\s*(.*)$", src or "", re.I)
    if m:
        lecture, rest = m.group(1), m.group(2).strip()
        one = r"(?:(?P<title>[A-Za-z][^\d;]*?)\s+)?(?:slides?\s+)?(?P<a>\d+)(?:\s*[\u2013-]\s*(?P<b>\d+))?"
        pages = None
        parts = [s.strip() for s in rest.split(";") if s.strip()] or [rest]       # "Independent Energy Modes 1\u20135; Translational Properties 1\u201311": several slide sets
        if len(parts) > 1:                                                         # the part whose title shares the most words with the equation's heading
            hw = _words(f"{heading} {ctx}")
            parts.sort(key=lambda s: -len(_words(re.sub(r"[\d\u2013-]+\s*$", "", s)) & hw))
        for part in parts:
            pages = re.fullmatch(one, part, re.I)
            if pages:
                break
        first = int(pages.group("a")) if pages else 1
        last = int(pages.group("b") or first) if pages else first
        title = (pages.group("title") or "").strip().lower() if pages else ""
        decks = [b for b in crud.list_books() if b["kind"] == "Lecture Notes" and set(b["course_ids"]) & set(note["course_ids"])
                 and b["pdf_path"].lower().endswith(".pdf")]
        same = [b for b in decks if (b.get("lecture") or "") == lecture]
        deck = next((b for b in same if title and title in b["title"].lower()), None) or (same[0] if same else _slides_book(note, lecture))
        if deck:
            path = data_path(deck["pdf_path"])
            return deck, _best_page(path, first, last, ctx, _set_pages(path, title, first, last), heading)
    m = re.search(r"Eqs?\.?\s*\((\d{1,4})\)", src or "")
    if m:                                                     # equation numbers of the course lecture notes: the page that carries the tag
        for b in crud.list_books():
            if b["kind"] == "Lecture Notes" and set(b["course_ids"]) & set(note["course_ids"]) and b["pdf_path"].lower().endswith(".pdf"):
                path = data_path(b["pdf_path"])
                tags = errata._equation_tags(str(path), path.stat().st_mtime).get(int(m.group(1)))
                if tags:
                    return b, tags[0][0] + 1
    return None


def _textbook_source(note, vk, ctx="", heading=""):
    """(book, page) for a line like 'V&K III §8, pp. 77-82': the page of the course's textbook (printed numbers made PDF numbers); of the range,
    the page that fits the text around the equation."""
    m = re.search(r"\bpp?\.\s*(\d{1,4})(?:\s*[–-]\s*(\d{1,4}))?", vk or "")
    books = [b for b in crud.list_books() if b["kind"] == "Textbook" and set(b["course_ids"]) & set(note["course_ids"])
             and b["pdf_path"].lower().endswith(".pdf")]
    if not books or not m:
        return None
    key = re.match(r"\s*([A-Za-z&]+)", vk or "")
    word = key.group(1).lower() if key else ""
    book = next((b for b in books if len(word) > 3 and (word in (b.get("author") or "").lower() or word in b["title"].lower())), None) or         next((b for b in books if word[:1] and (b.get("author") or b["title"]).lower().startswith(word[:1])), books[0])
    path = data_path(book["pdf_path"])
    off = _printed_offset(path)
    first, last = int(m.group(1)), int(m.group(2) or m.group(1))
    if last < first or last - first > 60:
        last = first
    return book, _best_page(path, first + off, last + off, ctx, None, heading)


def _show_equation(wins, payload):
    """A clicked equation: its source in the lecture slides / lecture notes, or (Shift, or when no lecture source is named) the textbook."""
    note = crud.get_book(int(payload["note"])) if str(payload.get("note", "")).isdigit() else None
    if not note:
        return
    found = None
    ctx = f"{payload.get('ctx', '')}"
    lecture, textbook = _lecture_source(note, payload.get("src", ""), ctx, payload.get("head", "")), _textbook_source(note, payload.get("vk", ""), ctx, payload.get("head", ""))
    found = (textbook or lecture) if payload.get("shift") else (lecture or textbook)
    if not found:
        st.toast("This source is not in the Library, or it names no page." if payload.get("chip") else "No source page is listed for this equation.", icon=":material/info:")
        return
    _open_pdf(wins, found[0], found[1])


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
                f'<div class="lab-tabs" data-w="{",".join(f"{w:g}" for w in _weights(wins))}" style="grid-template-columns: {" ".join(f"minmax(0, {w:g}fr)" for w in _weights(wins))}">{tabs}{plus}</div>',
                unsafe_allow_html=True)


def _full_screen():
    """The note the Note Reader shows, alone and as wide as the screen (like a note opened from a homework helper); Exit Full Screen goes back."""
    st.markdown("<style>.stMainBlockContainer {padding: 0.5rem 1.2rem 0 !important; max-width: none !important;}"
                ".stMainBlockContainer > [data-testid='stVerticalBlock'] {gap: 0.3rem !important;}"
                "[data-testid='stHeader'] {height: 0; min-height: 0; visibility: hidden;}"
                "[class*='st-key-lab_full_html'], [class*='st-key-lab_full_html'] [data-testid='stElementContainer'], "
                "[class*='st-key-lab_full_html'] iframe {height: calc(100vh - 75px) !important; width: 100% !important;}"
                "</style>", unsafe_allow_html=True)
    lab = settings.get_lab()
    courses, course_id = _current_chapter()
    notes = _course_notes(course_id) if courses else []
    book = next((b for b in notes if b["id"] == st.session_state.get("lab_note")), None) or \
        next((b for b in notes if b["id"] == lab.get("notes", {}).get(str(course_id))), None) or (notes[0] if notes else None)
    path = data_path(book["pdf_path"]) if book else None
    head, back = st.columns([8, 1.6], vertical_alignment="center")
    head.markdown(f"<div class='lab-detached-title'>{_esc(book['title']) if book else 'Notes'}</div>", unsafe_allow_html=True)
    if back.button("Exit Full Screen", icon=":material/fullscreen_exit:", key="lab_full_close", width="stretch"):
        st.session_state["lab_full"] = False
        st.rerun()
    if not book or not path.exists():
        st.info("There is no note to show."); return
    text = path.read_text(encoding="utf-8", errors="replace")
    part = next((p for p in outline.parts(text) if p["label"] == lab.get("tabs", {}).get(str(book["id"]))), None)     # the tab the note was left on
    with st.container(key="lab_full_html"):
        from views import quiz_view
        questions = None if 'id="qBox"' in text else quiz_view.book_questions(book)
        components.html(htmlnotes.safe_html(text, part["section"] if part else None, questions=questions, resume=f"full:{book['id']}", esc_exit=True, anchor="full"),
                        height=900, scrolling=True)


def render():
    if st.session_state.get("lab_full"):
        _full_screen()
        return
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
