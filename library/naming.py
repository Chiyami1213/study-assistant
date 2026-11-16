"""How the Library names files: the titles an imported file gets by default, in the form the Library already uses. Pure: no database, no Streamlit.

The forms are the ones in the Library today:
  homework          HW 5      HW 5 Solution   HW 5 Graded   HW 5 Helper   HW 5 Grade Explanation      (the homework number is also the lecture field)
  exams             Midterm 1   Final Exam   Midterm 1 Practice   Midterm 1 Solution   Midterm 1 Practice Solution   Midterm 1 Graded   Midterm 1 Helper
                    Midterm 1 Grade Explanation   Midterm 1 Preparation   Midterm 1 Reflection   Midterm 1 Statistics   Midterm 1 Equation Sheet
  notes             the topic only ("Blasius at Work"); the chapter or lecture number goes in the lecture field
  syllabus          Syllabus
Anything else keeps its file name, cleaned up. The student can change any default by hand."""
import re

COURSE_PREFIX = re.compile(r"^\s*[A-Za-z]{2,5}\s*\d{3,4}[A-Za-z]?\s*[-_:.\s]*")
HW_NUMBER = re.compile(r"(?:homework|hw|problem\s*set|pset|assignment|ps)[\s_#.\-]*(\d+)", re.I)
EXAM_ID = re.compile(r"\b(?:(mid[\s-]?term)[\s_#.\-]*(\d+)|(final)(?:[\s_]*exam)?|(exam|test|quiz)[\s_#.\-]*(\d+))\b", re.I)
NOTE_MARKER = re.compile(r"^\s*(?:ch(?:apter)?|lec(?:ture)?|week|wk|unit|module|part)[\s_.#]*(\d+(?:[\-–]\d+)?)\s*[-–:._\s]*", re.I)
TRAILING_NOTE = re.compile(r"\s*\((?:lec(?:ture)?|ch(?:apter)?|week)[^)]*\)\s*$", re.I)
GENERIC = re.compile(r"^(lecture|lec|notes?|slides?|class|chapter|week)?$", re.I)

HOMEWORK_KINDS = {"Homework": "", "Homework Solution": " Solution", "Graded Homework": " Graded", "Homework Helper": " Helper", "Grade Explanation": " Grade Explanation"}
EXAM_KINDS = {"Exam": "", "Practice Exam": "", "Exam Solution": " Solution", "Graded Exam": " Graded", "Exam Helper": " Helper", "Exam Grade Explanation": " Grade Explanation",
              "Exam Preparation": " Preparation", "Exam Reflection": " Reflection", "Equation Sheet": " Equation Sheet"}


def clean_stem(name):
    """A file name as plain words: no extension, no course number in front, underscores and runs of spaces turned into single spaces."""
    stem = re.sub(r"\.(pdf|html?|htm)$", "", (name or "").strip(), flags=re.I)
    stem = re.sub(r"[_]+", " ", stem)
    stem = COURSE_PREFIX.sub("", stem)
    return re.sub(r"\s+", " ", stem).strip(" -–:")


def exam_name(text):
    """'Midterm 2', 'Final Exam', 'Exam 1' or None, from the words of a file name."""
    m = EXAM_ID.search(text or "")
    if not m:
        return None
    if m.group(1):
        return f"Midterm {m.group(2)}"
    if m.group(3):
        return "Final Exam"
    return f"{m.group(4).capitalize()} {m.group(5)}"


def default_title(kind, name, pdf_title=""):
    """(title, lecture) a file gets by default, in the Library's own form; (None, "") when the Library has no form for this kind (the caller keeps what it has)."""
    stem = clean_stem(name)
    if kind in HOMEWORK_KINDS:
        m = HW_NUMBER.search(stem) or HW_NUMBER.search(pdf_title or "") or re.search(r"(\d+)(?!.*\d)", stem)
        if not m:
            return None, ""
        number = m.group(1)
        return f"HW {number}{HOMEWORK_KINDS[kind]}", number
    if kind in EXAM_KINDS:
        exam = exam_name(stem) or exam_name(pdf_title or "")
        if not exam:
            return None, ""
        practice = " Practice" if re.search(r"practice|sample|mock", stem, re.I) and "Practice" not in EXAM_KINDS[kind] else ""
        suffix = EXAM_KINDS[kind]
        if kind == "Practice Exam":
            return f"{exam} Practice", ""
        if kind == "Exam Reflection" and re.search(r"statistic|stats|distribution", stem, re.I):
            suffix = " Statistics"
        if kind == "Exam" and practice:
            return f"{exam} Practice", ""
        return f"{exam}{practice}{suffix}", ""
    if kind == "Syllabus":
        return "Syllabus", ""
    if kind in ("Notes", "Lecture Notes"):
        m = NOTE_MARKER.match(stem)
        lecture = m.group(1) if m else ""
        topic = TRAILING_NOTE.sub("", stem[m.end():] if m else stem).strip(" -–:")
        if GENERIC.match(topic):                                              # "Week 12 Lecture": nothing but the marker, so the marker stays in the title
            return (stem or None), lecture
        return topic or None, lecture
    return None, ""
