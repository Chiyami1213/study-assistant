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
        assert run["part"] == part and len(run["order"]) == 2 and (part != "speed" or run["limit"] == 10)
        for qi in run["order"][:right]:
            run["res"][qi] = {"chosen": run["qs"][qi]["a"], "notes": False, "hint": False}
        quiz_view._finish(course, ch, run)
        assert run["correct"] == right
    s = crud.quiz_stats(course["id"])[ch["book"]["id"]]
    assert (s["last_correct"], s["last_total"], sorted(s["parts"])) == (4, 6, ["concept", "guided", "speed"])
    assert [a["part"] for a in crud.quiz_attempts(course["id"], ch["book"]["id"])] == ["guided", "speed", "concept"]
    quiz_view._start(run_key, ch, "guided")
    assert [q["a"] for q in quiz_view.st.session_state[run_key]["qs"]] == [1, 1] and quiz_view.st.session_state[run_key]["order"] == [0, 1]       # steps keep their order and their options


def _add_note(cid, lecture, body):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = PDF_DIR / f"book_variety_{lecture}.html"
    dest.write_text(f"<html><head><title>T{lecture}</title></head><body>{body}</body></html>", encoding="utf-8")
    return crud.add_book(f"Note {lecture}", "", "", stored_path(dest), None, [cid], "Notes", "2026", str(lecture))


def test_guides_with_different_quizzes_are_all_handled():
    """Any mix of the parts: only a speed round (another variable name), only guided examples of the notes, only open questions, a broken quiz, no quiz at all."""
    cid = crud.add_course("HUM 1", "Variety", "Fall 2026", 0, "Active")
    only_speed = _add_note(cid, 1, '<section id="s1"><h2>One</h2></section><script>const SPEED=[["a?",["y","n"],0,"because"],["b?",["y","n"],1,"since"]],N=1,LIMIT=45;</script>')
    only_guided = _add_note(cid, 2, '<section id="s1"><h2>One</h2><details class="example" id="ex-3"><summary><span class="exn">Ex 3</span>Spread</summary><div class="exbody"><h5>Problem</h5><p>Find it.</p>'
                                    '<h5 class="exclear">Solution</h5></div></details></section><script>window.GD_DATA=[{"id": 3, "steps": [{"tag": "m", "q": "Which?", "o": [["A", 1, "yes"], ["B", 0, "no"]], "done": "x"}], "final": "7"}];</script>')
    only_open = _add_note(cid, 3, '<section id="quiz"><h2>Quiz</h2><details class="q"><summary>1. Why does the sky look blue?</summary><p>Rayleigh scattering.</p></details>'
                                  '<details class="q"><summary>2. Name one source of error.</summary><p>Parallax.</p></details></section>')
    _add_note(cid, 4, '<section id="s1"><h2>Broken</h2></section><script>var BANK=[["a",["y"</script><script>window.GD_DATA=[{"id": 1, "steps": [</script>')            # a quiz that cannot be read
    _add_note(cid, 5, '<section id="s1"><h2>No quiz at all</h2></section>')
    by = {c["book"]["id"]: c for c in quiz_view.course_chapters(crud.get_course(cid))}
    assert set(by) == {only_speed, only_guided, only_open}                                                   # the broken one and the one without a quiz offer nothing, and nothing fails
    assert list(quiz_view.chapter_parts(by[only_speed])) == ["speed"] and by[only_speed]["speed"]["n"] == 1 and by[only_speed]["speed"]["limit"] == 45
    g = quiz_view.chapter_parts(by[only_guided])
    assert list(g) == ["guided"] and g["guided"][0]["tag"].startswith("Practice 3") and "Find it." in g["guided"][0]["ctx"]            # the guided examples of the notes, no practice section needed
    o = quiz_view.chapter_parts(by[only_open])
    assert list(o) == ["concept"] and [q["kind"] for q in o["concept"]] == ["open", "open"]


def test_open_questions_are_answered_by_looking_at_the_model_answer_and_scored_by_the_student():
    cid = crud.add_course("HUM 2", "Essays", "Fall 2026", 0, "Active")
    bid = _add_note(cid, 1, '<section id="quiz"><h2>Quiz</h2><details class="q"><summary>1. Why?</summary><p>Because.</p></details><details class="q"><summary>2. How?</summary><p>Like so.</p></details></section>')
    course = crud.get_course(cid)
    ch = quiz_view.course_chapters(course)[0]
    quiz_view._start("quiz_run_open", ch, "concept")
    run = quiz_view.st.session_state["quiz_run_open"]
    run["res"][run["order"][0]] = {"got": True}
    run["res"][run["order"][1]] = {"got": False}
    quiz_view._finish(course, ch, run)
    assert (run["correct"], len(run["review"])) == (1, 2)
    assert crud.quiz_stats(cid)[bid]["last_correct"] == 1 and crud.quiz_stats(cid)[bid]["last_total"] == 2


