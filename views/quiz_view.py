"""Course Quiz tab and the Understanding block of the Overview.

A chapter's quiz joins two kinds of questions: conceptual checks written for each section of the HTML note
(quizzes/<course>/<note>.json, see quizgen.py) and the note's own Self-check questions. Answers are given one per
question and nothing is marked until the quiz is finished; then the score is shown, with the explanation for every
question that was missed. Below 60% the quiz is failed.

"Check Notes" opens the note at the question's section. Using it is recorded: an answer made with the notes open
is documented as assisted and does not count towards the unaided score, which is the score the Overview shows."""
import html
import json
import random

import streamlit as st
import streamlit.components.v1 as components

import crud
import htmlnotes
import quizgen
import quizzes
from database import BASE_DIR
from views import library_view

PASS, STRONG = 60, 80          # percent: below PASS the quiz is failed


@st.cache_data(show_spinner=False, max_entries=64)
def _questions(path, mtime):
    return quizzes.parse(open(path, encoding="utf-8", errors="replace").read())


def course_chapters(course):
    """[{book, name, questions, path}] for the course's HTML notes that have questions, in lecture order."""
    out = []
    for b in sorted((b for b in crud.list_books() if course["id"] in b["course_ids"]
                     and b["kind"] in ("Notes", "Lecture Notes") and b["pdf_path"].lower().endswith((".html", ".htm"))),
                    key=library_view._course_order):
        path = BASE_DIR / b["pdf_path"]
        if not path.exists():
            continue
        own = [{**q, "tag": "Self-check", "sec": None} for q in _questions(str(path), path.stat().st_mtime)]
        made = quizgen.questions(quizgen.load(quizgen.path_for(course["code"] or course["name"], b["title"])))
        qs = made + own
        if qs:
            out.append({"book": b, "questions": qs, "path": path, "made": len(made),
                        "name": (f"Lec {b['lecture']} · " if b.get("lecture") else "") + b["title"]})
    return out


def _pct(correct, total):
    return round(100 * correct / total) if total else 0


def _level(pct):
    return ("Strong", "done") if pct >= STRONG else ("Passed", "open") if pct >= PASS else ("Failed", "late")


def _unaided(s):
    return s["last_correct"] - s["last_assisted"]


# ---------- Overview: how well the materials are understood ----------
def understanding(course):
    chapters = course_chapters(course)
    if not chapters:
        return
    stats = crud.quiz_stats(course["id"])
    taken = [stats[c["book"]["id"]] for c in chapters if c["book"]["id"] in stats]
    st.subheader("Understanding")
    if taken:
        avg = round(sum(_pct(_unaided(s), s["last_total"]) for s in taken) / len(taken))
        failed = sum(_pct(_unaided(s), s["last_total"]) < PASS for s in taken)
        st.caption(f"{avg}% average unaided score · {len(taken)} of {len(chapters)} chapters quizzed"
                   + (f" · {failed} failed (below {PASS}%)" if failed else "")
                   + ". Answers that used the notes are recorded and do not count.")
    else:
        st.caption("No quizzes taken yet. Take one in the Quiz tab to see how well you know each chapter.")
    rows = ""
    for c in chapters:
        s = stats.get(c["book"]["id"])
        if s:
            pct = _pct(_unaided(s), s["last_total"])
            label, css = _level(pct)
            notes = f" · {s['last_assisted']} with notes" if s["last_assisted"] else ""
            detail = (f"{_unaided(s)}/{s['last_total']} unaided{notes} · best {s['best']}% · "
                      f"{s['attempts']} attempt{'s' if s['attempts'] != 1 else ''}")
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
    st.session_state[run_key] = {"book": chapter["book"]["id"], "order": order, "phase": "run", "res": {},
                                 "stamp": random.randint(1, 10 ** 9)}


def _leave(run_key):
    st.session_state.pop(run_key, None)


def _entry(run_key, qi):
    return st.session_state[run_key]["res"].setdefault(qi, {"chosen": None, "notes": False})


def _pick(run_key, qi, oi):
    _entry(run_key, qi)["chosen"] = oi                  # the last option pressed is the answer


def _use_notes(run_key, qi):
    _entry(run_key, qi)["notes"] = True                 # recorded for the whole attempt


def _self_grade(run_key, qi, got):
    _entry(run_key, qi)["got"] = got


def render(course):
    chapters = course_chapters(course)
    if not chapters:
        st.info("No quiz questions yet. Quizzes come from the conceptual checks and the Self-check section of this "
                "course's HTML notes in the Library.")
        return
    run_key = f"quiz_run_{course['id']}"
    run = st.session_state.get(run_key)
    by_book = {c["book"]["id"]: c for c in chapters}
    if run and run["book"] in by_book:
        _run(course, by_book[run["book"]], run, run_key)
        return
    stats = crud.quiz_stats(course["id"])
    st.caption(f"Pick a chapter or lecture. Nothing is marked until you finish, and below {PASS}% the quiz is failed. "
               f"Check Notes is allowed but recorded.")
    for c in chapters:
        s = stats.get(c["book"]["id"])
        name, meta, pill, go = st.columns([5, 2.6, 1.6, 1.3], vertical_alignment="center")
        name.markdown(f"**{c['name']}**  \n{len(c['questions'])} questions"
                      + (f" ({c['made']} section checks)" if c["made"] else ""))
        if s:
            pct = _pct(_unaided(s), s["last_total"])
            label, css = _level(pct)
            meta.markdown(f"Last {_unaided(s)}/{s['last_total']} unaided ({pct}%)  \nBest {s['best']}% · {s['attempts']} attempts")
            pill.markdown(f'<span class="dl-pill {css}">{label}</span>', unsafe_allow_html=True)
        else:
            meta.caption("Not taken yet")
        go.button("Retake" if s else "Start", key=f"quiz_go_{course['id']}_{c['book']['id']}", type="primary" if not s else "secondary",
                  width="stretch", on_click=_start, args=(run_key, c))


