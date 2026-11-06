"""Course Quiz tab and the Understanding block of the Overview.

Questions come from the Self-check sections of the course's HTML notes (one quiz per chapter or lecture).
Each finished quiz is saved with its score, and the Overview shows the latest score per chapter."""
import html
import json
import random

import streamlit as st

import crud
import quizzes
from database import BASE_DIR
from views import library_view

STRONG, OKAY = 80, 60


@st.cache_data(show_spinner=False, max_entries=64)
def _questions(path, mtime):
    return quizzes.parse(open(path, encoding="utf-8", errors="replace").read())


def course_chapters(course):
    """[{book, name, questions}] for the course's HTML notes that have self-check questions, in lecture order."""
    out = []
    for b in sorted((b for b in crud.list_books() if course["id"] in b["course_ids"]
                     and b["kind"] in ("Notes", "Lecture Notes") and b["pdf_path"].lower().endswith((".html", ".htm"))),
                    key=library_view._course_order):
        path = BASE_DIR / b["pdf_path"]
        if not path.exists():
            continue
        qs = _questions(str(path), path.stat().st_mtime)
        if qs:
            out.append({"book": b, "questions": qs,
                        "name": (f"Lec {b['lecture']} · " if b.get("lecture") else "") + b["title"]})
    return out


def _pct(correct, total):
    return round(100 * correct / total) if total else 0


def _level(pct):
    return ("Strong", "done") if pct >= STRONG else ("Getting There", "open") if pct >= OKAY else ("Needs Review", "late")


# ---------- Overview: how well the materials are understood ----------
def understanding(course):
    chapters = course_chapters(course)
    if not chapters:
        return
    stats = crud.quiz_stats(course["id"])
    taken = [stats[c["book"]["id"]] for c in chapters if c["book"]["id"] in stats]
    st.subheader("Understanding")
    if taken:
        avg = round(sum(_pct(s["last_correct"], s["last_total"]) for s in taken) / len(taken))
        st.caption(f"{avg}% average of the latest scores · {len(taken)} of {len(chapters)} chapters quizzed. "
                   f"Take a quiz in the Quiz tab.")
    else:
        st.caption("No quizzes taken yet. Take one in the Quiz tab to see how well you know each chapter.")
    rows = ""
    for c in chapters:
        s = stats.get(c["book"]["id"])
        if s:
            pct = _pct(s["last_correct"], s["last_total"])
            label, css = _level(pct)
            detail = f"{s['last_correct']}/{s['last_total']} · best {s['best']}% · {s['attempts']} attempt{'s' if s['attempts'] != 1 else ''}"
        else:
            pct, label, css, detail = 0, "Not Taken", "none", f"{len(c['questions'])} questions"
        rows += (f'<div class="und-row"><div class="und-name">{html.escape(c["name"])}'
                 f'<div class="und-detail">{detail}</div></div>'
                 f'<div class="und-bar"><i class="{css}" style="width:{pct}%"></i></div>'
                 f'<div class="und-pct">{pct}%</div><span class="dl-pill {css}">{label}</span></div>')
    st.markdown(f'<div class="dl-list">{rows}</div>', unsafe_allow_html=True)


# ---------- Quiz tab ----------
def _start(run_key, chapter):
    order = list(range(len(chapter["questions"])))
    random.shuffle(order)
    st.session_state[run_key] = {"book": chapter["book"]["id"], "order": order, "phase": "answer", "mc": {}, "typed": {},
                                 "got": {}, "stamp": random.random()}


def _leave(run_key):
    st.session_state.pop(run_key, None)


def render(course):
    chapters = course_chapters(course)
    if not chapters:
        st.info("No quiz questions yet. Quizzes come from the Self-check section of this course's HTML notes in the Library.")
        return
    run_key = f"quiz_run_{course['id']}"
    run = st.session_state.get(run_key)
    by_book = {c["book"]["id"]: c for c in chapters}
    if run and run["book"] in by_book:
        _run(course, by_book[run["book"]], run, run_key)
        return
    stats = crud.quiz_stats(course["id"])
    st.caption("Pick a chapter or lecture. The questions come from its Self-check section, in a new order each time.")
    for c in chapters:
        s = stats.get(c["book"]["id"])
        name, meta, pill, go = st.columns([5, 2.6, 1.6, 1.3], vertical_alignment="center")
        name.markdown(f"**{c['name']}**  \n{len(c['questions'])} questions")
        if s:
            pct = _pct(s["last_correct"], s["last_total"])
            label, css = _level(pct)
            meta.markdown(f"Last {s['last_correct']}/{s['last_total']} ({pct}%)  \nBest {s['best']}% · {s['attempts']} attempts")
            pill.markdown(f'<span class="dl-pill {css}">{label}</span>', unsafe_allow_html=True)
        else:
            meta.caption("Not taken yet")
        go.button("Retake" if s else "Start", key=f"quiz_go_{course['id']}_{c['book']['id']}", type="primary" if not s else "secondary",
                  width="stretch", on_click=_start, args=(run_key, c))


