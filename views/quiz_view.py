"""Course Quiz tab and the Understanding block of the Overview.

A chapter's quiz joins two kinds of questions: conceptual checks written for each section of the HTML note
(quizzes/<course>/<note>.json, see quizgen.py) and the note's own Self-check questions. Answers are given one per
question and nothing is marked until the quiz is finished; then the score is shown, with the explanation for every
question that was missed. Below 60% the quiz is failed.

"Check Notes" opens the note at the question's section, and "Hint" gives a nudge (the question's own hint when it has one,
and always one wrong option crossed out). Using either is recorded for the question and the attempt: an answer made with
them is documented as assisted and does not count towards the unaided score, which is the score the Overview shows."""
import html
import json
import random

import streamlit as st
import streamlit.components.v1 as components

import crud
import htmlnotes
import macros
import quizgen
import quizzes
from database import BASE_DIR
from views import library_view

PASS, STRONG = 60, 80          # percent: below PASS the quiz is failed


@st.cache_data(show_spinner=False, max_entries=64)
def _questions(path, mtime):
    # only real questions: the open "think of an answer" items of some notes are replaced by written multiple-choice ones
    return [x for x in quizzes.parse(open(path, encoding="utf-8", errors="replace").read()) if x["kind"] == "mc"]


@st.cache_data(show_spinner=False, max_entries=64)
def _sections(path, mtime):
    return quizgen.sections_of(open(path, encoding="utf-8", errors="replace").read())


def course_chapters(course):
    """[{book, name, questions, path}] for the course's HTML notes that have questions, in lecture order."""
    out = []
    for b in sorted((b for b in crud.list_books() if course["id"] in b["course_ids"]
                     and b["kind"] in ("Notes", "Lecture Notes") and b["pdf_path"].lower().endswith((".html", ".htm"))),
                    key=library_view._course_order):
        path = BASE_DIR / b["pdf_path"]
        if not path.exists():
            continue
        secs = _sections(str(path), path.stat().st_mtime)
        defs = macros.from_html(path.read_text(encoding="utf-8", errors="replace"))
        secs = [{**x, "title": quizzes._md(x["title"], defs)} for x in secs]      # titles as Markdown with TeX math
        own = []
        for qq in _questions(str(path), path.stat().st_mtime):          # the note's own questions: placed in the closest section
            sec = quizgen.match_section(qq["q"] + " " + " ".join(qq["o"]) + " " + qq["e"], secs)
            own.append({**qq, "sec": sec["id"] if sec else None, "tag": ("Self-check · " + sec["title"]) if sec else "Self-check",
                        "_num": sec["num"] if sec else None})
        made = quizgen.questions(quizgen.load(quizgen.path_for(course["code"] or course["name"], b["title"])))
        nums = {x["id"]: x["num"] for x in secs}
        labels = {x["id"]: x.get("label") for x in secs}
        ref = lambda n: f"{b['lecture']}.{n}" if b.get("lecture") and n else f"§{n}" if n else ""     # "10.2": lecture, section
        titles = {x["id"]: x["title"] for x in secs}
        for qq in made:
            qq["tag"] = (labels.get(qq.get("sec")) or ref(nums.get(qq.get("sec")))) + " · " + titles.get(qq.get("sec"), qq["tag"].lstrip("§ "))
        for qq in own:
            if qq.get("_num"):
                qq["tag"] = (labels.get(qq.get("sec")) or ref(qq["_num"])) + " · " + qq["tag"].replace("Self-check · ", "") + " (self-check)"
        qs = made + own
        if qs:
            out.append({"book": b, "questions": qs, "path": path, "made": len(made),
                        "name": (f"Lec {b['lecture']} · " if b.get("lecture") else "") + b["title"]})
    return out


def book_questions(book):
    """The quiz questions of an HTML note (the same set the Quiz tab asks), or None if it has none."""
    for cid in book["course_ids"]:
        course = crud.get_course(cid)
        for ch in course_chapters(course) if course else []:
            if ch["book"]["id"] == book["id"]:
                return ch["questions"]
    return None


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
            notes = ((f" · notes on {s['last_notes']}" if s["last_notes"] else "") + (f" · hints on {s['last_hints']}" if s["last_hints"] else ""))
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
    return st.session_state[run_key]["res"].setdefault(qi, {"chosen": None, "notes": False, "hint": False})


