"""Library: PDF books and notes as a cover grid (first page = cover) with a dashed add tile and a page preview."""
import base64
from datetime import date
import html
import hashlib
import re
import uuid

import streamlit as st
import streamlit.components.v1 as components

import covers
import htmlnotes
import gradereport
import hwassist
import reader
import crud
import navigation
import pdfmeta
from pdfmeta import split_lecture, strip_notes_prefix
from database import BASE_DIR, PDF_DIR

COLUMNS = 6
KINDS = ["Textbook", "Lecture Notes", "Notes", "Homework", "Homework Solution", "Exam", "Graded Homework", "Graded Exam", "Syllabus"]
HW_KINDS = ("Homework", "Homework Solution", "Graded Homework")          # kinds that carry a homework number
PLURAL = {"Textbook": "Textbooks", "Homework Solution": "Homework Solutions", "Exam": "Exams", "Syllabus": "Syllabi"}


@st.cache_data(show_spinner=False, max_entries=256)
def _cover_b64(path, mtime):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


@st.cache_data(show_spinner=False, max_entries=48)
def _page_png(path, mtime, page_index, width):
    return covers.render_page(path, page_index, width)


def _cover_html(book):
    """First page of the PDF as the cover; a generated gradient with the title if it can't be rendered."""
    img = covers.ensure_cover(book["id"], BASE_DIR / book["pdf_path"])
    if img:
        b64 = _cover_b64(str(img), img.stat().st_mtime)
        return f'<div class="book-cover has-img" style="background-image:url(data:image/jpeg;base64,{b64});"></div>'
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
SYLLABUS_WORDS = re.compile(r"(?<![a-z])(syllab(?:us|i)|course[\s_\-]*(?:information|policies|outline))(?![a-z])", re.I)
EXAM_WORDS = re.compile(r"(?<![a-z])(exams?|mid[\s_\-]*terms?|final[\s_\-]*exams?)(?![a-z])", re.I)
SOLUTION_WORDS = re.compile(r"(?<![a-z])(solutions?|soln?s?)(?![a-z])", re.I)
HOMEWORK_WORDS = re.compile(r"(?<![a-z])(homework|hw|problem[\s_\-]*sets?|psets?|assignment)(?![a-z])", re.I)
BOOK_WORDS = re.compile(r"(?<![a-z])(textbook|text[\s_\-]*book|edition|ed\.?\s*\d+|\d+(st|nd|rd|th)[\s_\-]*ed)(?![a-z])", re.I)


def detect_kind(filename, title=""):
    """'Exam', 'Homework', 'Textbook', 'Lecture Notes' or 'Notes' when the file name (then title) says so, else None."""
    for text in (filename, title):
        if not text:
            continue
        text = text.replace("_", " ")
        if SYLLABUS_WORDS.search(text):
            return "Syllabus"
        if EXAM_WORDS.search(text) and not HOMEWORK_WORDS.search(text):
            return "Exam"
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
    k = up.file_id if up else "none"  # reset the fields whenever a different file is chosen
    kind_guess = detect_kind(up.name, info["title"]) if up else None
    kind = st.segmented_control("Type", KINDS, default=kind_guess or "Textbook", key=f"bk_kind_{k}") or "Textbook"
    if kind_guess:
        st.caption(f"Type detected from the file name: {kind_guess}")
    is_hw = kind in HW_KINDS
    is_notes = kind in ("Lecture Notes", "Notes")
    # Notes: a leading "Lec 3" in the title or file name becomes the Lecture label, not part of the title.
    lec_guess, clean_title = split_lecture(info["title"])
    if not lec_guess and up:
        lec_guess = split_lecture(up.name.rsplit(".", 1)[0].replace("_", " "))[0]
    title = st.text_input("Title", value=strip_notes_prefix(clean_title) if is_notes else info["title"],
                          key=f"bk_title_{k}_{int(is_notes)}")
    lecture = ""
    if is_hw:                                                        # "hw4.pdf" -> homework number 4, title "HW 4"
        num = (re.search(r"\d+", up.name) or re.search(r"\d+", info["title"] or "")) if up else None
        lecture = st.text_input("Homework Number", value=num.group() if num else "", key=f"bk_hw_{k}", placeholder="4")
        if lecture.strip() and not title.strip().lower().startswith("hw"):
            title = f"HW {lecture.strip()}" + {"Homework Solution": " Solution", "Graded Homework": " Graded"}.get(kind, "")
    elif is_notes:
        lecture = st.text_input("Lecture", value=lec_guess, key=f"bk_lec_{k}", placeholder="3 or 3-4")
    c1, c2, c3 = st.columns([3, 2, 1.2])
    author = c1.text_input("Author", value=info["author"], key=f"bk_author_{k}")
    edition = c2.text_input("Edition", value=info["edition"], key=f"bk_edition_{k}", placeholder="7th Edition")
    # Your own notes default to the current year; a textbook keeps the year found in the file (if any).
    year = c3.text_input("Year", value=str(date.today().year) if is_notes else info["year"],
                         key=f"bk_year_{k}_{int(is_notes)}", placeholder="2019")
    courses = _course_options()
    guess = detect_course(up.name, info["title"]) if up else None
    start = guess if guess in courses else (default_course if default_course in courses else None)
    course_ids = st.multiselect("Courses (Optional)", list(courses), default=[start] if start else [],
                                format_func=courses.get, key=f"bk_course_{k}")
    if guess:
        st.caption(f"Course detected from the file name: {crud.label(crud.get_course(guess))}")
    if st.button("Add to Library", type="primary", disabled=not (up and title.strip())):
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        ext = ".pdf" if up.name.lower().endswith(".pdf") else ".html"
        dest = PDF_DIR / f"book_{uuid.uuid4().hex[:10]}{ext}"
        dest.write_bytes(up.getvalue())
        crud.add_book(title.strip(), author.strip(), edition.strip(), str(dest.relative_to(BASE_DIR)),
                      info["pages"], course_ids, kind, year.strip(), lecture.strip())
        st.rerun()