def _finish(course, chapter, run, run_key):
    qs, order = chapter["questions"], run["order"]
    correct, review = 0, []
    for qi in order:
        q = qs[qi]
        if q["kind"] == "mc":
            chosen = run["mc"].get(qi)
            ok = chosen == q["a"]
        else:
            chosen, ok = None, bool(run["got"].get(qi))
        correct += ok
        review.append({"q": qi, "chosen": chosen, "ok": ok})
    crud.add_quiz_attempt(course["id"], chapter["book"]["id"], correct, len(order), json.dumps(review))
    run.update(phase="done", correct=correct, review=review)


def _run(course, chapter, run, run_key):
    qs, order, cid, bid = chapter["questions"], run["order"], course["id"], chapter["book"]["id"]
    head, back = st.columns([6, 1.6], vertical_alignment="center")
    head.subheader(chapter["name"])
    back.button("Back To Quizzes" if run["phase"] == "done" else "Leave Quiz", key=f"quiz_back_{cid}", width="stretch",
                on_click=_leave, args=(run_key,))

    if run["phase"] == "answer":
        with st.form(f"quiz_form_{cid}_{bid}_{run['stamp']}"):
            for pos, qi in enumerate(order, 1):
                q = qs[qi]
                st.markdown(f"**{pos}.** {q['q']}")
                if q["kind"] == "mc":
                    st.radio("Answer", q["o"], index=None, key=f"qz_{cid}_{bid}_{qi}_{run['stamp']}", label_visibility="collapsed")
                else:
                    st.text_area("Your answer (optional)", key=f"qz_{cid}_{bid}_{qi}_{run['stamp']}", height=80)
            sent = st.form_submit_button("Check Answers", type="primary")
        if sent:
            for qi in order:
                q, val = qs[qi], st.session_state.get(f"qz_{cid}_{bid}_{qi}_{run['stamp']}")
                if q["kind"] == "mc":
                    run["mc"][qi] = q["o"].index(val) if val in q["o"] else None
                else:
                    run["typed"][qi] = val or ""
            if any(qs[qi]["kind"] == "open" for qi in order):
                run["phase"] = "grade"
            else:
                _finish(course, chapter, run, run_key)
            st.rerun()
        return

    if run["phase"] == "grade":
        st.caption("These questions are marked by you. Read the model answer, then say whether you had it.")
        with st.form(f"quiz_grade_{cid}_{bid}_{run['stamp']}"):
            for pos, qi in enumerate(order, 1):
                q = qs[qi]
                if q["kind"] != "open":
                    continue
                st.markdown(f"**{pos}.** {q['q']}")
                if run["typed"].get(qi):
                    st.caption("Your answer: " + run["typed"][qi])
                st.info(q["e"])
                st.radio("Did you have it?", ["Got it", "Missed it"], index=None, horizontal=True,
                         key=f"qg_{cid}_{bid}_{qi}_{run['stamp']}")
            sent = st.form_submit_button("Save Score", type="primary")
        if sent:
            for qi in order:
                if qs[qi]["kind"] == "open":
                    run["got"][qi] = st.session_state.get(f"qg_{cid}_{bid}_{qi}_{run['stamp']}") == "Got it"
            _finish(course, chapter, run, run_key)
            st.rerun()
        return

    # done: the score and a review of every question
    total, correct = len(order), run["correct"]
    pct = _pct(correct, total)
    label, css = _level(pct)
    st.markdown(f'<div class="und-score"><b>{correct} / {total}</b><span>{pct}%</span><span class="dl-pill {css}">{label}</span></div>',
                unsafe_allow_html=True)
    st.button("Retake", key=f"quiz_again_{cid}", on_click=_start, args=(run_key, chapter))
    for pos, r in enumerate(run["review"], 1):
        q = qs[r["q"]]
        st.markdown(f"{'✅' if r['ok'] else '❌'} **{pos}.** {q['q']}")
        if q["kind"] == "mc":
            if not r["ok"]:
                st.markdown("Your answer: " + (q["o"][r["chosen"]] if r["chosen"] is not None else "(none)"))
            st.markdown("Answer: " + q["o"][q["a"]])
        if q["e"]:
            st.caption(q["e"]) if q["kind"] == "mc" else st.markdown(q["e"])