def test_the_quiz_tab_runs_an_open_question_quiz_end_to_end():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    cid = crud.add_course("HUM 3", "Essays", "Fall 2026", 0, "Active")
    bid = _add_note(cid, 1, '<section id="quiz"><h2>Quiz</h2><details class="q"><summary>1. Why?</summary><p>Because.</p></details></section>')
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=90)
    at.session_state["page"] = "Courses"
    at.session_state["open_course"] = cid
    at.session_state["course_tab"] = (cid, "Quiz")
    at.run()
    assert not at.exception
    at.button(key=f"quiz_go_{cid}_{bid}").click().run()
    assert not at.exception and any(b.label == "I Had It" for b in at.button)
    next(b for b in at.button if b.label == "I Had It").click().run()
    at.button(key=f"quiz_finish_{cid}").click().run()
    assert not at.exception and crud.quiz_stats(cid)[bid]["last_correct"] == 1


CLOSED = ('<section id="quiz"><h2>Quiz</h2><div id="cbr"><h3>Closed-Book Round · Write It From Memory</h3>'
          '<div class="cbbar"><button type="button" id="cbClose">Close all</button><span class="cbp" id="cbProg"></span></div>'
          '<details class="cb"><summary><span class="cbn">1.</span><span class="cbq">Write: Gibbs phase rule</span></summary><div class="cba"><div class="eqb key"><div class="eqm">\\[F=C-P+2\\]</div></div>'
          '<p class="small">\\(C\\) components, \\(P\\) phases.</p><label class="cbk"><input type="checkbox" data-id="c1"/> I wrote this correctly from memory</label></div></details>'
          '<details class="cb"><summary><span class="cbn">2.</span><span class="cbq">Write: Enthalpy</span></summary><div class="cba"><div class="eqb key"><div class="eqm">\\[H\\equiv U+pV\\]</div></div>'
          '<label class="cbk"><input type="checkbox" data-id="c2"/> I wrote this correctly from memory</label></div></details></div></section>')


def test_the_closed_book_round_is_a_quiz_of_its_own_scored_by_the_student():
    from study import quizparts
    qs = quizparts.closed(CLOSED)
    assert [q["q"] for q in qs] == ["Write: Gibbs phase rule", "Write: Enthalpy"] and all(q["kind"] == "open" for q in qs)
    assert "$$F=C-P+2$$" in qs[0]["e"] and "$C$ components" in qs[0]["e"] and "I wrote this correctly" not in qs[0]["e"]      # the answer without the tick box
    assert quizparts.closed("<section id='s1'>no round</section>") == []
    cid = crud.add_course("HUM 3", "Closed", "Fall 2026", 0, "Active")
    bid = _add_note(cid, 1, CLOSED)
    course = crud.get_course(cid)
    ch = quiz_view.course_chapters(course)[0]
    assert list(quiz_view.chapter_parts(ch)) == ["closed"] and quiz_view.PART_LABEL["closed"] == "Closed-Book Round"
    quiz_view._start("quiz_run_closed", ch, "closed")
    run = quiz_view.st.session_state["quiz_run_closed"]
    run["res"][run["order"][0]] = {"got": True}
    run["res"][run["order"][1]] = {"got": False}
    quiz_view._finish(course, ch, run)
    s = crud.quiz_stats(cid)[bid]
    assert (s["last_correct"], s["last_total"]) == (1, 2) and set(s["parts"]) == {"closed"}


def test_speed_round_time_is_seconds_per_question_from_settings():
    from core import settings
    assert settings.get_quiz() == {"speed_seconds": 5, "use_guide_time": False}                            # the default: 5 seconds for each question
    cid = crud.add_course("HUM 4", "Speed", "Fall 2026", 0, "Active")
    _add_note(cid, 1, '<section id="s1"><h2>One</h2></section><script>var BANK=[["a?",["y","n"],0,"x"],["b?",["y","n"],1,"x"],["c?",["y","n"],0,"x"],["d?",["y","n"],1,"x"]],N=3,LIMIT=90;</script>')
    ch = quiz_view.course_chapters(crud.get_course(cid))[0]
    assert quiz_view.speed_limit(ch) == 15                                                                  # 3 questions x 5 s, not the 90 s of the guide
    settings.set_quiz(speed_seconds=8)
    assert quiz_view.speed_limit(ch) == 24
    quiz_view._start("quiz_run_speedtime", ch, "speed")
    assert quiz_view.st.session_state["quiz_run_speedtime"]["limit"] == 24
    settings.set_quiz(use_guide_time=True)
    assert quiz_view.speed_limit(ch) == 90                                                                  # or the guide's own limit when Settings says so
    settings.set_quiz(speed_seconds=5, use_guide_time=False)