def _pick(run_key, qi, oi):
    _entry(run_key, qi)["chosen"] = oi                  # the last option pressed is the answer


def _use_notes(run_key, qi):
    _entry(run_key, qi)["notes"] = True                 # recorded for the whole attempt
    st.session_state[run_key]["panel"] = qi             # the note opens on the right half, at this question's section


def _use_hint(run_key, qi):
    _entry(run_key, qi)["hint"] = True                  # recorded for the whole attempt


def _hint_for(q):
    """(hint text, index of the option crossed out). A question may carry its own hint; one wrong option always goes."""
    wrong = [i for i in range(len(q["o"])) if i != q["a"]]
    gone = random.Random(q["q"]).choice(wrong) if wrong else None
    own = (q.get("h") or "").strip()
    text = own or ("Think about the section named above." if q.get("tag") else "")
    return (text + " One wrong option is crossed out.").strip(), gone


def _close_notes(run_key):
    st.session_state[run_key]["panel"] = None


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
               f"Check Notes and Hint are allowed but recorded.")
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
        review.append({"q": qi, "chosen": res.get("chosen"), "ok": _is_right(qs[qi], res), "notes": bool(res.get("notes")),
                       "hint": bool(res.get("hint"))})
    correct = sum(r["ok"] for r in review)
    assisted = sum(r["ok"] and (r["notes"] or r["hint"]) for r in review)       # right, but with notes or a hint
    notes_used, hints_used = sum(r["notes"] for r in review), sum(r["hint"] for r in review)
    crud.add_quiz_attempt(course["id"], chapter["book"]["id"], correct, len(review), json.dumps(review), assisted,
                          notes_used, hints_used)
    run.update(phase="done", correct=correct, assisted=assisted, notes_used=notes_used, hints_used=hints_used, review=review)


def _note_panel(chapter, q, run_key, qi):
    """The right half: the note, opened at the section of the question being answered (the top for the rest)."""
    with st.container(key="quiz_notes_pane"):
        head, close = st.columns([5, 1.4], vertical_alignment="center")
        head.markdown(f"**Notes** · {q.get('tag') or chapter['name']}")
        close.button("Close Notes", key="quiz_notes_close", width="stretch", on_click=_close_notes, args=(run_key,))
        st.caption("Using the notes or a hint is recorded: answers made with either do not count towards the unaided score.")
        text = chapter["path"].read_text(encoding="utf-8", errors="replace")
        components.html(htmlnotes.safe_html(text, q.get("sec")), height=700, scrolling=True)


def _cards(chapter, run, run_key, cid):
    """The question cards. Returns the CSS that shows each chosen option."""
    qs, order, res_all, styles = chapter["questions"], run["order"], run["res"], ""
    for pos, qi in enumerate(order, 1):
        q, res = qs[qi], res_all.get(qi) or {}
        prefix = f"qo_{cid}_{run['stamp']}_{qi}"
        with st.container(border=True, key=f"qcard_{cid}_{run['stamp']}_{qi}"):
            st.markdown(f"**{pos}.** {q['q']}")
            if q.get("tag"):
                st.caption(q["tag"])
            if q["kind"] == "mc":
                with st.container(horizontal=True, gap="medium", key=f"qopts_{cid}_{run['stamp']}_{qi}"):
                    for oi, text in enumerate(q["o"]):
                        st.button(text, key=f"{prefix}_{oi}", on_click=_pick, args=(run_key, qi, oi))
                if res.get("chosen") is not None:
                    sel = f".stApp .st-key-{prefix}_{res['chosen']} button[data-testid^='stBaseButton']"
                    styles += (f"{sel}, {sel}:hover {{border: 2px solid var(--accent) !important; background: rgba(76, 141, 255, 0.24) !important;}}"
                               f"{sel} p::before {{content: '✓  '; font-weight: 700;}}")
            if q["kind"] == "mc" and res.get("hint"):
                text, gone = _hint_for(q)
                st.markdown(f":orange[**Hint used. This is recorded.**] {text}")
                if gone is not None:
                    styles += (f".stApp .st-key-{prefix}_{gone} button[data-testid^='stBaseButton'] "
                               f"{{opacity: 0.4; text-decoration: line-through; pointer-events: none;}}")
            if res.get("notes"):
                st.markdown(":orange[**Notes used for this question. This is recorded.**]")
            with st.container(horizontal=True, gap="small", key=f"qhelp_{cid}_{run['stamp']}_{qi}"):
                st.button("Show Notes" if res.get("notes") else "Check Notes", key=f"{prefix}_notes", type="tertiary",
                          icon=":material/menu_book:", on_click=_use_notes, args=(run_key, qi),
                          help="opens the note on the right. it is recorded that you used it")
                if q["kind"] == "mc":
                    st.button("Hint", key=f"{prefix}_hint", type="tertiary", icon=":material/lightbulb:",
                              on_click=_use_hint, args=(run_key, qi), disabled=bool(res.get("hint")),
                              help="gives a hint and crosses out one wrong option. it is recorded that you used it")
    return styles


