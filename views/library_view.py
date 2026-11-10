"""Library: PDF books and notes as a cover grid (first page = cover) with a dashed add tile and a page preview."""
import base64
from datetime import date
import html
import hashlib
import re
import shutil
import uuid

import streamlit as st
import streamlit.components.v1 as components

import covers
import htmlnotes
import gradereport
import solcrop
import hwassist
import reader
import crud
import libbackup
import syllabus
import navigation
import pdfmeta
from pdfmeta import guess_lecture, split_lecture, strip_notes_prefix
from database import BASE_DIR, PDF_DIR, data_path, stored_path

COLUMNS = 6
KINDS = ["Textbook", "Lecture Notes", "Notes", "Homework", "Homework Helper", "Homework Solution", "Graded Homework", "Grade Explanation",
         "Practice Exam", "Exam", "Exam Helper", "Exam Solution", "Graded Exam", "Exam Grade Explanation", "Exam Preparation", "Exam Reflection",
         "Syllabus", "Equation Sheet"]
# One tab for each family; inside a tab the files order (and, with Sort: Type, group) by these categories.
HW_GROUP = ("Homework", "Homework Helper", "Homework Solution", "Graded Homework", "Grade Explanation")
EXAM_GROUP = ("Practice Exam", "Exam", "Exam Helper", "Exam Solution", "Graded Exam", "Exam Grade Explanation", "Exam Preparation", "Exam Reflection")
FILTERS = ["Textbook", "Lecture Notes", "Notes", "Homework", "Exam", "Syllabus", "Equation Sheet"]       # the pills after "All"
FILTER_KINDS = {"Homework": HW_GROUP, "Exam": EXAM_GROUP}


def filter_for(kind):
    """The pill a file of this kind appears under (and what an older remembered filter means now)."""
    return "Homework" if kind in HW_GROUP else "Exam" if kind in EXAM_GROUP else kind
HW_KINDS = HW_GROUP          # kinds that carry a homework number
PLURAL = {"Textbook": "Textbooks", "Homework Solution": "Homework Solutions", "Exam": "Exams", "Practice Exam": "Practice Exams", "Exam Preparation": "Exam Preparation", "Exam Reflection": "Exam Reflections", "Homework Helper": "Homework Helpers", "Exam Helper": "Exam Helpers", "Exam Solution": "Exam Solutions", "Syllabus": "Syllabi", "Equation Sheet": "Equation Sheets"}


@st.cache_data(show_spinner=False, max_entries=256)
def _cover_b64(path, mtime):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


@st.cache_data(show_spinner=False, max_entries=48)
def _page_png(path, mtime, page_index, width):
    return covers.render_page(path, page_index, width)


def _cover_url(img):
    """Where the page shows a cover from. Covers are copied under static/covers (served by Streamlit, and kept by the browser), so the Library page
    does not carry about 300 inline images every time it is drawn; without static serving the image is inlined."""
    try:
        if reader.scroll_available():
            dest = BASE_DIR / "static" / "covers" / img.name
            if not dest.exists() or dest.stat().st_mtime < img.stat().st_mtime:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(img, dest)
            return f"/app/static/covers/{img.name}?v={int(img.stat().st_mtime)}"
    except OSError:
        pass
    return f"data:image/jpeg;base64,{_cover_b64(str(img), img.stat().st_mtime)}"


def _cover_html(book):
    """First page of the PDF as the cover; a generated gradient with the title if it can't be rendered."""
    img = covers.ensure_cover(book["id"], data_path(book["pdf_path"]))
    if img:
        url = _cover_url(img)
        return f'<div class="book-cover has-img" style="background-image:url({url});"></div>'
    hue = int(hashlib.md5(book["title"].encode()).hexdigest()[:6], 16) % 360
    title = book["title"].replace("<", "&lt;")
    return (f'<div class="book-cover" style="background: linear-gradient(155deg, hsl({hue},45%,38%), '
            f'hsl({(hue + 40) % 360},50%,24%));"><span>{title}</span></div>')


def detect_course(filename, title=""):
    """Course id guessed from a file name (then the title): 'PHYS_6105 notes.pdf' -> PHYS 6105."""
    courses = crud.list_courses(section=None)
    for text in (filename, title):
        if not text:
            continue
        hits = []
        for c in courses:
            m = re.fullmatch(r"([A-Za-z]+)\s*(\d+)", (c["code"] or "").strip())
            if not m:
                continue
            pat = rf"(?<![A-Za-z]){m.group(1)}[\s_\-.]*{m.group(2)}(?!\d)"
            if re.search(pat, text, re.I):
                hits.append(c)
        if hits:  # longest code wins if several match
            return max(hits, key=lambda c: len(c["code"]))["id"]
        named = [c for c in courses if c["name"] and c["name"] != c["code"] and len(c["name"]) > 5
                 and re.search(rf"(?<![A-Za-z]){re.escape(c['name'])}(?![A-Za-z])", text.replace("_", " "), re.I)]
        if len(named) == 1:
            return named[0]["id"]
    return None


LECTURE_WORDS = re.compile(r"(?<![a-z])(lectures?|lec|slides?)(?![a-z])", re.I)
NOTES_WORDS = re.compile(r"(?<![a-z])(notes?|handouts?|cheat[\s_\-]*sheets?|study[\s_\-]*guides?|"
                         r"summary|summaries|review|annotated|worksheet|recitation)(?![a-z])", re.I)
SHEET_WORDS = re.compile(r"(?<![a-z])(equation|formula)[\s_\-]*sheets?(?![a-z])", re.I)
SYLLABUS_WORDS = re.compile(r"(?<![a-z])(syllab(?:us|i)|course[\s_\-]*(?:information|policies|outline))(?![a-z])", re.I)
PRACTICE_WORDS = re.compile(r"(?<![a-z])(practice|sample|mock|past|old|review)(?![a-z])", re.I)
EXAM_WORDS = re.compile(r"(?<![a-z])(exams?|mid[\s_\-]*terms?|final[\s_\-]*exams?)(?![a-z])", re.I)
HELPER_WORDS = re.compile(r"(?<![a-z])(helpers?|hints?)(?![a-z])", re.I)
GRADE_WORDS = re.compile(r"(?<![a-z])(grades?|explanations?)(?![a-z])", re.I)
SOLUTION_WORDS = re.compile(r"(?<![a-z])(solutions?|soln?s?)(?![a-z])", re.I)
HOMEWORK_WORDS = re.compile(r"(?<![a-z])(homework|hw|problem[\s_\-]*sets?|psets?|assignment)(?![a-z])", re.I)
BOOK_WORDS = re.compile(r"(?<![a-z])(textbook|text[\s_\-]*book|edition|ed\.?\s*\d+|\d+(st|nd|rd|th)[\s_\-]*ed)(?![a-z])", re.I)


