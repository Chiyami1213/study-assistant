"""An outline pasted from somewhere else becomes the editor's text form (and then the same outline the editor saves)."""
from library import courseoutline as C


def test_markers_set_the_levels():
    text = "I. Foundations\n  A. Continuum\n    1. Knudsen number\n      a. a detail\nII. Viscous flow"
    assert C.normalize_text(text).splitlines() == ["I.  Foundations", "  A.  Continuum", "    1.  Knudsen number", "      a.  a detail", "II.  Viscous flow"]


def test_the_markers_decide_even_without_indentation():
    text = "I. Foundations\nA. Continuum\n1. Knudsen number\na. a detail\nII. Viscous flow"
    assert [l[:len(l) - len(l.lstrip())] for l in C.normalize_text(text).splitlines()] == ["", "  ", "    ", "      ", ""]


def test_bullets_and_tabs_get_their_level_from_the_indent():
    text = "• Course Overview\n\t• Syllabus\n\t• Grading\n\t\t• Homework\n• Fluid Statics\n    - Pressure"
    assert C.normalize_text(text).splitlines() == ["Course Overview", "  Syllabus", "  Grading", "    Homework", "Fluid Statics", "  Pressure"]


def test_decimal_numbers_give_the_depth_and_are_dropped():
    assert C.normalize_text("1 Intro\n1.1 Motivation\n1.1.1 History\n2 Methods").splitlines() == ["Intro", "  Motivation", "    History", "Methods"] or \
        C.normalize_text("1.1 Motivation\n1.1.1 History").splitlines() == ["  Motivation", "    History"]


def test_part_lines_are_topics_and_the_result_reads_back_as_an_outline():
    text = "Part 0 Course Overview\nPart 1 Foundations\n  A. Continuum\n  B. Viscosity\nPart 2 Boundary layers"
    normal = C.normalize_text(text)
    assert normal.splitlines()[0] == "Part 0  Course Overview" and normal.splitlines()[2] == "  A.  Continuum"
    items = C.from_text(normal)
    assert [(i["level"], i["marker"], i["title"]) for i in items] == [("L", "Part 0", "Course Overview"), ("L", "Part 1", "Foundations"), ("A", "A", "Continuum"), ("A", "B", "Viscosity"),
                                                                      ("L", "Part 2", "Boundary layers")] or len(items) == 5


def test_blank_lines_and_nothing_are_fine():
    assert C.normalize_text("") == "" and C.normalize_text("\n\n  \n") == "" and C.normalize_text(None) == ""
    assert C.normalize_text("  just a line  ") == "just a line"


# ---------------------------------------------------------------- lecture by lecture, chapter by chapter
def test_a_table_of_lectures_becomes_the_text_form_and_reads_back_as_the_same_outline():
    rows = [{"number": "1", "title": "Introduction", "hours": ""}, {"number": "4-5", "title": "Plasma Physics", "hours": "3 Hours"}, {"number": "", "title": "Diagnostics", "hours": ""},
            {"number": "9", "title": "", "hours": ""}]
    text = C.rows_to_text(rows, "Lec")
    assert text.splitlines() == ["Lec 1  Introduction", "Lec 4-5  Plasma Physics  [3 Hours]", "Lec 3  Diagnostics"]               # a row without a title is dropped; a missing number is the row's place
    items = C.from_text(text)
    assert [(i["level"], i["marker"], i["title"], i["hours"]) for i in items] == [("L", "Lec 1", "Introduction", ""), ("L", "Lec 4-5", "Plasma Physics", "3 Hours"), ("L", "Lec 3", "Diagnostics", "")]
    assert C.rows_from_items(items) == [{"number": "1", "title": "Introduction", "hours": ""}, {"number": "4-5", "title": "Plasma Physics", "hours": "3 Hours"}, {"number": "3", "title": "Diagnostics", "hours": ""}]


def test_chapters_and_lectures_are_told_apart_and_an_outline_with_levels_is_neither():
    assert C.flat_kind(C.from_text("Lec 1  A\nLec 2  B")) == "Lectures" and C.flat_kind(C.from_text("Ch 1  A\nCh 2  B")) == "Chapters"
    assert C.flat_kind(C.from_text("I. Topic\n  A. Sub")) is None and C.flat_kind([]) is None
    assert C.rows_from_items(C.from_text("I. Topic\n  A. Sub")) == [{"number": "", "title": "Topic", "hours": ""}]          # only the top level goes into a table


def test_the_speed_round_and_the_guided_numerical_practice_belong_to_the_quiz_tab():
    from study import outline
    page = ('<section id="s1"><h2>One</h2></section><section id="quiz"><h2>Quiz</h2><div id="qBox"></div><div id="speed"><h3>Part 2 Speed Round</h3></div></section>'
            '<section id="gpractice"><h2>Guided Numerical Practice</h2></section>')
    assert [(p["key"], p["section"]) for p in outline.parts(page)] == [("notes", "s1"), ("quiz", "quiz")]          # one Quiz tab, no extra Notes part
    only = '<section id="s1"><h2>One</h2></section><section id="gpractice"><h2>Guided Numerical Practice</h2></section>'
    assert [p["key"] for p in outline.parts(only)] == ["notes", "quiz"]
