"""Prompts for the student's Claude chat: every page type, the course filled in, the format the app reads, and file names the Library recognizes."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from study import promptgen as P
from views import library_import, library_view

APP = str(Path(__file__).resolve().parent.parent / "app.py")
COURSE = {"code": "XYZ 101", "name": "Fluid Statics"}
NUMBER = {"chapter": "3", "homework": "4", "exam": "Midterm 2"}


def number_of(kind):
    return NUMBER[P.KINDS[kind][1]]


@pytest.mark.parametrize("kind", list(P.KINDS))
def test_every_prompt_has_the_course_the_page_name_and_no_placeholder_left(kind):
    text = P.build_prompt(kind, COURSE, number_of(kind))
    name = P.file_name(kind, COURSE, number_of(kind))
    assert name.startswith("XYZ101 ") and f"`{name}`" in text
    assert not any(token in text for token in ("<COURSE>", "<FILE>", "<N>"))
    assert "AE6765" not in text and "AE 6009" not in text and "Vincenti" not in text            # nothing of the author's own courses
    assert "## App Format (Required)" in text and "## Your Job" in text and "## Inputs I Will Give You" in text


def test_the_page_names_follow_the_librarys_forms():
    names = {k: P.file_name(k, COURSE, number_of(k)) for k in P.KINDS}
    assert names == {"Study Guide": "XYZ101 Chapter 3 Notes", "Homework Helper": "XYZ101 Homework 4 Helper", "Homework Grade Explanation": "XYZ101 Homework 4 Grades",
                     "Exam Grade Explanation": "XYZ101 Midterm 2 Grades", "Exam Reflection": "XYZ101 Midterm 2 Reflection", "Exam Preparation": "XYZ101 Midterm 2 Preparation"}
    assert P.file_name("Exam Preparation", COURSE, "Final Exam") == "XYZ101 Final Exam Preparation"
    assert P.course_tag({"code": "MA 266 / 303", "name": "x"}) == "MA266" and P.course_tag({"code": "", "name": "Tonal  Harmony"}) == "Tonal Harmony"


@pytest.mark.usefixtures("fresh_data")
def test_the_library_recognizes_the_files_a_prompt_asks_for():
    expect = {"Study Guide": ("Notes", "3"), "Homework Helper": ("Homework Helper", "4"), "Homework Grade Explanation": ("Grade Explanation", "4"),
              "Exam Grade Explanation": ("Exam Grade Explanation", ""), "Exam Reflection": ("Exam Reflection", ""), "Exam Preparation": ("Exam Preparation", "")}
    for kind, (library_kind, lecture) in expect.items():
        file = P.file_name(kind, COURSE, number_of(kind)) + ".html"
        got_kind, title, got_lecture, _ = library_import.guess_fields(file)
        assert (got_kind, got_lecture) == (library_kind, lecture), (kind, got_kind, got_lecture)
    assert library_import.guess_fields("XYZ101 Midterm 2 Preparation.html")[1] == "Midterm 2 Preparation"
    assert library_import.guess_fields("XYZ101 Final Exam Reflection.html")[1] == "Final Exam Reflection"
    assert library_view.detect_kind("XYZ101 Midterm 2 Preparation.pdf") == "Exam"                      # a pdf of that name is still just an exam file


def test_the_format_the_app_reads_is_in_the_prompt_of_each_page():
    guide = P.build_prompt("Study Guide", COURSE, "3")
    for needle in ("`mindmap`", "`eqsheet`", "`errata`", "`quiz`", 's2-2', 'id="qBox"', "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js"):
        assert needle in guide, needle
    helper = P.build_prompt("Homework Helper", COURSE, "4")
    assert '<section class="card" id="p1">' in helper and '<div class="part">' in helper and '<span class="pl">a)</span>' in helper and "Lec N §x.y · Title" in helper
    for kind in ("Homework Grade Explanation", "Exam Grade Explanation"):
        grades = P.build_prompt(kind, COURSE, number_of(kind))
        assert 'class="gc"' in grades and 'class="badge"' in grades and 'href="#p1"' in grades and "Midterm 2 Preparation" in grades
    assert "Exam Reflection" in P.build_prompt("Exam Reflection", COURSE, "Final Exam") and "Final Exam Reflection" in P.build_prompt("Exam Reflection", COURSE, "Final Exam")
    prep = P.build_prompt("Exam Preparation", COURSE, "Midterm 2")
    assert "Mock Exam" in prep and "Predicted Problems" in prep and "Score After the Exam" in prep


def test_the_page_specification_is_the_one_of_the_page_and_exams_have_no_helper():
    helper = P.build_prompt("Homework Helper", COURSE, "4")
    assert "Before You Start: Lessons From Graded Work" in helper and "Patterns to Carry Forward" not in helper
    exam = P.build_prompt("Exam Grade Explanation", COURSE, "Midterm 2")
    assert "Notes on the Exam Statement" in exam and "no helper page" in exam and "Mock Exam" not in exam
    assert "Homework n" not in P.build_prompt("Homework Grade Explanation", COURSE, "4") and "Homework 4" in P.build_prompt("Homework Grade Explanation", COURSE, "4")


def test_notes_textbooks_and_the_style_rules_are_added_when_given():
    notes = [{"lecture": "3", "title": "Eigenvalues"}, {"lecture": "", "title": "Overview"}]
    text = P.build_prompt("Homework Helper", COURSE, "4", notes=notes)
    assert "## My Notes For This Course" in text and "- Lec 3: Eigenvalues" in text and "- Overview" in text
    assert "## My Notes For This Course" not in P.build_prompt("Homework Helper", COURSE, "4")
    guide = P.build_prompt("Study Guide", COURSE, "3", textbooks=["Statics Made Simple"])
    assert "- Statics Made Simple" in guide and "## Study Guide Rules" in guide and "Highlighter" in guide
    short = P.build_prompt("Study Guide", COURSE, "3", include_rules=False)
    assert "## Study Guide Rules" not in short and len(short) < len(guide) / 2
    assert "## Style Rules (From My Study Guides)" in P.build_prompt("Exam Reflection", COURSE, "Midterm 1") and "Highlighter" not in P.build_prompt("Exam Reflection", COURSE, "Midterm 1")


def test_an_unknown_page_type_is_refused_and_the_section_reader_works():
    with pytest.raises(ValueError):
        P.build_prompt("Poster", COURSE, "1")
    assert P.sections("intro\n## A\nx\n### sub\ny\n## B\nz") == [("A", "x\n### sub\ny"), ("B", "z")]
    assert P.sections("## A\n### 1. one\na\n### 2. two\nb", "### ") == [("1. one", "a"), ("2. two", "b")]


@pytest.mark.usefixtures("fresh_data")
def test_the_library_import_menu_has_the_prompt_button():
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Library"
    at.run()
    assert not at.exception and at.button(key="imp_menu_prompt") is not None