def _is_right(q, res):
    if not res:
        return False
    return res.get("chosen") == q["a"] if q["kind"] == "mc" else bool(res.get("got"))


def _finish(course, chapter, run):
    qs = chapter["questions"]
    review = []
    for qi in run["order"]:
        res = run["res"].get(qi) or {}
        review.append({"q": qi, "chosen": res.get("chosen"), "ok": _is_right(qs[qi], res), "notes": bool(res.get("notes"))})
    correct = sum(r["ok"] for r in review)
    assisted = sum(r["ok"] and r["notes"] for r in review)
    crud.add_quiz_attempt(course["id"], chapter["book"]["id"], correct, len(review), json.dumps(review), assisted)
    run.update(phase="done", correct=correct, assisted=assisted, review=review)


def _note_panel(chapter, q):
    """The note, opened at the question's section (or from the top for the note's own Self-check questions)."""
    text = chapter["path"].read_text(encoding="utf-8", errors="replace")
    components.html(htmlnotes.safe_html(text, q.get("sec")), height=420, scrolling=True)


def _run(course, chapter, run, run_key):
    qs, order, cid = chapter["questions"], run["order"], course["id"]
    head, back = st.columns([6, 1.6], vertical_alignment="center")
    head.subheader(chapter["name"])
    back.button("Back To Quizzes" if run["phase"] == "done" else "Leave Quiz", key=f"quiz_back_{cid}", width="stretch",
                on_click=_leave, args=(run_key,))
    if run["phase"] == "done":
        _done(chapter, run, run_key)
        return

    res_all, styles = run["res"], ""
    answered = sum(1 for qi in order if (res_all.get(qi) or {}).get("chosen") is not None or (res_all.get(qi) or {}).get("got") is not None)
    used = sum(1 for qi in order if (res_all.get(qi) or {}).get("notes"))
    st.caption(f"{answered} of {len(order)} answered · {used} with notes (recorded). Press an option to choose it; "
               f"you can change it until you finish. Answers are marked at the end.")
    for pos, qi in enumerate(order, 1):
        q, res = qs[qi], res_all.get(qi) or {}
        prefix = f"qo_{cid}_{run['stamp']}_{qi}"
        with st.container(border=True, key=f"qcard_{cid}_{run['stamp']}_{qi}"):
            st.markdown(f"**{pos}.** {q['q']}" + (f"  \n:gray[{q['tag']}]" if q.get("tag") else ""))
            if q["kind"] == "mc":
                with st.container(horizontal=True, key=f"qopts_{cid}_{run['stamp']}_{qi}"):
                    for oi, text in enumerate(q["o"]):
                        st.button(text, key=f"{prefix}_{oi}", on_click=_pick, args=(run_key, qi, oi))
                if res.get("chosen") is not None:
                    styles += (f".st-key-{prefix}_{res['chosen']} button {{border-color: var(--accent) !important; "
                               f"background: rgba(76, 141, 255, 0.18) !important;}}")
            else:
                st.caption("Think of your answer first, then check it against the model answer when you finish.")
                a, b, _ = st.columns([1.2, 1.2, 5])
                a.button("Got It", key=f"{prefix}_got", on_click=_self_grade, args=(run_key, qi, True))
                b.button("Missed It", key=f"{prefix}_miss", on_click=_self_grade, args=(run_key, qi, False))
                if res.get("got") is not None:
                    st.caption("Marked as " + ("got it." if res["got"] else "missed."))
            if res.get("notes"):
                st.markdown(":orange[**Notes used for this question. This is recorded.**]")
                _note_panel(chapter, q)
            else:
                st.button("Check Notes", key=f"{prefix}_notes", type="tertiary", icon=":material/menu_book:",
                          on_click=_use_notes, args=(run_key, qi), help="opens the note here. it is recorded that you used it")
    if styles:
        st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)
    if st.button("Finish And Score", key=f"quiz_finish_{cid}", type="primary"):
        _finish(course, chapter, run)
        st.rerun()


def _done(chapter, run, run_key):
    qs = chapter["questions"]
    total, correct, assisted = len(run["order"]), run["correct"], run["assisted"]
    unaided = correct - assisted
    pct = _pct(unaided, total)
    label, css = _level(pct)
    st.markdown(f'<div class="und-score"><b>{unaided} / {total}</b><span>{pct}% unaided</span>'
                f'<span class="dl-pill {css}">{label}</span></div>', unsafe_allow_html=True)
    if assisted:
        st.caption(f"{correct} / {total} correct in all. {assisted} correct answer{'s' if assisted != 1 else ''} used the notes "
                   f"and {'are' if assisted != 1 else 'is'} recorded as assisted, so not counted.")
    if pct < PASS:
        st.error(f"Failed: {pct}% is below {PASS}%. Review the explanations below, then retake.")
    st.button("Retake", key=f"quiz_again_{chapter['book']['id']}", on_click=_start, args=(run_key, chapter))
    for pos, r in enumerate(run["review"], 1):
        q = qs[r["q"]]
        with st.container(border=True):
            st.markdown(f"{'✅' if r['ok'] else '❌'} **{pos}.** {q['q']}" + ("  \n📖 :orange[notes used]" if r["notes"] else ""))
            if q["kind"] == "mc":
                if not r["ok"]:
                    st.markdown("Your answer: " + (q["o"][r["chosen"]] if r["chosen"] is not None else "(none)"))
                st.markdown("Answer: " + q["o"][q["a"]])
            if not r["ok"] and q["e"]:                          # explanations are shown for what was missed
                st.info(q["e"])