def detect_kind(filename, title=""):
    """'Exam', 'Homework', 'Textbook', 'Lecture Notes' or 'Notes' when the file name (then title) says so, else None."""
    for text in (filename, title):
        if not text:
            continue
        text = text.replace("_", " ")
        if SHEET_WORDS.search(text):
            return "Equation Sheet"
        if SYLLABUS_WORDS.search(text):
            return "Syllabus"
        if filename.lower().endswith((".html", ".htm")) and (HELPER_WORDS.search(text) or GRADE_WORDS.search(text)):
            exam = bool(EXAM_WORDS.search(text)) and not HOMEWORK_WORDS.search(text)           # written outside the app, imported as a page
            if HELPER_WORDS.search(text):
                return "Exam Helper" if exam else "Homework Helper"
            return "Exam Grade Explanation" if exam else "Grade Explanation"
        if EXAM_WORDS.search(text) and not HOMEWORK_WORDS.search(text):
            if SOLUTION_WORDS.search(text):
                return "Exam Solution"
            return "Practice Exam" if PRACTICE_WORDS.search(text) else "Exam"
        if HOMEWORK_WORDS.search(text):                       # "hw4 solution.pdf" is the solution, "hw4.pdf" the homework
            return "Homework Solution" if SOLUTION_WORDS.search(text) else "Homework"
        if BOOK_WORDS.search(text):
            return "Textbook"
        if LECTURE_WORDS.search(text):
            return "Lecture Notes"
        if NOTES_WORDS.search(text):
            return "Notes"
    return None


def _course_options():
    return {c["id"]: crud.label(c) for c in crud.list_courses(section=None)}


def _auto(name, value):
    """The session key of a box of the Add File window. The box follows what was detected (from the file or its type) until something is typed in
    it; after that, choosing another file or type leaves what was typed alone."""
    key = f"bk_{name}"
    seen = st.session_state.setdefault("_bk_auto", {})
    if key not in st.session_state or st.session_state[key] == seen.get(key):
        st.session_state[key] = value
    seen[key] = value
    return key


def _reset_add_boxes():
    """A fresh Add File window: nothing typed before is kept."""
    for k in [k for k in st.session_state if str(k).startswith("bk_")] + ["_bk_auto"]:
        st.session_state.pop(k, None)


@st.dialog("Add File", width="large")
def _add_dialog(default_course=None):
    with st.container(key="library_file_box"):
        up = st.file_uploader("File", type=["pdf", "html", "htm"])
    info = {"title": "", "author": "", "edition": "", "year": "", "pages": None, "source": ""}
    if up:
        cache = st.session_state.setdefault("_pdf_info", {})
        if up.file_id not in cache:
            with st.spinner("Reading PDF details..."):
                cache[up.file_id] = (pdfmeta.extract_info if up.name.lower().endswith('.pdf')
                                          else pdfmeta.extract_html_info)(up.getvalue(), up.name)
        info = cache[up.file_id]
        found = [n for n in ("title", "author", "edition", "year") if info[n]]
        st.caption("Detected " + (", ".join(found) if found else "nothing") +
                   f" from {info['source']} - edit anything that looks wrong.")
    kind_guess = detect_kind(up.name, info["title"]) if up else None
    kind = st.segmented_control("Type", KINDS, key=_auto("kind", kind_guess or "Textbook")) or "Textbook"
    if kind_guess:
        st.caption(f"Type detected from the file name: {kind_guess}")
    is_hw = kind in HW_KINDS
    is_notes = kind in ("Lecture Notes", "Notes")
    # Notes: a leading "Lec 3" in the title or file name becomes the Lecture label, not part of the title.
    lec_guess, clean_title = split_lecture(info["title"])
    if not lec_guess and up:
        lec_guess = guess_lecture(up.name.rsplit(".", 1)[0], info["title"])          # "Lec 3", or "Chapter 3" in an html note's name or title
    title = st.text_input("Title", key=_auto("title", crud.fix_course_ids(strip_notes_prefix(clean_title) if is_notes else info["title"])))     # "AE333" -> "AE 333"
    lecture = ""
    if is_hw:                                                        # "hw4.pdf" -> homework number 4, title "HW 4"
        num = (re.search(r"\d+", up.name) or re.search(r"\d+", info["title"] or "")) if up else None
        lecture = st.text_input("Homework Number", key=_auto("hw", num.group() if num else ""), placeholder="4")
        if lecture.strip() and not title.strip().lower().startswith("hw"):
            title = f"HW {lecture.strip()}" + {"Homework Solution": " Solution", "Graded Homework": " Graded", "Homework Helper": " Helper", "Grade Explanation": " Grade Explanation"}.get(kind, "")
    elif is_notes:
        lecture = st.text_input("Lecture", key=_auto("lec", lec_guess), placeholder="3 or 3-4")
    c1, c2, c3 = st.columns([3, 2, 1.2])
    author = c1.text_input("Author", key=_auto("author", info["author"]))
    edition = c2.text_input("Edition", key=_auto("edition", info["edition"]), placeholder="7th Edition")
    # Your own notes default to the current year; a textbook keeps the year found in the file (if any).
    year = c3.text_input("Year", key=_auto("year", str(date.today().year) if is_notes else info["year"]), placeholder="2019")
    courses = _course_options()
    guess = detect_course(up.name, info["title"]) if up else None
    start = guess if guess in courses else (default_course if default_course in courses else None)
    course_ids = st.multiselect("Courses (Optional)", list(courses), format_func=courses.get, key=_auto("course", [start] if start else []))
    if guess:
        st.caption(f"Course detected from the file name: {crud.label(crud.get_course(guess))}")
    if st.button("Add to Library", type="primary", disabled=not (up and title.strip())):
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        ext = ".pdf" if up.name.lower().endswith(".pdf") else ".html"
        dest = PDF_DIR / f"book_{uuid.uuid4().hex[:10]}{ext}"
        dest.write_bytes(up.getvalue())
        new_id = crud.add_book(title.strip(), author.strip(), edition.strip(), stored_path(dest),
                               info["pages"], course_ids, kind, year.strip(), lecture.strip(), orig_name=up.name)
        libbackup.auto()                                           # keeps the backup folder (if one is chosen) up to date
        if kind == "Syllabus" and ext == ".pdf":
            syllabus.auto_build(course_ids, new_id, dest)          # the syllabus section of the course page
        _reset_add_boxes()
        st.rerun()


