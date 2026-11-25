"""A chapter's quiz has three parts that are done separately and count in total: conceptual questions, the speed round, the guided numerical practice."""
import pytest

from core import crud
from core.database import PDF_DIR, stored_path
from study import quizparts
from views import quiz_view

pytestmark = pytest.mark.usefixtures("fresh_data")

NOTE = r"""<html><head><title>T</title></head><body>
<section id="s1"><h2>One</h2><h3 id="s1-1">A</h3></section>
<section id="quiz"><h2>Quiz</h2><div id="qBox"></div><div id="speed"><div id="srBox"></div></div></section>
<section id="gpractice"><h2>Guided Numerical Practice</h2><details class="example" id="ex-P1"><summary><span class="exn">Practice 1</span>Spread<span class="extag">x</span></summary>
<div class="exbody"><h5>Problem</h5><p>Find \(x\).</p><h5 class="exclear">Solution</h5></div></details></section>
<script>const Q = [["s1-1", "What?", ["a","b"], 1, "because", "hint"], ["s1-1","Who?",["c","d"],0,"e"]];</script>
<script>(function(){var BANK=[["q1",["y","n","m"],0,"e1"],["q2",["y","n","m"],1,"e2"],["q3",["y","n"],0,"e3"]],KEY='k',N=2,LIMIT=90;})();</script>
<script>window.GD_DATA=[{"id": 1, "steps": [{"tag": "x", "q": "worked example, not practice", "o": [["a", 1, "r"]], "done": "x"}]}];</script>
<script>window.GD_DATA=(window.GD_DATA||[]).concat([{"id": "P1", "steps": [{"tag": "Assumptions", "q": "Which?", "o": [["opt A", 0, "bad reason"], ["opt B", 1, "good"]], "done": "x"},
 {"tag": "Method", "q": "Next?", "o": [["P", 0, "no"], ["R", 1, "yes"]], "done": "y"}], "final": "42"}]);</script></body></html>"""


def test_the_speed_round_and_the_guided_practice_are_read_from_the_page():
    sp = quizparts.speed(NOTE)
    assert (len(sp["questions"]), sp["n"], sp["limit"]) == (3, 2, 90) and sp["questions"][1]["a"] == 1 and sp["questions"][0]["tag"] == "Speed Round"
    gd = quizparts.guided(NOTE)
    assert [(g["id"], g["title"], len(g["questions"])) for g in gd] == [("P1", "Spread", 2)]                  # only the practice, not the worked examples of the notes
    q = gd[0]["questions"][0]
    assert q["a"] == 1 and q["ofb"] == ["bad reason", "good"] and q["e"] == "good" and "Step 1 of 2" in q["tag"] and "Find $x$." in q["ctx"] and q["noshuffle"]
    assert quizparts.speed("<p>none</p>") is None and quizparts.guided("<p>none</p>") == []


def _chapter():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = PDF_DIR / "book_parts.html"
    dest.write_text(NOTE, encoding="utf-8")
    cid = crud.add_course("PHYS 9", "Parts", "Fall 2026", 0, "Active")
    crud.add_book("Chapter 1 Notes", "", "", stored_path(dest), None, [cid], "Notes", "2026", "1")
    course = crud.get_course(cid)
    return course, quiz_view.course_chapters(course)[0]


def test_the_course_quiz_tab_offers_three_quizzes_for_the_chapter():
    course, ch = _chapter()
    parts = quiz_view.chapter_parts(ch)
    assert list(parts) == ["concept", "speed", "guided"] and [len(q) for q in parts.values()] == [2, 3, 2]
    assert [quiz_view._count(ch, p, q) for p, q in parts.items()] == [2, 2, 2]                                  # a speed round asks 2 of its bank of 3


def test_each_part_is_scored_separately_and_the_total_adds_them_up():
    course, ch = _chapter()
    run_key = "quiz_run_test"
    for part, right in (("concept", 1), ("speed", 2), ("guided", 1)):
        quiz_view._start(run_key, ch, part)
        run = quiz_view.st.session_state[run_key]
        assert run["part"] == part and len(run["order"]) == 2 and (part != "speed" or run["limit"] == 90)
        for qi in run["order"][:right]:
            run["res"][qi] = {"chosen": run["qs"][qi]["a"], "notes": False, "hint": False}
        quiz_view._finish(course, ch, run)
        assert run["correct"] == right
    s = crud.quiz_stats(course["id"])[ch["book"]["id"]]
    assert (s["last_correct"], s["last_total"], sorted(s["parts"])) == (4, 6, ["concept", "guided", "speed"])
    assert [a["part"] for a in crud.quiz_attempts(course["id"], ch["book"]["id"])] == ["guided", "speed", "concept"]
    quiz_view._start(run_key, ch, "guided")
    assert [q["a"] for q in quiz_view.st.session_state[run_key]["qs"]] == [1, 1] and quiz_view.st.session_state[run_key]["order"] == [0, 1]       # steps keep their order and their options
