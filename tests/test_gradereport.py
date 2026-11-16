"""The grade report inside a Gradescope graded copy is read by the app itself (no script): the problems, the scores, the grader comments and where each comment sits on the paper."""
import pymupdf
import pytest

from study import gradereport as G

pytestmark = pytest.mark.usefixtures("fresh_data")


def graded_copy(path, with_report=True):
    doc = pymupdf.open()
    if with_report:
        page = doc.new_page()
        lines = ["Homework 3", "14.5 / 20 pts", "Question 1", "Energy Balance", "9 / 10 pts", "+ 0 pts Sign error in the work term", "1", "You dropped the minus sign here",
                 "Question 2", "Entropy", "5.5 / 10 pts", "+ 2 pts Correct setup", "+ 0 pts No final number", "2", "Finish the numbers"]
        for i, text in enumerate(lines):
            page.insert_text((40, 60 + 16 * i), text, fontsize=10)
    for q, note in ((1, "1"), (2, "2")):
        page = doc.new_page()
        page.insert_text((40, 40), f"Question assigned to the following page: {q}", fontsize=10)
        page.insert_text((300, 200), note, fontsize=5)                                  # the small number of the comment, on the paper
    doc.save(path)
    doc.close()


def test_the_report_of_a_graded_copy_is_read_and_kept(tmp_path):
    path = tmp_path / "hw3_graded.pdf"
    graded_copy(path)
    assert G.load(901) is None
    data = G.read_into(901, path)
    assert data and data["total"] == [14.5, 20.0] and [(p["n"], p["score"], p["max"]) for p in data["problems"]] == [(1, 9.0, 10.0), (2, 5.5, 10.0)]
    assert [c["id"] for c in data["comments"]] == [1, 2] and data["comments"][0]["problem"] == 1 and data["comments"][1]["page"] == 2
    assert [i["lost"] for i in data["problems"][1]["items"]] == [False, True]
    assert G.load(901) == data                                                         # kept for the file: the viewer reads it from there


def test_a_file_without_a_report_is_left_alone(tmp_path):
    plain = tmp_path / "plain.pdf"
    graded_copy(plain, with_report=False)
    assert G.read_into(902, plain) is None and G.load(902) is None
    assert G.read_into(903, tmp_path / "missing.pdf") is None