def _annot_id(book):
    """Homework and exam files can be drawn on (pen, highlighter; saved automatically): the file's id, else None."""
    return book["id"] if book["kind"] in HW_GROUP + EXAM_GROUP and book["pdf_path"].lower().endswith(".pdf") else None


def _default_view(book):
    """Homework and exam files (the problems, solutions, graded papers ...) open as one page wide, scrolling continuously."""
    return "scroll" if book["kind"] in HW_GROUP + EXAM_GROUP else "page"


def _viewer(book):
    """Preview: pages rendered as images, with prev/next, page jump and zoom."""
    if book["kind"] in HW_GROUP + EXAM_GROUP:          # the reading page of a homework or exam: the same margin at the right as at the left
        st.markdown("<style>.block-container {padding-right: 2.5rem !important;}</style>", unsafe_allow_html=True)
    if st.button("← Back"):                      # to the page the file was opened from (course, library ...)
        if not navigation.go_back():
            st.session_state["open_book"] = None
            st.rerun()
    st.header(book["title"])
    path = data_path(book["pdf_path"])
    if not path.exists():
        st.error("The stored PDF file is missing."); return
    if path.suffix.lower() in (".html", ".htm"):
        from views import quiz_view                        # the note's Self-check shows the same questions as the course Quiz tab
        jump = st.session_state.pop("lib_goto", None)
        _handle_link(book)                                 # links of a preparation, reflection ... page to the notes and to the course's other pages
        components.html(htmlnotes.safe_html(path.read_text(encoding="utf-8", errors="replace"), goto=jump, links=True,
                                            questions=quiz_view.book_questions(book), resume=None if jump else "library"),
                        height=900, scrolling=True)
        return
    if book["kind"] in ("Homework", "Exam", "Practice Exam") and book["course_ids"]:     # the homework or exam and the helper side by side
        left, right = st.columns([1, 1], gap="medium")
        helper = _sibling(book, ("Homework Helper",) if book["kind"] == "Homework" else ("Exam Helper",))
        if helper:
            with right:
                _handle_link(book)                       # before the paper is drawn: a click may change its page
        marks = _problem_marks(book, path, st.session_state.get(f"hp{book['id']}_sel")) if helper else []
        with left:
            reader.pdf_reader(path, f"view_{book['id']}", height=820, view=_default_view(book), start=st.session_state.pop(f"view_page_{book['id']}", 1),
                              marks=marks, active=[m["n"] for m in marks if m.get("active")], marks_list=False, annot=_annot_id(book))
        with right:
            if helper:                                   # written outside the app; the automatic hints only when there is none
                _imported_panel(helper, book, marks=True)
            else:
                _homework_helper(book)
        return
    if book["kind"] in ("Graded Homework", "Graded Exam"):      # the paper on the left, why it got this grade on the right
        left, right = st.columns([1, 1], gap="medium")
        sel = st.session_state.get(f"gp{book['id']}_sel")
        explanation = _sibling(book, ("Grade Explanation",) if book["kind"] == "Graded Homework" else ("Exam Grade Explanation",))
        graded = gradereport.load(book["id"])
        if explanation:
            with right:
                _handle_link(book)                       # before the paper is drawn: a click may change its page or its marks
            sel = st.session_state.get(f"gp{book['id']}_sel")
        marks = _grade_marks(book, path, sel)                 # the written page marks the paper too
        with left:
            reader.pdf_reader(path, f"view_{book['id']}", height=820, view=_default_view(book), start=st.session_state.pop(f"view_page_{book['id']}", 1),
                              marks=marks, active=[m["n"] for m in marks if m.get("active")], marks_list=False, annot=_annot_id(book))
        with right:
            if explanation:                              # the grade and the links to the problem and the solution, then the written page
                _grade_panel(book, header_only=True)
                _imported_panel(explanation, book, marks=bool(graded and graded.get("total")), height=700)
            else:                                        # no written page: the automatic panel
                with st.container(height=860, border=False):       # scrolls on its own, like the paper beside it
                    _grade_panel(book)
        return
    reader.pdf_reader(path, f"view_{book['id']}", height=820, view=_default_view(book),
                      start=st.session_state.pop(f"view_page_{book['id']}", 1), annot=_annot_id(book))


def _lecture_note(book, lecture):
    """The course's notes file for a lecture (chapter) number, or None."""
    for b in sorted(crud.list_books(), key=lambda b: b["kind"] != "Notes"):
        if (b["kind"] in ("Notes", "Lecture Notes") and set(b["course_ids"]) & set(book["course_ids"])
                and lecture in re.findall(r"\d+", b.get("lecture") or "")):
            return b
    return None


def _handle_link(book):
    """A link in the written page (a notes section, the helper, the solution) writes 'note:<lecture>:<id>' or 'companion:<what>'
    into a hidden box (see htmlnotes._LINKS); open that file."""
    sink = st.text_input("Page Link", key="lib_link_sink", label_visibility="collapsed")
    if not sink or sink == st.session_state.get("_lib_link_done"):
        return
    st.session_state["_lib_link_done"] = sink
    action, _, rest = sink.split("|")[0].partition(":")
    if action == "note":
        lecture, _, anchor = rest.partition(":")
        note = _lecture_note(book, lecture) if lecture else None
        if note:
            _open_note(note["id"], None if anchor in ("", "top") else anchor)
            st.rerun()
    elif action == "mark" and re.fullmatch(r"[pc]\d+[a-z]?", rest):          # a problem, a part or a comment of the written page
        if book["kind"] in ("Graded Homework", "Graded Exam"):
            data = gradereport.load(book["id"]) or {}
            if rest[0] == "c":
                if not any(c["id"] == int(rest[1:]) for c in data.get("comments") or []):
                    st.rerun()                                              # a comment the grade data does not have
                page = next((c.get("page") for c in data.get("comments") or [] if c["id"] == int(rest[1:])), None)
            else:
                page = next((x.get("page") for x in data.get("problems") or [] if x["n"] == int(rest[1:])), None)
            _select_grade(book["id"], rest, page)
        elif rest[0] == "p":                                                 # a problem or a part of a written helper: show it in the problem file
            st.session_state[f"hp{book['id']}_sel"] = rest
            found = _problem_info(book).get(re.match(r"p(\d+)", rest).group(1))
            part = next((q for q in (found or {}).get("parts") or [] if q["id"] == rest[-1]), None) if rest[-1].isalpha() else None
            if found:
                _go_page(book["id"], (part or found)["page"])
        st.rerun()
    elif action == "doc":                                                    # a link to another page of the course, by its name
        target = _doc_target(book, rest)
        if target:
            _open_file_at(target["id"], 1)
            st.rerun()