def _run(course, chapter, run, run_key):
    qs, order, cid = chapter["questions"], run["order"], course["id"]
    head, back = st.columns([6, 1.6], vertical_alignment="center")
    head.subheader(chapter["name"])
    back.button("Back To Quizzes" if run["phase"] == "done" else "Leave Quiz", key=f"quiz_back_{cid}", width="stretch",
                on_click=_leave, args=(run_key,))
    if run["phase"] == "done":
        _done(chapter, run, run_key)
        return

    res_all = run["res"]
    answered = sum(1 for qi in order if (res_all.get(qi) or {}).get("chosen") is not None)
    notes = sum(1 for qi in order if (res_all.get(qi) or {}).get("notes"))
    hints = sum(1 for qi in order if (res_all.get(qi) or {}).get("hint"))
    st.caption(f"{answered} of {len(order)} answered · {notes} with notes · {hints} with hints (both recorded). Press an "
               f"option to choose it; you can change it until you finish. Answers are marked at the end.")
    panel = run.get("panel")
    if panel is not None:                                # notes open: the questions on the left half, the note on the right
        left, right = st.columns(2, gap="medium")
        with right:
            _note_panel(chapter, qs[panel], run_key, panel)
    else:
        left = st.container()
    with left:
        styles = _cards(chapter, run, run_key, cid)
        if st.button("Finish And Score", key=f"quiz_finish_{cid}", type="primary"):
            _finish(course, chapter, run)
            st.rerun()
    if styles:
        st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)


def _done(chapter, run, run_key):
    qs = chapter["questions"]
    total, correct, assisted = len(run["order"]), run["correct"], run["assisted"]
    unaided = correct - assisted
    pct = _pct(unaided, total)
    label, css = _level(pct)
    st.markdown(f'<div class="und-score"><b>{unaided} / {total}</b><span>{pct}% unaided</span>'
                f'<span class="dl-pill {css}">{label}</span></div>', unsafe_allow_html=True)
    st.caption(f"Recorded for this attempt: notes used on {run['notes_used']} question{'s' if run['notes_used'] != 1 else ''}, "
               f"hints on {run['hints_used']}.")
    if assisted:
        st.caption(f"{correct} / {total} correct in all. {assisted} correct answer{'s' if assisted != 1 else ''} used the notes "
                   f"or a hint and {'are' if assisted != 1 else 'is'} recorded as assisted, so not counted.")
    if pct < PASS:
        st.error(f"Failed: {pct}% is below {PASS}%. Review the explanations below, then retake.")
    st.button("Retake", key=f"quiz_again_{chapter['book']['id']}", on_click=_start, args=(run_key, chapter))
    for pos, r in enumerate(run["review"], 1):
        q = qs[r["q"]]
        with st.container(border=True):
            st.markdown(f"{'✅' if r['ok'] else '❌'} **{pos}.** {q['q']}" + ("  \n" + ("📖 :orange[notes used]  " if r["notes"] else "") + ("💡 :orange[hint used]" if r["hint"] else "")
                                                                  if r["notes"] or r["hint"] else ""))
            if q["kind"] == "mc":
                if not r["ok"]:
                    st.markdown("Your answer: " + (q["o"][r["chosen"]] if r["chosen"] is not None else "(none)"))
                st.markdown("Answer: " + q["o"][q["a"]])
            if not r["ok"] and q["e"]:                          # explanations are shown for what was missed
                st.info(q["e"])
