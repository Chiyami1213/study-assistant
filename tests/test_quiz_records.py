"""A quiz record belongs to a chapter of a course, not only to the page it was taken on: when the note is deleted and imported again, the record comes back to the new note."""
import pytest

from core import crud

pytestmark = pytest.mark.usefixtures("fresh_data")


def note(cid, lecture, title="Chapter"):
    return crud.add_book(title, "", "", f"pdfs/n{lecture}.html", None, [cid], "Notes", "2026", lecture)


def test_a_record_follows_its_chapter_to_the_note_imported_again():
    cid = crud.add_course("PHYS 1", "P", "Fall 2026", 0, "Active")
    first = note(cid, "0")
    other = note(cid, "1")
    crud.add_quiz_attempt(cid, first, 28, 29)
    crud.add_quiz_attempt(cid, other, 40, 46)
    crud.delete_book(first)
    assert crud.quiz_attempts(cid, first) and crud.quiz_stats(cid).get(first)                         # nothing is erased with the note
    again = note(cid, "00", "Chapter 0 Notes")                                                          # "00" is chapter 0 too
    assert [(a["correct"], a["total"]) for a in crud.quiz_attempts(cid, again)] == [(28, 29)]
    assert crud.quiz_attempts(cid, first) == [] and len(crud.quiz_attempts(cid, other)) == 1


def test_an_ambiguous_chapter_is_left_alone_and_records_of_other_courses_are_not_taken():
    a = crud.add_course("A 1", "A", "Fall 2026", 0, "Active")
    b = crud.add_course("B 1", "B", "Fall 2026", 0, "Active")
    gone = note(a, "5")
    crud.add_quiz_attempt(a, gone, 1, 2)
    crud.delete_book(gone)
    note(b, "5")                                                                                         # another course: not for this record
    note(a, "5", "One")
    two = note(a, "5", "Two")                                                                            # two notes of chapter 5 in the course: which one is not known
    assert crud.quiz_attempts(a, two) == [] and crud.relink_quiz_attempts() == 0


def test_the_three_quizzes_of_a_chapter_are_separate_but_count_in_total():
    cid = crud.add_course("PHYS 2", "P", "Fall 2026", 0, "Active")
    b = note(cid, "3")
    crud.add_quiz_attempt(cid, b, 10, 12)                                      # conceptual (the usual)
    s = crud.quiz_stats(cid)[b]
    assert (s["last_correct"], s["last_total"], list(s["parts"])) == (10, 12, ["concept"])
    crud.add_quiz_attempt(cid, b, 6, 8, part="speed")
    crud.add_quiz_attempt(cid, b, 4, 8, part="guided")
    s = crud.quiz_stats(cid)[b]
    assert (s["last_correct"], s["last_total"], s["attempts"]) == (20, 28, 3)    # 10 + 6 + 4 of 12 + 8 + 8
    crud.add_quiz_attempt(cid, b, 8, 8, part="speed")                          # a retake of one part replaces its score in the total
    s = crud.quiz_stats(cid)[b]
    assert (s["last_correct"], s["last_total"], s["parts"]["speed"]["attempts"]) == (22, 28, 2)
    assert s["best"] == 83 and len(crud.quiz_attempts(cid, b)) == 4 and [a["part"] for a in crud.quiz_attempts(cid, b, "speed")] == ["speed", "speed"]