def _viewer(book):
    """Preview: pages rendered as images, with prev/next, page jump and zoom."""
    if st.button("← Back"):                      # to the page the file was opened from (course, library ...)
        if not navigation.go_back():
            st.session_state["open_book"] = None
            st.rerun()
    st.header(book["title"])
    path = BASE_DIR / book["pdf_path"]
    if not path.exists():
        st.error("The stored PDF file is missing."); return
    if path.suffix.lower() in (".html", ".htm"):
        from views import quiz_view                        # the note's Self-check shows the same questions as the course Quiz tab
        components.html(htmlnotes.safe_html(path.read_text(encoding="utf-8", errors="replace"),
                                            goto=st.session_state.pop("lib_goto", None),
                                            questions=quiz_view.book_questions(book)), height=900, scrolling=True)
        return
    if book["kind"] == "Homework" and book["course_ids"]:     # the homework and the helper side by side
        left, right = st.columns([3, 2], gap="medium")
        with left:
            reader.pdf_reader(path, f"view_{book['id']}", height=820, start=st.session_state.pop(f"view_page_{book['id']}", 1))
        with right:
            _homework_helper(book)
        return
    if book["kind"] in ("Graded Homework", "Graded Exam"):      # the paper on the left, why it got this grade on the right
        left, right = st.columns([3, 2], gap="medium")
        with left:
            reader.pdf_reader(path, f"view_{book['id']}", height=820, start=st.session_state.pop(f"view_page_{book['id']}", 1))
        with right:
            _grade_panel(book)
        return
    reader.pdf_reader(path, f"view_{book['id']}", height=820,
                      start=st.session_state.pop(f"view_page_{book['id']}", 1))


def _open_file_at(book_id, page):
    """Callback: open another file of the course (the problem file, the solution) at a page."""
    st.session_state["open_book"] = book_id
    st.session_state[f"view_page_{book_id}"] = page
    st.session_state[f"view_{book_id}_page"] = page


def _sibling(book, kinds):
    """The file of the same course and number as this graded file: the problem file or the solution."""
    number = re.search(r"\d+", book.get("lecture") or book["title"])
    if not number:
        return None
    for b in crud.list_books():
        n = re.search(r"\d+", b.get("lecture") or b["title"])
        if b["kind"] in kinds and set(b["course_ids"]) & set(book["course_ids"]) and n and n.group() == number.group():
            return b
    return None


