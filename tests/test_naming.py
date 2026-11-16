"""The Library's naming forms are the defaults of an imported file (the real examples are from the Library)."""
import pytest

from library import naming as N


@pytest.mark.parametrize("kind, name, expected", [
    ("Homework", "AE6009 Homework 5.pdf", ("HW 5", "5")),
    ("Homework", "hw4.pdf", ("HW 4", "4")),
    ("Homework", "Chapter_06_Problem_Set.pdf", ("HW 06", "06")),
    ("Homework Solution", "PHYS6105 Homework 5 Solution.pdf", ("HW 5 Solution", "5")),
    ("Graded Homework", "AE6765 Homework 5 elee478.pdf", ("HW 5 Graded", "5")),
    ("Homework Helper", "AE6765 Homework 6 Helper.html", ("HW 6 Helper", "6")),
    ("Grade Explanation", "AE6765 Homework 5 Grades.html", ("HW 5 Grade Explanation", "5")),
    ("Exam", "AE6765 Midterm 1.pdf", ("Midterm 1", "")),
    ("Exam", "Final Exam.pdf", ("Final Exam", "")),
    ("Exam", "AE6765 Final.pdf", ("Final Exam", "")),
    ("Practice Exam", "AE6765 Midterm 2 Practice.pdf", ("Midterm 2 Practice", "")),
    ("Exam Solution", "PHYS6105 Midterm 2 Solution.pdf", ("Midterm 2 Solution", "")),
    ("Exam Solution", "PHYS6105 Midterm 1 Practice Solution.pdf", ("Midterm 1 Practice Solution", "")),
    ("Graded Exam", "AE6765 Midterm 1 Graded.pdf", ("Midterm 1 Graded", "")),
    ("Exam Helper", "PHYS6105 Midterm 2 Practice Helper.html", ("Midterm 2 Practice Helper", "")),
    ("Exam Grade Explanation", "AE6765 Midterm 1 Grades.html", ("Midterm 1 Grade Explanation", "")),
    ("Exam Preparation", "PHYS6105 Midterm 1 Preparation.html", ("Midterm 1 Preparation", "")),
    ("Exam Reflection", "AE6765 Midterm 1 Reflection.html", ("Midterm 1 Reflection", "")),
    ("Exam Reflection", "AE6765 Midterm 1 Stats.pdf", ("Midterm 1 Statistics", "")),
    ("Equation Sheet", "AE6765 Final Exam Equation Sheet.html", ("Final Exam Equation Sheet", "")),
    ("Equation Sheet", "Midterm 1 Equation Sheet.pdf", ("Midterm 1 Equation Sheet", "")),
    ("Syllabus", "AE6009 Syllabus Fall 2026.pdf", ("Syllabus", "")),
    ("Notes", "AE6009 Ch17 - Illingworth-Levy Similarity (Lec 20).html", ("Illingworth-Levy Similarity", "17")),
    ("Notes", "AE6009 Ch15 - Thermal Boundary Layer (Lec 18).html", ("Thermal Boundary Layer", "15")),
    ("Lecture Notes", "PHYS6105 Week 12 Lecture.pdf", ("Week 12 Lecture", "12")),
    ("Lecture Notes", "AE6009 Lec 15 Reynolds Analogy.pdf", ("Reynolds Analogy", "15")),
    ("Lecture Notes", "Lec 3 Thermal Boundary Layer.html", ("Thermal Boundary Layer", "3")),
])
def test_the_default_title_and_lecture_follow_the_library_forms(kind, name, expected):
    assert N.default_title(kind, name) == expected


def test_a_kind_with_no_form_or_a_file_without_the_number_is_left_to_the_caller():
    assert N.default_title("Textbook", "Fundamentals of Aerodynamics.pdf") == (None, "")
    assert N.default_title("Homework", "just homework.pdf") == (None, "")
    assert N.default_title("Exam", "something.pdf") == (None, "")


def test_the_number_can_come_from_the_title_inside_the_file():
    assert N.default_title("Homework", "scan0001.pdf", "Homework 7") == ("HW 7", "7")
    assert N.default_title("Exam", "scan0002.pdf", "Midterm 2") == ("Midterm 2", "")


def test_clean_stem_drops_the_extension_the_course_number_and_underscores():
    assert N.clean_stem("AE6009_Lec_17.html") == "Lec 17" and N.clean_stem("PHYS 6105 Week 3.pdf") == "Week 3" and N.clean_stem("plain name.PDF") == "plain name"
