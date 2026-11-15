"""Reading dated work and class times out of the text of a syllabus."""
from datetime import date

from planner import syllabus_read as R

FIRST, LAST = date(2026, 8, 24), date(2026, 12, 18)
TEXT = """AE 6009 Syllabus
Lecture: Tuesdays and Thursdays 2:00 - 3:15 PM, Room Guggenheim 442
Grading policy: homework 30%, midterm 30%, final 40%
Schedule
Sep 3   Introduction
Sep 10  HW 1 due 11:59 PM
Sep 24
Homework 2 due
Oct 8   Midterm Exam 1 (in class)
Oct 22 Quiz 3
10/29   Project Proposal due
Nov 26  No class, Thanksgiving break
Dec 11, 2026  Final Exam, 8:00 AM
"""


def test_the_dated_work_is_found_with_its_category_and_date():
    items = {(i.title, i.category, i.due) for i in R.find_items(TEXT, FIRST, LAST)}
    assert ("HW 1", "Homework", date(2026, 9, 10)) in items
    assert ("Homework 2", "Homework", date(2026, 9, 24)) in items                    # the date and the work on two lines of a split table row
    assert ("Midterm Exam 1", "Exam", date(2026, 10, 8)) in items
    assert ("Quiz 3", "Quiz", date(2026, 10, 22)) in items
    assert ("Project Proposal", "Project", date(2026, 10, 29)) in items
    assert ("Final Exam", "Exam", date(2026, 12, 11)) in items


def test_times_are_read_and_the_usual_ones_are_filled_in():
    by = {i.title: i for i in R.find_items(TEXT, FIRST, LAST)}
    assert by["HW 1"].due_time == "23:59" and by["Final Exam"].due_time == "08:00" and by["Midterm Exam 1"].due_time == "09:00" and by["Quiz 3"].due_time == "23:59"


def test_lines_without_work_and_the_grading_policy_give_nothing():
    titles = [i.title for i in R.find_items(TEXT, FIRST, LAST)]
    assert not any("Introduction" in t or "Thanksgiving" in t for t in titles)
    assert R.find_items("Grading: homework 30%, final 40%. Office hours Mon 3 pm.", FIRST, LAST) == []


def test_a_date_without_a_year_takes_the_year_of_the_term():
    spring = R.find_items("Jan 20 HW 1 due", date(2027, 1, 11), date(2027, 5, 7))
    assert spring[0].due == date(2027, 1, 20)
    assert R.find_items("Dec 3 HW 1 due", FIRST, LAST)[0].due == date(2026, 12, 3)
    assert R.find_items("Mar 5, 2028 HW 1 due", FIRST, LAST)[0].due == date(2028, 3, 5)


def test_the_same_work_on_the_same_day_is_listed_once_and_in_date_order():
    items = R.find_items("Oct 2 HW 3 due\nOct 2 HW 3 due\nSep 1 HW 1 due", FIRST, LAST)
    assert [i.title for i in items] == ["HW 1", "HW 3"]


def test_class_times_from_words_and_from_codes():
    (m,) = R.find_meetings(TEXT)
    assert (m.days, m.start, m.end) == ((1, 3), "14:00", "15:15") and "Guggenheim" in m.location
    (m,) = R.find_meetings("Class meets MWF 10:00-10:50 AM")
    assert (m.days, m.start, m.end) == ((0, 2, 4), "10:00", "10:50")
    assert R.find_meetings("Office hours Tuesday 3-4 pm") == []                      # not a class