def _grade_panel(book):
    """Beside a graded file: the grade, the rubric of each problem with the points lost, and the grader's comments (with the page
    each one belongs to). Canvas-only grades show what Canvas gave."""
    st.subheader("Grade Explanation")
    data = gradereport.load(book["id"])
    exam = book["kind"] == "Graded Exam"
    problem_file = _sibling(book, ("Exam",) if exam else ("Homework",))
    solution = None if exam else _sibling(book, ("Homework Solution",))
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
    st.caption(f"Source: {data['source']}.")
    for text in data.get("general") or []:
        st.markdown(f":red[{text}]")
    problems = data.get("problems") or []
    comments = data.get("comments") or []
    if not problems and not comments and not data.get("general"):
        st.caption("Full marks." if got >= of else "Canvas shows only the total for this one, with no comments.")
    for pr in problems:
        cost = pr["max"] - pr["score"]
        with st.container(border=True, key=f"gp{book['id']}_p{pr['n']}"):
            head, page, sol = st.columns([4, 1.4, 1.8], vertical_alignment="center")
            head.markdown(f"**{pr['title']}**  " + (f":red[**{pr['score']:g} / {pr['max']:g}**]" if cost > 0
                                                     else f":green[**{pr['score']:g} / {pr['max']:g}**]"))
            if pr.get("page"):
                page.button(f"Page {pr['page']}", key=f"gp{book['id']}_p{pr['n']}_page", type="tertiary", on_click=_go_page,
                            args=(book["id"], pr["page"]), help="show this problem in your paper")
            if pr.get("solution_page") and solution:
                sol.button(f"Solution p. {pr['solution_page']}", key=f"gp{book['id']}_p{pr['n']}_sol", type="tertiary",
                           on_click=_open_file_at, args=(solution["id"], pr["solution_page"]), help="open this problem in the solution")
            for it in pr["items"]:
                st.markdown((":red[" + it["text"] + "]") if it["lost"] else it["text"])
                note = next((c for c in comments if c["id"] == it.get("comment")), None)
                if note:
                    t, b = st.columns([5, 1.4], vertical_alignment="center")
                    t.markdown(f"> **Grader:** {note['text']}")
                    if note.get("page"):
                        b.button(f"Page {note['page']}", key=f"gp{book['id']}_c{note['id']}", type="tertiary", on_click=_go_page,
                                 args=(book["id"], note["page"]), help="show where the grader marked this")
    for note in comments:                                  # Canvas comments, and report comments not tied to a rubric line
        if problems and any(it.get("comment") == note["id"] for pr in problems for it in pr["items"]):
            continue
        t, b = st.columns([5, 1.4], vertical_alignment="center")
        t.markdown(f"> **Grader:** {note['text']}")
        if note.get("page"):
            b.button(f"Page {note['page']}", key=f"gp{book['id']}_c{note['id']}", type="tertiary", on_click=_go_page,
                     args=(book["id"], note["page"]), help="show where the grader marked this")


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


def _homework_helper(book):
    """For each problem and sub-problem: the note section it draws on, and a hint built from that section."""
    course = crud.get_course(book["course_ids"][0])
    books = crud.list_books()
    try:
        problems = hwassist.analyze(book, course, books)
    except Exception:
        problems = []
    st.subheader("Homework Helper")
    number = re.search(r"\d+", book.get("lecture") or book["title"])
    solution = next((b for b in books if b["kind"] == "Homework Solution" and set(b["course_ids"]) & set(book["course_ids"])
                     and number and re.search(r"\d+", b.get("lecture") or b["title"])
                     and re.search(r"\d+", b.get("lecture") or b["title"]).group() == number.group()), None)
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
            for part in pr["parts"]:
                pkey = f"{key}{part['id']}"
                txt, pbulb = st.columns([8, 1], vertical_alignment="center")
                txt.markdown(f"**{part['id']})** {hwassist.tex(hwassist.clean(part['text']), limit=170)}")
                if part["hint"]:
                    with pbulb.popover("", icon=":material/lightbulb:", help="hint for this part"):
                        st.markdown(part["hint"])
                if part["tags"] and part["tags"][:1] != pr["tags"][:1]:
                    _tag_buttons(part["tags"][:1], pkey)


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
            p = BASE_DIR / book["pdf_path"]
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
    """Order inside a course: notes in lecture-number order, then other notes, then textbooks (each by title)."""
    numbers = tuple(int(n) for n in re.findall(r"\d+", book.get("lecture") or ""))
    if book["kind"] == "Homework":
        return (1.5, numbers, book["title"].lower())
    if book["kind"] == "Homework Solution":
        return (1.6, numbers, book["title"].lower())
    if book["kind"] == "Syllabus":
        return (-1, (), book["title"].lower())
    if book["kind"] == "Graded Homework":
        return (1.65, numbers, book["title"].lower())
    if book["kind"] == "Graded Exam":
        return (1.75, tuple(int(n) for n in re.findall(r"\d+", book["title"])), book["title"].lower())
    if book["kind"] == "Exam":
        return (1.7, tuple(int(n) for n in re.findall(r"\d+", book["title"])), book["title"].lower())
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
            tip = "" if has_books else ' title="click to add pdf"'
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
    st.session_state.setdefault("library_filter", st.session_state.get("_library_filter_kept", "All"))
    options = ["All"] + KINDS
    counts = {"All": len(all_books), **{k: sum(b["kind"] == k for b in all_books) for k in KINDS}}
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
    books = all_books if choice == "All" else [b for b in all_books if b["kind"] == choice]
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
