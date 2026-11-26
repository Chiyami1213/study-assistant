"""What the Library shows and in which order, and what a file name says about a file. PURE (no Streamlit, no Qt): the classic page (`views/library_view.py`) and the native one (`qtui/pages/library_page.py`) both use it."""
import re

from core import crud

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



def detect_course(filename, title=""):
    """Course id guessed from a file name (then the title): 'MATH_101 notes.pdf' -> MATH 101."""
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
REFLECTION_WORDS = re.compile(r"(?<![a-z])reflections?(?![a-z])", re.I)
PREPARATION_WORDS = re.compile(r"(?<![a-z])(preparation|prep)(?![a-z])", re.I)
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
        if filename.lower().endswith((".html", ".htm")) and EXAM_WORDS.search(text) and not HOMEWORK_WORDS.search(text):          # the pages of "Midterm 1 Reflection" and "Final Exam Preparation"
            if REFLECTION_WORDS.search(text):
                return "Exam Reflection"
            if PREPARATION_WORDS.search(text):
                return "Exam Preparation"
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



SORTS = ["Type", "Course", "Date Added", "Title"]          # Type (tiles of types) is the usual way to look at the Library
INNER = {"Type": ["Course", "Date Added", "Title"], "Course": ["Type", "Date Added", "Title"]}      # how the files inside a tile can be sorted


def type_tiles(books):
    """[(type name, count)] for the tiles of the Library: one for each family of files that has a file."""
    out = []
    for name in FILTERS:
        n = sum(b["kind"] in FILTER_KINDS.get(name, (name,)) for b in books)
        if n:
            out.append((name, n))
    return out


def course_tiles(books, courses):
    """[(course id or 0 for files without a course, label, color, count)] in menu order (Active, Self-Study, Completed)."""
    out = []
    ordered = [c for s in crud.STATUSES for c in crud.courses_by_status(s)]
    for c in ordered:
        n = sum(c["id"] in b["course_ids"] for b in books)
        if n:
            out.append((c["id"], crud.label(c), crud.course_color(c), n))
    ids = {c["id"] for c in ordered}
    loose = sum(not any(i in ids for i in b["course_ids"]) for b in books)
    if loose:
        out.append((0, "No Course", "#6b7280", loose))
    return out


def books_of_type(books, name):
    return [b for b in books if b["kind"] in FILTER_KINDS.get(name, (name,))]


def books_of_course(books, course_id):
    ids = {c["id"] for s in crud.STATUSES for c in crud.courses_by_status(s)}
    if course_id == 0:
        return [b for b in books if not any(i in ids for i in b["course_ids"])]
    return [b for b in books if course_id in b["course_ids"]]


TIMELINE_UNITS = ["Day", "Month", "Year"]


def timeline_groups(books, descending=True, unit="Day"):
    """[(heading, books, None)]: the files by the day (or the month, or the year) they were added, the newest first (or the oldest first)."""
    from datetime import date as _date
    size = {"Day": 10, "Month": 7, "Year": 4}.get(unit, 10)
    groups = {}
    for b in books:
        groups.setdefault((b.get("added_at") or "")[:size], []).append(b)
    out = []
    for key in sorted(groups, reverse=descending):
        try:
            d = _date.fromisoformat((key + "-01-01")[:10] if size == 4 else (key + "-01")[:10] if size == 7 else key)
            heading = f"{d:%A, %B} {d.day}, {d.year}" if size == 10 else f"{d:%B %Y}" if size == 7 else str(d.year)
        except ValueError:
            heading = "Date Unknown"
        out.append((heading, sorted(groups[key], key=lambda b: ((b.get("added_at") or ""), b["id"]), reverse=descending), None))
    return out


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
