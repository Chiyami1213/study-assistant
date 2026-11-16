"""Prompts for the student's AI chat (Claude, ChatGPT, Gemini): every page type, the course filled in, the format the app reads, and file names the Library recognizes."""
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


def test_the_quiz_array_the_prompt_asks_for_is_what_the_quiz_reader_understands():
    from study import quizzes
    prompt = P.build_prompt("Study Guide", COURSE, "3")
    assert "const Q = [" in prompt and "zero-based index of the correct option" in prompt
    page = ('<html><body><section id="quiz"><h2>Quiz</h2><div id="qBox"></div></section><script>const Q = [\n'
            '  ["s2-2", "What does \\(Av=\\lambda v\\) define?", ["A norm", "An eigenpair", "A basis", "A rank"], 1, "It is the eigenvalue equation.", "Think of v.", false],\n'
            '  ["s3-1", "Which result is from the textbook?", ["One", "Two", "Three"], 0, "Because.", "", true],\n];</script></body></html>')
    got = quizzes.parse(page)
    assert [(q["kind"], q["section"], q["a"], q["textbook"]) for q in got] == [("mc", "s2-2", 1, False), ("mc", "s3-1", 0, True)]
    assert got[0]["o"][1] == "An eigenpair" and got[0]["h"] == "Think of v."


@pytest.mark.parametrize("assistant", list(P.ASSISTANTS))
@pytest.mark.parametrize("kind", list(P.KINDS))
def test_a_prompt_for_each_assistant_has_no_placeholder_and_only_claude_talks_of_artifacts(kind, assistant):
    text = P.build_prompt(kind, COURSE, number_of(kind), assistant=assistant)
    assert "{{" not in text and "<COURSE>" not in text
    assert (f"a {assistant} chat" in text.split(chr(10))[2])
    assert ("claude" in text.lower()) == (assistant == "Claude") and ("an HTML artifact" in text) == (assistant == "Claude")
    assert "Artifact tool" not in text or assistant == "Claude"
    assert 'id="p1"' in text or kind in ("Study Guide", "Exam Reflection", "Exam Preparation")                       # the format the app reads is in every one


def test_chatgpt_and_gemini_hand_over_a_file_or_one_code_block_and_name_notes_pages_with_a_neutral_address():
    chatgpt = P.build_prompt("Homework Helper", COURSE, "4", assistant="ChatGPT")
    gemini = P.build_prompt("Homework Helper", COURSE, "4", assistant="Gemini")
    assert "one downloadable `.html` file" in chatgpt and "single code block" in chatgpt and "Canvas" in gemini and "single code block" in gemini
    for text in (chatgpt, gemini):
        assert "https://study-assistant.local/artifact/notes-3#s2-2" in text and "Lec N §x.y · Title" in text
        assert "claude:viewport" not in text and "whole updated file" in text
    assert "an artifact link on any host" in P.build_prompt("Homework Helper", COURSE, "4")                          # Claude's text is as it was
    with pytest.raises(ValueError):
        P.build_prompt("Homework Helper", COURSE, "4", assistant="Bard")


def test_the_notes_link_reader_accepts_an_artifact_address_on_any_host():
    from study import htmlnotes
    assert "/\/artifact\/([^#?\/]+)/" in htmlnotes._LINKS and "claude\.ai" not in htmlnotes._LINKS.split("function art")[1].split("function lecOf")[0]