def _doc_target(book, text):
    """The Library file that a link named like "Midterm 2 Preparation", "Homework 4 Grades", "Midterm 1 Reflection" or "Homework 5 Helper"
    means, in the course of `book`: the preparation or reflection page itself, the graded paper (it shows the explanation beside it), or
    the problem file (it shows the helper beside it). None if the name says nothing."""
    t = re.sub(r"\s+", " ", text.replace("\u2197", " ")).strip().lower()
    num = re.search(r"(homework|hw|problem set|midterm|exam|quiz|test)\s*#?\s*(\d+)", t)
    key = num.group(2) if num else ("final" if "final" in t else None)
    if not key:
        return None
    homework = bool(re.search(r"homework|\bhw\b|problem set", t))
    if "reflection" in t:
        kinds = ("Exam Reflection",)
    elif "prepar" in t:
        kinds = ("Exam Preparation",)
    elif "helper" in t or "hint" in t:
        kinds = ("Homework",) if homework else ("Exam",)
    elif "grade" in t or "explanation" in t:
        kinds = ("Graded Homework",) if homework else ("Graded Exam",)
    elif "solution" in t:
        kinds = ("Homework Solution",) if homework else ("Exam Solution",)
    elif not homework:
        kinds = ("Exam Preparation",)                    # just "Midterm 2" or "Midterm 2 page": the exam's preparation page
    else:
        return None
    found = [b for b in crud.list_books() if b["kind"] in kinds and set(b["course_ids"]) & set(book["course_ids"]) and _pair_key(b) == key]
    return min(found, key=lambda b: ("practice" in b["title"].lower(), b["id"])) if found else None


def _problem_info(book):
    """{problem number: parsed problem} of a homework or exam file."""
    path = data_path(book["pdf_path"])
    try:
        return {str(x["id"]): x for x in hwassist.parse_problems(str(path), path.stat().st_mtime)}
    except Exception:
        return {}


def _find_text(page, text):
    """The first place a start of this text appears on a PDF page, or None (the start is tried at several lengths)."""
    text = re.sub(r"\s+", " ", text).strip()
    for n in (32, 20, 12):
        hits = page.search_for(text[:n]) if len(text) >= 6 else []
        if hits:
            return hits[0]
    return None


