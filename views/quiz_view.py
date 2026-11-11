"""Course Quiz tab and the Understanding block of the Overview.

A chapter's quiz joins two kinds of questions: conceptual checks written for each section of the HTML note
(quizzes/<course>/<note>.json, see quizgen.py) and the note's own Self-check questions. Answers are given one per
question. A finished quiz can be opened again from the quiz list (View): every attempt keeps its questions, the answers given
and the explanations. A retake adds a new attempt and keeps the earlier ones; the history is deleted only when the user asks
(Clear Attempt History, after a confirmation). Two modes are offered when a quiz is started: "Check After Finishing" (nothing is marked until the quiz is finished;
then the score is shown, with the explanation for every question that was missed) and "Check After Each Answer" (an answer is
marked as soon as it is given, with its explanation, and then cannot be changed; Check Notes and Hint are off for it). Below 60%
the quiz is failed.

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
import re
import quizgen
import quizzes
from database import BASE_DIR, data_path
from views import library_view

PASS, STRONG = 60, 80          # percent: below PASS the quiz is failed
MODE_END, MODE_EACH = "Check After Finishing", "Check After Each Answer"


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
        path = data_path(b["pdf_path"])
        if not path.exists():
            continue
        secs = _sections(str(path), path.stat().st_mtime)
        defs = macros.from_html(path.read_text(encoding="utf-8", errors="replace"))
        secs = [{**x, "title": quizzes._md(x["title"], defs)} for x in secs]      # titles as Markdown with TeX math
        own = []
        text = path.read_text(encoding="utf-8", errors="replace")
        subs = {m.group(1): (m.group(2), quizzes._md(re.sub(r"<[^>]+>", "", m.group(3)), defs))          # subsections: "s1-1" -> ("1.1", title)
                for m in re.finditer(r'data-t="([^"]+)"[^>]*><span class="n">([\d.]+)</span>(.*?)</a>', text, re.S)}
        for qq in _questions(str(path), path.stat().st_mtime):
            if qq.get("section"):                                       # the note names the subsection each question tests
                top = re.match(r"s\d+", qq["section"])
                num, title = subs.get(qq["section"], (None, None))
                label = f"{num} · {title}" if num else (secs and next((x["title"] for x in secs if x["id"] == (top.group(0) if top else "")), "Quiz"))
                own.append({**qq, "sec": qq["section"], "tag": (label or "Quiz") + (" (textbook)" if qq.get("textbook") else ""),
                            "_own": True})
                continue
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
        if own and all(qq.get("_own") for qq in own):                   # the note's own quiz replaces the written section checks
            made = []
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
    mode = st.session_state.get(run_key + "_mode") or MODE_END
    st.session_state[run_key + "_modepref"] = mode                  # remembered for the next quiz (the radio is not drawn during a quiz)
    st.session_state[run_key] = {"book": chapter["book"]["id"], "order": order, "phase": "run", "res": {},
                                 "stamp": random.randint(1, 10 ** 9), "mode": "each" if mode == MODE_EACH else "end"}


def _open_view(run_key, chapter):
    st.session_state[run_key] = {"book": chapter["book"]["id"], "phase": "view", "order": []}


def _clear_history(run_key, course_id, book_id=None):
    crud.clear_quiz_attempts(course_id, book_id)
    if book_id is not None:
        st.session_state.pop(run_key, None)             # the view had nothing left to show
    st.session_state["quiz_cleared"] = "Attempt history cleared." if book_id is None else "Attempt history of this quiz cleared."


def _leave(run_key):
    st.session_state.pop(run_key, None)


def _entry(run_key, qi):
    return st.session_state[run_key]["res"].setdefault(qi, {"chosen": None, "notes": False, "hint": False})


def _pick(run_key, qi, oi):
    e = _entry(run_key, qi)
    if st.session_state[run_key].get("mode") == "each" and e["chosen"] is not None:
        return                                          # marked at once, so the answer is final
    e["chosen"] = oi                                    # otherwise the last option pressed is the answer


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
    if st.session_state.get("quiz_cleared"):
        st.toast(st.session_state.pop("quiz_cleared"))
    pref = st.session_state.get(run_key + "_modepref") or MODE_END
    st.radio("Checking Mode", [MODE_END, MODE_EACH], index=[MODE_END, MODE_EACH].index(pref), horizontal=True, key=run_key + "_mode",
             help="check after finishing: nothing is marked until you finish. check after each answer: an answer is marked right away "
                  "and cannot be changed; check notes and hint are not available")
    st.caption(f"Pick a chapter or lecture. Below {PASS}% the quiz is failed. Check Notes and Hint are allowed (not in the mode that "
               f"checks each answer) but recorded.")
    for c in chapters:
        s = stats.get(c["book"]["id"])
        name, meta, pill, view, go = st.columns([4.4, 2.6, 1.6, 1.2, 1.3], vertical_alignment="center")
        name.markdown(f"**{c['name']}**  \n{len(c['questions'])} questions"
                      + (f" ({c['made']} section checks)" if c["made"] else ""))
        if s:
            pct = _pct(_unaided(s), s["last_total"])
            label, css = _level(pct)
            meta.markdown(f"Last {_unaided(s)}/{s['last_total']} unaided ({pct}%)  \nBest {s['best']}% · {s['attempts']} attempts")
            pill.markdown(f'<span class="dl-pill {css}">{label}</span>', unsafe_allow_html=True)
        else:
            meta.caption("Not taken yet")
        if s:
            view.button("View", key=f"quiz_view_{course['id']}_{c['book']['id']}", width="stretch", icon=":material/visibility:",
                        on_click=_open_view, args=(run_key, c), help="opens a finished attempt again: the questions, your answers and the explanations")
        go.button("Retake" if s else "Start", key=f"quiz_go_{course['id']}_{c['book']['id']}", type="primary" if not s else "secondary",
                  width="stretch", on_click=_start, args=(run_key, c))
    if stats:
        st.caption("Every finished quiz is kept: a retake adds an attempt and the earlier ones stay. View opens them again.")
        _clear_box(run_key, course)


def _clear_box(run_key, course, book_id=None):
    """Clear Attempt History with a confirmation: the only way recorded attempts are ever deleted."""
    what = "this quiz" if book_id is not None else "every quiz of this course"
    with st.popover("Clear Attempt History", icon=":material/delete_sweep:"):
        st.markdown(f"Delete all recorded attempts of {what}? The scores in Understanding go back to Not Taken. This cannot be undone.")
        st.button("Yes, Clear Attempt History", key=f"quiz_clear_{course['id']}_{book_id}", type="primary",
                  on_click=_clear_history, args=(run_key, course["id"], book_id))


def _is_right(q, res):
    if not res:
        return False
    return res.get("chosen") == q["a"] if q["kind"] == "mc" else bool(res.get("got"))


def _finish(course, chapter, run):
    qs = chapter["questions"]
    review = []
    for qi in run["order"]:
        res = run["res"].get(qi) or {}
        q = qs[qi]
        review.append({"q": qi, "chosen": res.get("chosen"), "ok": _is_right(q, res), "notes": bool(res.get("notes")),
                       "hint": bool(res.get("hint")),
                       "snap": {"kind": q["kind"], "q": q["q"], "o": q["o"], "a": q["a"], "e": q.get("e") or "", "tag": q.get("tag")}})   # kept so the attempt can be viewed later
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
        locked = run.get("mode") == "each" and q["kind"] == "mc" and res.get("chosen") is not None       # marked at once; final
        with st.container(border=True, key=f"qcard_{cid}_{run['stamp']}_{qi}"):
            st.markdown(f"**{pos}.** {q['q']}")
            if q.get("tag"):
                st.caption(q["tag"])
            if q["kind"] == "mc":
                with st.container(horizontal=True, gap="medium", key=f"qopts_{cid}_{run['stamp']}_{qi}"):
                    for oi, text in enumerate(q["o"]):
                        st.button(text, key=f"{prefix}_{oi}", on_click=_pick, args=(run_key, qi, oi), disabled=locked)
                if locked:
                    base = f".stApp .st-key-{prefix}_%d button[data-testid^='stBaseButton']"
                    sel = base % q["a"]
                    styles += (f"{sel}, {sel}:focus, {sel}:focus:not(:active), {sel}:disabled {{opacity: 1 !important; border: 2px solid #2e9e5b !important; background: rgba(46, 158, 91, 0.26) !important;}}"
                               f"{sel} p::before {{content: '✓  '; font-weight: 700;}}")
                    if res["chosen"] != q["a"]:
                        sel = base % res["chosen"]
                        styles += (f"{sel}, {sel}:focus, {sel}:focus:not(:active), {sel}:disabled {{opacity: 1 !important; border: 2px solid #d64545 !important; background: rgba(214, 69, 69, 0.26) !important;}}"
                                   f"{sel} p::before {{content: '✗  '; font-weight: 700;}}")
                elif res.get("chosen") is not None:
                    sel = f".stApp .st-key-{prefix}_{res['chosen']} button[data-testid^='stBaseButton']"
                    styles += (f"{sel}, {sel}:hover {{border: 2px solid var(--accent) !important; background: rgba(76, 141, 255, 0.24) !important;}}"
                               f"{sel} p::before {{content: '✓  '; font-weight: 700;}}")
            if locked:
                if res["chosen"] == q["a"]:
                    st.markdown(":green[**Correct.**]")
                else:
                    st.markdown(":red[**Not correct.**] The answer is: " + q["o"][q["a"]])
                if q.get("e"):
                    st.info(q["e"])
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
                          icon=":material/menu_book:", on_click=_use_notes, args=(run_key, qi), disabled=locked,
                          help="opens the note on the right. it is recorded that you used it")
                if q["kind"] == "mc":
                    st.button("Hint", key=f"{prefix}_hint", type="tertiary", icon=":material/lightbulb:",
                              on_click=_use_hint, args=(run_key, qi), disabled=bool(res.get("hint")) or locked,
                              help="gives a hint and crosses out one wrong option. it is recorded that you used it")
    return styles


def _run(course, chapter, run, run_key):
    qs, order, cid = chapter["questions"], run["order"], course["id"]
    head, back = st.columns([6, 1.6], vertical_alignment="center")
    head.subheader(chapter["name"])
    back.button("Back To Quizzes" if run["phase"] in ("done", "view") else "Leave Quiz", key=f"quiz_back_{cid}", width="stretch",
                on_click=_leave, args=(run_key,))
    if run["phase"] == "done":
        _done(chapter, run, run_key)
        return
    if run["phase"] == "view":
        _view(course, chapter, run_key)
        return

    res_all = run["res"]
    answered = sum(1 for qi in order if (res_all.get(qi) or {}).get("chosen") is not None)
    notes = sum(1 for qi in order if (res_all.get(qi) or {}).get("notes"))
    hints = sum(1 for qi in order if (res_all.get(qi) or {}).get("hint"))
    if run.get("mode") == "each":
        right = sum(1 for qi in order if _is_right(qs[qi], res_all.get(qi)))
        st.caption(f"{answered} of {len(order)} answered · {right} right so far · {notes} with notes · {hints} with hints (both recorded). "
                   f"Press an option to answer; it is marked at once and cannot be changed.")
    else:
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
    total, correct, assisted = run.get("total") or len(run["order"]), run["correct"], run["assisted"]
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
    if not run["review"]:
        st.caption("The answers of this attempt were not saved, so only the score can be shown.")
    for pos, r in enumerate(run["review"], 1):
        q = r.get("snap") or (qs[r["q"]] if r["q"] < len(qs) else None)
        if q is None:
            continue
        with st.container(border=True):
            st.markdown(f"{'✅' if r['ok'] else '❌'} **{pos}.** {q['q']}" + ("  \n" + ("📖 :orange[notes used]  " if r["notes"] else "") + ("💡 :orange[hint used]" if r["hint"] else "")
                                                                  if r["notes"] or r["hint"] else ""))
            if q["kind"] == "mc":
                if not r["ok"]:
                    st.markdown("Your answer: " + (q["o"][r["chosen"]] if r["chosen"] is not None else "(none)"))
                st.markdown("Answer: " + q["o"][q["a"]])
            if q.get("e"):
                if not r["ok"]:                                 # explanations are shown for what was missed ...
                    st.info(q["e"])
                else:                                           # ... and can be opened for what was right
                    with st.expander("Explanation"):
                        st.markdown(q["e"])


def _view(course, chapter, run_key):
    """A finished attempt opened again: the score and every question with the answer given and the explanation."""
    from datetime import datetime, timezone
    attempts = crud.quiz_attempts(course["id"], chapter["book"]["id"])
    if not attempts:
        st.caption("This quiz has no finished attempts yet.")
        return

    def label(a):
        try:
            when = datetime.fromisoformat(a["taken_at"]).replace(tzinfo=timezone.utc).astimezone().strftime("%b %d, %Y %I:%M %p")
        except (TypeError, ValueError):
            when = str(a["taken_at"])
        return f"{when} · {a['correct']} / {a['total']}"

    by_id = {a["id"]: a for a in attempts}
    pick = st.selectbox("Attempt", list(by_id), format_func=lambda i: label(by_id[i]), key=f"quiz_viewpick_{course['id']}_{chapter['book']['id']}")
    a = by_id[pick]
    try:
        review = json.loads(a["answers"]) if a["answers"] else []
    except ValueError:
        review = []
    _clear_box(run_key, course, chapter["book"]["id"])
    _done(chapter, {"correct": a["correct"], "assisted": a["assisted"], "notes_used": a["notes_used"], "hints_used": a["hints_used"],
                    "review": review, "total": a["total"], "order": []}, run_key)