def _problem_marks(book, path, sel):
    """The box to draw on the problem file around the heading of the problem, or the lines of the part, picked in the written helper."""
    m = re.fullmatch(r"p(\d+)([a-z]?)", sel or "")
    found = _problem_info(book).get(m.group(1)) if m else None
    if not found:
        return []
    part = next((q for q in found.get("parts") or [] if q["id"] == m.group(2)), None) if m.group(2) else None
    target = part or found
    sizes = _page_sizes(path, {target["page"]})
    if target["page"] not in sizes:
        return []
    W, H = sizes[target["page"]]
    rect, label = (W * 0.05, H * 0.05, W * 0.95, H * 0.12), found["title"]        # the top of the page when nothing is found
    try:
        import pymupdf
        page = pymupdf.open(path)[target["page"] - 1]
        if part:
            hit = _find_text(page, part["text"])
            if hit:
                later = [h.y0 for q in found["parts"] if q["id"] > part["id"] and q["page"] == part["page"]
                         for h in [_find_text(page, q["text"])] if h and h.y0 > hit.y0]
                lines = min(4, max(1, len(re.sub(r"\s+", " ", part["text"])) // 85 + 1))
                bottom = (min(later) - 2) if later else hit.y0 + 15 * lines
                rect, label = (hit.x0 - 30, hit.y0 - 3, W * 0.95, bottom), f"{found['id']}{part['id']})"
        else:
            hit = _find_text(page, found["title"])
            if hit:
                rect = (W * 0.05, hit.y0 - 5, W * 0.95, hit.y1 + 5)
    except Exception:
        pass
    return [{"n": f"{found['id']}{part['id'] if part else ''}", "label": label, "md": "", "page": target["page"] - 1, "size": (W, H),
             "sentence": False, "active": True, "rect": rect}]


def _imported_panel(doc, book, marks=False, height=860):
    """The helper or grade explanation written outside the app, shown beside the paper; its notes links open your notes."""
    path = data_path(doc["pdf_path"])
    if not path.exists():
        st.error("The stored file is missing."); return
    components.html(htmlnotes.safe_html(path.read_text(encoding="utf-8", errors="replace"), resume=f"doc{doc['id']}", links=True, marks=marks),
                    height=height, scrolling=True)


def _open_file_at(book_id, page):
    """Callback: open another file of the course (the problem file, the solution) at a page."""
    st.session_state["open_book"] = book_id
    st.session_state[f"view_page_{book_id}"] = page
    st.session_state[f"view_{book_id}_page"] = page


def _pair_key(book):
    """What pairs a graded file, a solution, a helper ... with its problem file: the homework or exam number, or "final"."""
    m = re.search(r"\d+", book.get("lecture") or "") or re.search(
        r"(?:homework|hw|problem\s*set|assignment|mid[\s_\-]*term|exam|quiz|test)\s*#?\s*(\d+)", book["title"], re.I) or re.search(r"\d+", book["title"])
    if m:
        return m.group(m.lastindex or 0)
    return "final" if "final" in book["title"].lower() else None


def _sibling(book, kinds):
    """The file of the same course and number as this one: the problem file, the solution, the helper, the graded paper ..."""
    key = _pair_key(book)
    if not key:
        return None
    for b in crud.list_books():
        if (b["id"] != book["id"] and b["kind"] in kinds and set(b["course_ids"]) & set(book["course_ids"]) and _pair_key(b) == key
                and ("practice" in b["title"].lower()) == ("practice" in book["title"].lower())):
            return b
    return None


def _toggle_flag(flag):
    st.session_state[flag] = not st.session_state.get(flag)


def _solution_pages(pr, problems, total):
    """The pages of the solution file that answer one problem: from its start to the page before the next problem's."""
    start = pr.get("solution_page")
    later = sorted(p["solution_page"] for p in problems if p.get("solution_page") and p["solution_page"] > (start or 0))
    end = (later[0] - 1) if later else min(total, (start or 1) + 4)
    return list(range(start, max(start, end) + 1)) if start else []


def _select_grade(book_id, sel, page):
    """Callback: a problem, a rubric line or a comment was clicked: show its page and mark it on the paper."""
    st.session_state[f"gp{book_id}_sel"] = sel
    if page:
        _go_page(book_id, page)


def _page_sizes(path, pages):
    import pymupdf
    try:
        doc = pymupdf.open(path)
        return {pg: (doc[pg - 1].rect.width, doc[pg - 1].rect.height) for pg in pages if 1 <= pg <= doc.page_count}
    except Exception:
        return {}


def _grade_marks(book, path, sel):
    """Boxes to draw on the paper for the clicked problem: its heading, a bar on its other pages, and the places the grader marked.
    The clicked one is emphasised."""
    data = gradereport.load(book["id"])
    if not data or not sel:
        return []
    comments = {c["id"]: c for c in data.get("comments") or []}
    problems = {pr["n"]: pr for pr in data.get("problems") or []}
    if sel.startswith("c") and int(sel[1:]) in comments:
        pn = comments[int(sel[1:])].get("problem")
    else:
        pn = int(sel[1:]) if sel[1:].isdigit() else None
    pr = problems.get(pn)
    sizes = _page_sizes(path, {c.get("page") for c in comments.values() if c.get("page")} | set((pr or {}).get("pages") or []))
    marks = []
    if pr:
        for pg in pr.get("pages") or []:
            if pg not in sizes:
                continue
            W, H = sizes[pg]
            first = pg == pr.get("page")
            marks.append({"n": f"{pn}", "label": pr["title"] + ("" if first else " (continued)"), "md": "", "page": pg - 1,
                          "size": (W, H), "sentence": not first, "active": sel == f"p{pn}",
                          "rect": (W * 0.05, H * 0.05, W * 0.95, H * 0.17) if first else (6, 8, 22, H - 8)})
    for c in comments.values():
        if (pr and c.get("problem") != pn) or not c.get("pos") or c.get("page") not in sizes:
            continue
        if not pr and sel != f"c{c['id']}":
            continue
        W, H = sizes[c["page"]]
        x, y = c["pos"]
        marks.append({"n": f"{c['id']}", "label": c["text"][:70], "md": "", "page": c["page"] - 1, "size": (W, H), "sentence": True,
                      "active": sel == f"c{c['id']}", "rect": (x - 20, y - 14, x + 20, y + 14)})
    return marks


def _exam_problems(book, exam_file, solution, analysis):
    """Problem cards for a graded exam without per-problem marks: notes sections, and on request the solution pages."""
    sol_pages = {}
    if solution:
        sol_path = data_path(solution["pdf_path"])
        try:
            found = hwassist.parse_problems(str(sol_path), sol_path.stat().st_mtime)
        except Exception:
            found = []
        starts = {str(x["id"]): x["page"] for x in found}
        order = sorted(starts.values())
        total = solution.get("total_pages") or (max(order) if order else 1)
        for pid, start in starts.items():
            later = [x for x in order if x > start]
            sol_pages[pid] = list(range(start, (later[0] - 1 if later else total) + 1))
    for pid, a in analysis.items():
        with st.container(border=True, key=f"gp{book['id']}_x{pid}"):
            st.markdown(f"**{pid}. {hwassist.tex(hwassist.clean(a['title']))}**")
            if a.get("tags"):
                _tag_buttons(a["tags"], f"gp{book['id']}_x{pid}")
            if solution and sol_pages.get(pid):
                flag = f"gp{book['id']}_x{pid}_open"
                opened = st.session_state.get(flag)
                st.button("Hide Solution" if opened else "Show Solution", key=f"{flag}_btn", icon=":material/fact_check:",
                          on_click=_toggle_flag, args=(flag,), help="the solution's pages for this problem")
                if opened:
                    sol_path = data_path(solution["pdf_path"])
                    for pg in sol_pages[pid]:
                        st.image(reader.page_image(sol_path, sol_path.stat().st_mtime, pg - 1, 1100), caption=f"Solution, page {pg}")


def _grade_panel(book, header_only=False):
    """Beside a graded file: the grade, the rubric of each problem with the points lost, and the grader's comments. Clicking a
    problem, a rubric line or a comment shows its page and marks it on the paper. Canvas-only grades show what Canvas gave.
    `header_only`: just the title, the links to the problem and the solution, and the grade (above a written explanation)."""
    st.subheader("Grade Explanation")
    data = gradereport.load(book["id"])
    exam = book["kind"] == "Graded Exam"
    problem_file = _sibling(book, ("Exam",) if exam else ("Homework",))
    solution = _sibling(book, ("Exam Solution",) if exam else ("Homework Solution",))
    cols = st.columns(2)
    if problem_file:
        cols[0].button("Open Homework" if not exam else "Open Exam", key=f"gp{book['id']}_problem", icon=":material/description:",
                       on_click=_open_file_at, args=(problem_file["id"], 1), help="open the problem file")
    if solution:
        cols[1].button("Open Solution", key=f"gp{book['id']}_solution", icon=":material/task_alt:", on_click=_open_file_at,
                       args=(solution["id"], 1), help="open the solution file")
    if not data or not data.get("total"):
        st.caption("Not graded yet.")
        return
    got, of = data["total"]
    st.markdown(f"### {got:g} / {of:g} ({got / of:.0%})")
    if header_only:
        return
    analysis = {}
    if problem_file and problem_file["course_ids"]:           # which sections of the course notes each problem draws on
        try:
            analysis = {str(a["id"]): a for a in hwassist.analyze(problem_file, crud.get_course(problem_file["course_ids"][0]), crud.list_books())}
        except Exception:
            analysis = {}
    st.caption(f"Source: {data['source']}. Click a problem, a line or a comment to see it marked on your paper.")
    for text in data.get("general") or []:
        st.markdown(f":red[{text}]")
    problems = data.get("problems") or []
    comments = data.get("comments") or []
    by_id = {c["id"]: c for c in comments}
    if not problems and not comments and not data.get("general"):
        st.caption("Full marks." if got >= of else "Canvas shows only the total for this one, with no comments.")
    for pr in problems:
        cost = pr["max"] - pr["score"]
        with st.container(border=True, key=f"gp{book['id']}_p{pr['n']}"):
            head, sol = st.columns([4, 2], vertical_alignment="center")
            with head:
                st.button(pr["title"], key=f"gpi_{book['id']}_p{pr['n']}", type="tertiary", on_click=_select_grade,
                          args=(book["id"], f"p{pr['n']}", pr.get("page")), help="show this problem on your paper")
                st.markdown((f":red[**{pr['score']:g} / {pr['max']:g}**]" if cost > 0 else f":green[**{pr['score']:g} / {pr['max']:g}**]"))
            if pr.get("solution_page") and solution:
                sol.button(f"Solution p. {pr['solution_page']}", key=f"gp{book['id']}_p{pr['n']}_sol", type="tertiary",
                           on_click=_open_file_at, args=(solution["id"], pr["solution_page"]), help="open this problem in the solution")
            tagged = analysis.get(str(pr["n"]))
            if tagged and tagged.get("tags"):                  # the notes sections this problem draws on
                _tag_buttons(tagged["tags"], f"gp{book['id']}_p{pr['n']}")
            if tagged and tagged.get("examples"):
                _example_buttons(tagged["examples"], f"gp{book['id']}_p{pr['n']}")
            for k, it in enumerate(pr["items"]):
                note = by_id.get(it.get("comment"))
                label = (":red[" + it["text"] + "]") if it["lost"] else it["text"]
                if note and note.get("page"):                # a line the grader commented on: go to where it was marked
                    target = (f"c{note['id']}", note["page"])
                else:                                        # otherwise the problem's own page
                    target = (f"p{pr['n']}", pr.get("page"))
                st.button(label, key=f"gpi_{book['id']}_p{pr['n']}_{k}", type="tertiary", on_click=_select_grade,
                          args=(book["id"], target[0], target[1]), help="show this on your paper")
                if note:
                    st.markdown(f"> **Grader:** {note['text']}")
                part = re.match(r"(?:[\d.]+ pts? )?([a-e])\)", it["text"])
                if it["lost"] and part and tagged:             # a lost part: the section of the notes for that part
                    sub = next((x for x in tagged.get("parts") or [] if x["id"] == part.group(1) and x.get("tags")), None)
                    if sub and sub["tags"][:1] != (tagged.get("tags") or [])[:1]:
                        _tag_buttons(sub["tags"][:1], f"gp{book['id']}_p{pr['n']}_{k}")
            feedback = [c for c in comments if c.get("problem") == pr["n"]]
            if solution and pr.get("solution_page") and (cost > 0 or feedback):       # the corrected answer, from the solution
                flag = f"gp{book['id']}_p{pr['n']}_open"
                opened = st.session_state.get(flag)
                st.button("Hide Corrected Answer" if opened else "Show Corrected Answer", key=f"{flag}_btn", icon=":material/fact_check:",
                          on_click=_toggle_flag, args=(flag,), help="the solution's answer to this problem, with the grader's comments")
                if opened:
                    sol_path = data_path(solution["pdf_path"])
                    mtime = sol_path.stat().st_mtime
                    pages = tuple(_solution_pages(pr, problems, solution.get("total_pages") or 1))
                    wanted = [it for it in pr["items"] if it["lost"] or it.get("comment")] or [None]
                    shown = set()
                    for it in wanted:                          # the exact part of the solution behind each lost or commented line
                        text = it["text"] if it else pr["title"]
                        part = re.match(r"(?:[\d.]+ pts? )?([a-e])\)", text)
                        target = part.group(1) if part else ("implications" if "implication" in text.lower() else "analysis")
                        if target in shown:
                            continue
                        shown.add(target)
                        label = {"implications": "Implications", "analysis": "Solution"}.get(target, f"Part {target})")
                        st.markdown(f"**{label}** in the solution" + (f" · {text}" if it else ""))
                        note = by_id.get(it.get("comment")) if it else None
                        if note:
                            st.markdown(f"> **Grader:** {note['text']}")
                        found = solcrop.crops(str(sol_path), mtime, pages, target)
                        for pg, png in found:
                            st.image(png, caption=f"Solution, page {pg}")
                        if not found:
                            st.caption("This part could not be cut out of the solution file.")
                            st.button(f"Open Solution p. {pr['solution_page']}", key=f"gp{book['id']}_p{pr['n']}_{target}_open", type="tertiary",
                                      on_click=_open_file_at, args=(solution["id"], pr["solution_page"]))
    if exam and not problems and analysis:                 # an exam with only its total: each problem, its notes and its solution
        st.markdown("**Problems**")
        st.caption("Canvas gives only the total for this exam. Each problem below links to the notes it draws on and, when the "
                   "solution file is in the Library, shows the solution.")
        _exam_problems(book, problem_file, solution, analysis)
    for note in comments:                                  # Canvas comments, and report comments not tied to a rubric line
        if problems and any(it.get("comment") == note["id"] for pr in problems for it in pr["items"]):
            continue
        st.button(f"Page {note['page']}: {note['text']}" if note.get("page") else note["text"], key=f"gpi_{book['id']}_c{note['id']}",
                  type="tertiary", on_click=_select_grade, args=(book["id"], f"c{note['id']}", note.get("page")),
                  help="show where the grader marked this")


def _open_note(note_id, section_id):
    """Callback: open a note of the course at a section."""
    st.session_state["open_book"] = note_id
    st.session_state["lib_goto"] = section_id


def _go_page(book_id, page):
    st.session_state[f"view_{book_id}_page"] = page
    reader._bump(f"view_{book_id}")


def _tag_buttons(tags, key):
    """One button per matching note section: opens that note at the section."""
    for i, (label, note_id, sec_id) in enumerate(tags[:2]):
        st.button(label, key=f"{key}_note_{i}", type="tertiary", icon=":material/menu_book:", on_click=_open_note,
                  args=(note_id, sec_id), help="open this note at that section")


def _example_buttons(tags, key):
    """One button per worked example of the notes that looks like this problem: opens that example, unfolded."""
    for i, (label, note_id, ex_id) in enumerate(tags[:2]):
        st.button(label, key=f"{key}_ex_{i}", type="tertiary", icon=":material/calculate:", on_click=_open_note,
                  args=(note_id, ex_id), help="open a similar worked example in the notes")


def _homework_helper(book):
    """For each problem and sub-problem of a homework or an exam: the note section it draws on, and a hint built from that section."""
    exam = book["kind"] in ("Exam", "Practice Exam")
    course = crud.get_course(book["course_ids"][0])
    books = crud.list_books()
    try:
        problems = hwassist.analyze(book, course, books)
    except Exception:
        problems = []
    st.subheader("Exam Helper" if exam else "Homework Helper")
    solution = _sibling(book, ("Exam Solution",) if exam else ("Homework Solution",))
    if solution:
        st.button("Open Solution", key=f"hw{book['id']}_solution", icon=":material/task_alt:", on_click=_open_note,
                  args=(solution["id"], None), help="open the solution file of this homework")
    if not problems:
        st.caption("No numbered problems were found in this file.")
        return
    st.caption("Each problem is matched to the section of your course notes that it draws on. The light bulb gives a hint built "
               "from that section. The match is automatic, so check the section before relying on it.")
    for pr in problems:
        key = f"hw{book['id']}_{pr['id']}"
        with st.container(border=True, key=f"{key}_card"):
            head, page, bulb = st.columns([6, 1.5, 1], vertical_alignment="center")
            head.markdown(f"**{pr['id']}.** {hwassist.tex(hwassist.clean(pr['title']))}")
            page.button(f"Page {pr['page']}", key=f"{key}_page", type="tertiary", on_click=_go_page, args=(book["id"], pr["page"]))
            if pr["hint"]:
                with bulb.popover("", icon=":material/lightbulb:", help="hint for this problem"):
                    st.markdown(pr["hint"])
            _tag_buttons(pr["tags"], key)
            _example_buttons(pr.get("examples") or [], key)
            for part in pr["parts"]:
                pkey = f"{key}{part['id']}"
                txt, pbulb = st.columns([8, 1], vertical_alignment="center")
                txt.markdown(f"**{part['id']})** {hwassist.tex(hwassist.clean(part['text']), limit=170)}")
                if part["hint"]:
                    with pbulb.popover("", icon=":material/lightbulb:", help="hint for this part"):
                        st.markdown(part["hint"])
                if part["tags"] and part["tags"][:1] != pr["tags"][:1]:
                    _tag_buttons(part["tags"][:1], pkey)
                if part.get("examples") and part["examples"][:1] != (pr.get("examples") or [])[:1]:
                    _example_buttons(part["examples"][:1], pkey)


@st.dialog("Edit File", width="large")
def _edit_dialog(book):
    st.caption(f"Stored File: {book['pdf_path']}")
    kind = st.segmented_control("Type", KINDS, default=book["kind"] if book["kind"] in KINDS else "Textbook",
                                key=f"ek_{book['id']}") or book["kind"]
    title = st.text_input("Title", value=book["title"], key=f"et_{book['id']}")
    lecture = ""
    if kind in ("Lecture Notes", "Notes") + HW_KINDS:
        hw = kind in HW_KINDS
        lecture = st.text_input("Homework Number" if hw else "Lecture", value=book.get("lecture") or "",
                                key=f"el_{book['id']}", placeholder="4" if hw else "3 or 3-4")
    c1, c2, c3 = st.columns([3, 2, 1.2])
    author = c1.text_input("Author", value=book["author"] or "", key=f"ea_{book['id']}")
    edition = c2.text_input("Edition", value=book["edition"] or "", key=f"ee_{book['id']}")
    year = c3.text_input("Year", value=book.get("year") or "", key=f"ey_{book['id']}")
    courses = _course_options()
    course_ids = st.multiselect("Courses (Optional)", list(courses),
                                default=[i for i in book["course_ids"] if i in courses],
                                format_func=courses.get, key=f"ec_{book['id']}")

    a, b, _ = st.columns([1, 1.4, 8])
    if a.button("Save", type="primary", key=f"save_book_{book['id']}"):
        crud.update_book(book["id"], title.strip() or book["title"], author.strip(), edition.strip(), kind,
                         course_ids, year.strip(), lecture.strip())
        if kind == "Syllabus" and book["pdf_path"].lower().endswith(".pdf"):
            syllabus.auto_build(course_ids, book["id"], data_path(book["pdf_path"]))
        st.rerun()
    if b.button("Preview", key=f"open_book_{book['id']}"):
        st.session_state["open_book"] = book["id"]
        st.rerun()

    st.divider()
    confirm = f"confirm_remove_{book['id']}"
    if st.button("Remove from Library", key=f"del_book_{book['id']}"):
        st.session_state[confirm] = True
    if st.session_state.get(confirm):
        st.warning("This also deletes the stored copy in data/pdfs. Your original file is not touched.")
        if st.button("Yes, Remove It", type="primary", key=f"del_yes_{book['id']}"):
            p = data_path(book["pdf_path"])
            crud.delete_book(book["id"])
            covers.remove_cover(book["id"])
            if p.exists():
                p.unlink()
            st.session_state[confirm] = False
            st.rerun()


def _book_card(book, courses):
    """One card as plain HTML (a grid of these is a single element, so the page stays light with many files)."""
    linked = [courses[i] for i in book["course_ids"] if i in courses]
    tag = "".join(f'<span class="book-badge tag" style="background:{crud.course_color(c)};'
                  f'border-color:{crud.course_color(c)}">{html.escape(c["code"])}</span>' for c in linked if c["code"])
    states = list(dict.fromkeys(crud.course_status(c) for c in linked))     # one label per distinct status
    lec = (f'<span class="book-badge meta">{"HW" if book["kind"] in HW_KINDS else "Lec"} {html.escape(book["lecture"])}</span>'
           if book.get("lecture") else "")
    status = "".join(f'<span class="book-badge status {s.lower().replace("-", "")}">{s}</span>' for s in states)
    chips = "".join(f'<span class="book-badge meta">{html.escape(x)}</span>'
                    for x in (book["edition"], book.get("year")) if x)   # edition and year as separate labels
    author = f'<div class="lib-author">{html.escape(book["author"])}</div>' if book["author"] else ""
    return (f'<div class="lib-card"><div class="lib-cover" data-lib-act="open:{book["id"]}">{_cover_html(book)}</div>'
            f'<div class="book-badges"><span class="book-badge">{html.escape(book["kind"])}</span>{lec}{tag}{status}</div>'
            f'<div class="lib-name-row"><strong>{html.escape(book["title"])}</strong>'
            f'<span class="lib-menu" data-lib-act="edit:{book["id"]}">...</span></div>'
            f'{"<div class=book-badges>" + chips + "</div>" if chips else ""}{author}</div>')


SORTS = ["Default", "Course", "Title", "Type", "Date Added"]


def _course_order(book):
    """Order inside a course: notes in lecture-number order, then other notes, then textbooks (each by title); homework and exam files
    by category (homework, solution, graded; practice exam, exam, graded exam) and then by number."""
    numbers = tuple(int(n) for n in re.findall(r"\d+", book.get("lecture") or ""))
    by_title = tuple(int(n) for n in re.findall(r"\d+", book["title"]))
    rank = {"Homework": 1.50, "Homework Helper": 1.52, "Homework Solution": 1.55, "Graded Homework": 1.60, "Grade Explanation": 1.62, "Practice Exam": 1.70,
            "Exam Preparation": 1.72, "Exam": 1.75, "Exam Helper": 1.76, "Exam Solution": 1.78, "Graded Exam": 1.80, "Exam Grade Explanation": 1.81, "Exam Reflection": 1.82}
    if book["kind"] in HW_GROUP:
        return (rank[book["kind"]], numbers, book["title"].lower())
    if book["kind"] in EXAM_GROUP:
        return (rank[book["kind"]], by_title, book["title"].lower())
    if book["kind"] == "Syllabus":
        return (-1, (), book["title"].lower())
    if book["kind"] in ("Lecture Notes", "Notes"):
        return (0, numbers, "") if numbers else (1, (), book["title"].lower())
    return (2, (), book["title"].lower())


def _sorted_groups(books, sort_by):
    """[(heading, books, course_id)] - one unlabeled group for flat sorts, headed groups for Course and Type."""
    if sort_by == "Title":
        return [("", sorted(books, key=lambda b: b["title"].lower()), None)]
    if sort_by == "Date Added":
        return [("", sorted(books, key=lambda b: (b["added_at"] or "", b["id"]), reverse=True), None)]
    if sort_by == "Type":
        groups = {}
        for b in sorted(books, key=lambda b: (KINDS.index(b["kind"]) if b["kind"] in KINDS else 99, b["title"].lower())):
            groups.setdefault(PLURAL.get(b["kind"], b["kind"]), []).append(b)
        return [(heading, items, None) for heading, items in groups.items()]
    if sort_by == "Course":
        # Courses in menu order (Active, Self-Study, Completed); files without a course go last.
        courses = [c for s in crud.STATUSES for c in crud.courses_by_status(s)]
        rank = {c["id"]: i for i, c in enumerate(courses)}
        groups = []
        for c in courses:    # a file linked to several courses shows up under each of them
            items = sorted((b for b in books if c["id"] in b["course_ids"]), key=_course_order)
            if items:
                groups.append((crud.label(c), items, c["id"]))
        loose = sorted((b for b in books if not any(i in rank for i in b["course_ids"])), key=_course_order)
        if loose:
            groups.append(("No Course", loose, None))
        return groups
    return [("", books, None)]


def _tile_grid(tiles, has_books, courses, default_course=None):
    cells = []
    for tile in tiles:
        if tile == "add":
            tip = ' title="click, or drop a pdf or html file here, to add it"'
            cells.append(f'<div class="lib-card"><div class="lib-add" data-lib-act="add:{default_course or 0}"{tip}>+</div></div>')
        else:
            cells.append(_book_card(tile, courses))
    st.markdown(f'<div class="lib-grid">{"".join(cells)}</div>', unsafe_allow_html=True)


def _handle_click():
    """A click on a card writes 'action:id|stamp' into a hidden box (see the script in app.py); act on it once."""
    sink = st.text_input("Library Click", key="lib_sink", label_visibility="collapsed")
    if not sink or sink == st.session_state.get("_lib_sink_done"):
        return
    st.session_state["_lib_sink_done"] = sink
    action, _, rest = sink.split("|")[0].partition(":")
    try:
        ident = int(rest)
    except ValueError:
        return
    if action == "open" and crud.get_book(ident):
        st.session_state["open_book"] = ident
        st.rerun()
    elif action == "edit" and crud.get_book(ident):
        _edit_dialog(crud.get_book(ident))
    elif action == "add":
        _reset_add_boxes()
        _add_dialog(ident or None)


def render():
    st.session_state.setdefault("open_book", None)
    open_book = crud.get_book(st.session_state["open_book"]) if st.session_state["open_book"] else None
    if open_book:
        _viewer(open_book); return

    all_books = crud.list_books()
    courses = {c["id"]: c for c in crud.list_courses(section=None)}
    _handle_click()
    st.markdown("<h1 class='lib-title'>Library</h1>", unsafe_allow_html=True)
    # The filter and the sort are remembered apart from their widgets (a widget's value is dropped while a file is open), so
    # Back from a homework or a note returns to the same list, for example the Homework filter.
    options = ["All"] + FILTERS
    kept = st.session_state.get("_library_filter_kept", "All")
    kept = kept if kept in options else filter_for(kept) if filter_for(kept) in options else "All"       # an older single-kind filter
    st.session_state.setdefault("library_filter", kept)
    if st.session_state.get("library_filter") not in options:
        st.session_state["library_filter"] = kept
    counts = {"All": len(all_books), **{f: sum(b["kind"] in FILTER_KINDS.get(f, (f,)) for b in all_books) for f in FILTERS}}
    f1, f2 = st.columns([6, 1], vertical_alignment="center")
    with f1:
        choice = st.segmented_control("Show", options, key="library_filter", label_visibility="collapsed",
                                      format_func=lambda o: f"{PLURAL.get(o, o)} ({counts[o]})") or "All"
    st.session_state["_library_filter_kept"] = choice
    st.session_state.setdefault("library_sort", st.session_state.get("_library_sort_kept", "Course"))   # by course unless you pick another
    with f2, st.container(key="lib_sort_box"):                              # narrow, at the right edge of the page
        sort_by = st.selectbox("Sort by", SORTS, key="library_sort", label_visibility="collapsed",
                               format_func=lambda s: f"Sort: {s}")
    st.session_state["_library_sort_kept"] = sort_by
    books = all_books if choice == "All" else [b for b in all_books if b["kind"] in FILTER_KINDS.get(choice, (choice,))]
    st.caption(f"{len(books)} {'Title' if len(books) == 1 else 'Titles'}")

    # Books fill rows of six. The dashed "+" add tile follows the last book; when sorted by course, every
    # course group ends with its own "+" tile that adds a file straight into that course.
    groups = _sorted_groups(books, sort_by) or [("", [], None)]
    for i, (title, items, course_id) in enumerate(groups):
        if title:
            st.markdown(f"#### {title} ({len(items)})")
        last = i == len(groups) - 1
        _tile_grid(list(items) + (["add"] if last or sort_by == "Course" else []), bool(all_books),
                   courses, course_id)
