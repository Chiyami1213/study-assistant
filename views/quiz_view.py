"""Course Quiz tab and the Understanding block of the Overview.

A chapter's quiz is the questions of the HTML note itself (its Quiz or Self-check, see quizzes.py). Answers are given one per
question. Save For Later keeps a quiz that is not finished (the questions in their order, the answers so far, the notes and hints
used) in quiz_progress/ of the data folder; the quiz list then offers Resume. A finished quiz can be opened again from the quiz list (View): every attempt keeps its questions, the answers given
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
import time
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from core import crud, settings
from study import htmlnotes
from study import macros
import re
from study import quizgen
from study import quizparts
from study import quizzes
from core.database import BASE_DIR, DATA_DIR, data_path
from views import library_view

PASS, STRONG = 60, 80          # percent: below PASS the quiz is failed
MODE_END, MODE_EACH = "Check After Finishing", "Check After Each Answer"
from study.quizrun import (PASS, STRONG, MODE_END, MODE_EACH, PART_LABEL, shuffled, _questions, _extra_parts, chapter_parts, speed_limit, _count, _sections, course_chapters,
                           _pct, _level, _unaided, PROGRESS_DIR, _progress_file, saved_progress, _save_progress, _drop_progress, _hint_for, _is_right, _ANCHOR, _LETTER_REF, _NUMBER)
from study import quizrun
def book_questions(book):
    """The quiz questions of an HTML note (the same set the Quiz tab asks), or None if it has none."""
    return quizrun.book_questions(book, st.session_state.setdefault("_quiz_seed", random.randint(1, 10 ** 9)))      # the same order all session, another next time


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
            pct, label, css, detail = 0, "Not Taken", "none", f"{sum(_count(c, p, q) for p, q in chapter_parts(c).items())} questions in {len(chapter_parts(c))} quiz{'zes' if len(chapter_parts(c)) != 1 else ''}"
        rows += (f'<div class="und-row"><div class="und-name">{html.escape(c["name"])}'
                 f'<div class="und-detail">{detail}</div></div>'
                 f'<div class="und-bar"><i class="{css}" style="width:{pct}%"></i></div>'
                 f'<div class="und-pct">{pct}%</div><span class="dl-pill {css}">{label}</span></div>')
    st.markdown(f'<div class="dl-list">{rows}</div>', unsafe_allow_html=True)


# ---------- Quiz tab ----------
def _start(run_key, chapter, part="concept"):
    mode = st.session_state.get(run_key + "_mode") or MODE_END
    st.session_state[run_key + "_modepref"] = mode                  # remembered for the next quiz (the radio is not drawn during a quiz)
    st.session_state[run_key] = quizrun.new_run(chapter, part, mode)


def _open_view(run_key, chapter):
    st.session_state[run_key] = {"book": chapter["book"]["id"], "phase": "view", "order": []}


# ---------- Save for later: a quiz that is not finished is kept in the data folder and can be resumed ----------
def _save_for_later(run_key, course_id):
    run = st.session_state.get(run_key)
    if run and run.get("phase") == "run":
        _save_progress(course_id, run)
        st.session_state.pop(run_key, None)
        st.session_state["quiz_notice"] = "Quiz saved. Resume it from the Quiz tab."


def _resume(run_key, course_id, book_id, part="concept"):
    run = saved_progress(course_id, book_id, part)
    if run:
        st.session_state[run_key] = run


def _discard_saved(course_id, book_id, part="concept"):
    _drop_progress(course_id, book_id, part)
    st.session_state["quiz_notice"] = "Saved quiz discarded."


def _clear_history(run_key, course_id, book_id=None):
    crud.clear_quiz_attempts(course_id, book_id)
    if book_id is not None:
        st.session_state.pop(run_key, None)             # the view had nothing left to show
    st.session_state["quiz_notice"] = "Attempt history cleared." if book_id is None else "Attempt history of this quiz cleared."


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
    if st.session_state.get("quiz_notice"):
        st.toast(st.session_state.pop("quiz_notice"))
    pref = st.session_state.get(run_key + "_modepref") or MODE_END
    st.radio("Checking Mode", [MODE_END, MODE_EACH], index=[MODE_END, MODE_EACH].index(pref), horizontal=True, key=run_key + "_mode",
             help="check after finishing: nothing is marked until you finish. check after each answer: an answer is marked right away "
                  "and cannot be changed; check notes and hint are not available")
    st.caption(f"Pick a chapter or lecture. Each chapter has up to four quizzes (conceptual questions, a speed round, guided practice, a closed-book round of equations to write from memory): take them separately; their scores count together in the total. "
               f"Below {PASS}% the total is failed. Check Notes and Hint are allowed (not in the mode that checks each answer, and not in the speed round) but recorded.")
    for c in chapters:
        s = stats.get(c["book"]["id"])
        parts = chapter_parts(c)
        name, meta, pill, view = st.columns([4.4, 3.4, 1.6, 1.2], vertical_alignment="center")
        n_all = sum(_count(c, p, q) for p, q in parts.items())
        name.markdown(f"**{c['name']}**  \n{n_all} questions in {len(parts)} quiz{'zes' if len(parts) != 1 else ''}")
        if s:
            pct = _pct(_unaided(s), s["last_total"])
            label, css = _level(pct)
            meta.markdown(f"Total {_unaided(s)}/{s['last_total']} unaided ({pct}%)  \nBest {s['best']}% · {s['attempts']} attempts")
            pill.markdown(f'<span class="dl-pill {css}">{label}</span>', unsafe_allow_html=True)
        else:                                                    # at the far right of the row, where the View button of a taken quiz would be
            view.markdown('<div style="text-align:right; opacity:0.6; font-size:0.875rem;">Not taken yet</div>', unsafe_allow_html=True)
        if s:
            view.button("View", key=f"quiz_view_{course['id']}_{c['book']['id']}", width="stretch", icon=":material/visibility:",
                        on_click=_open_view, args=(run_key, c), help="opens a finished attempt again: the questions, your answers and the explanations")
        cells = st.columns([2] * len(parts) + [max(1, 6 - 2 * len(parts))], vertical_alignment="top")
        for (part, qs), cell in zip(parts.items(), cells):
            ps = (s or {}).get("parts", {}).get(part)
            saved = saved_progress(course["id"], c["book"]["id"], part)
            unit = {"guided": "steps", "closed": "equations"}.get(part, "questions")
            cell.caption(f"**{PART_LABEL[part]}** · {_count(c, part, qs)} {unit}" + (f" · last {ps['last_correct'] - ps['last_assisted']}/{ps['last_total']}" if ps else " · not taken")
                         + (f" · {speed_limit(c)} s" if part == "speed" else ""))
            suffix = "" if part == "concept" else f"_{part}"
            cell.button("Retake" if ps else "Start", key=f"quiz_go_{course['id']}_{c['book']['id']}{suffix}", type="primary" if not ps and not saved else "secondary",
                        width="stretch", on_click=_start, args=(run_key, c, part))
        for part in parts:
            saved = saved_progress(course["id"], c["book"]["id"], part)
            if saved:
                suffix = "" if part == "concept" else f"_{part}"
                done_n = sum(1 for v in saved["res"].values() if v.get("chosen") is not None or v.get("got") is not None)
                when = saved.get("saved_at", "")[:16].replace("T", " ")
                with st.container(horizontal=True, vertical_alignment="center", gap="small", key=f"quiz_saved_{course['id']}_{c['book']['id']}{suffix}"):
                    st.caption(f":material/bookmark: Saved {PART_LABEL[part].lower()}: {done_n} of {len(saved['order'])} answered"
                               f" · {'checked after each answer' if saved.get('mode') == 'each' else 'checked after finishing'}"
                               + (f" · saved {when}" if when else ""))
                    st.button("Resume", key=f"quiz_resume_{course['id']}_{c['book']['id']}{suffix}", type="primary", icon=":material/play_arrow:",
                              on_click=_resume, args=(run_key, course["id"], c["book"]["id"], part))
                    st.button("Discard Saved Quiz", key=f"quiz_drop_{course['id']}_{c['book']['id']}{suffix}", type="tertiary",
                              on_click=_discard_saved, args=(course["id"], c["book"]["id"], part),
                              help="deletes the saved, unfinished quiz. finished attempts are not touched")
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


def _finish(course, chapter, run):
    quizrun.finish_run(course["id"], chapter, run)


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
    qs, order, res_all, styles = run.get("qs") or chapter["questions"], run["order"], run["res"], ""
    for pos, qi in enumerate(order, 1):
        q, res = qs[qi], res_all.get(qi) or {}
        prefix = f"qo_{cid}_{run['stamp']}_{qi}"
        locked = run.get("mode") == "each" and q["kind"] == "mc" and res.get("chosen") is not None       # marked at once; final
        with st.container(border=True, key=f"qcard_{cid}_{run['stamp']}_{qi}"):
            if q.get("ctx"):                                       # a guided step: the problem it belongs to (open at the first step of each problem)
                first = pos == 1 or qs[order[pos - 2]].get("group") != q.get("group")
                with st.expander("Problem", expanded=first):
                    st.markdown(q["ctx"])
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
                    if (q.get("ofb") or [None] * 9)[res["chosen"]]:
                        st.warning(q["ofb"][res["chosen"]])        # why the option chosen is wrong
                if q.get("e"):
                    st.info(q["e"])
            if q["kind"] != "mc":                                  # an open (essay) question: think of an answer, look at the model answer, then say whether you had it
                with st.expander("Show the model answer"):
                    st.markdown(q.get("e") or "(The page gives no model answer.)")
                with st.container(horizontal=True, gap="small", key=f"qself_{cid}_{run['stamp']}_{qi}"):
                    st.button("I Had It", key=f"{prefix}_got", icon=":material/check:", type="primary" if res.get("got") is True else "secondary", on_click=_self_grade, args=(run_key, qi, True))
                    st.button("Not Yet", key=f"{prefix}_miss", icon=":material/close:", type="primary" if res.get("got") is False else "secondary", on_click=_self_grade, args=(run_key, qi, False))
            if q["kind"] == "mc" and res.get("hint"):
                text, gone = _hint_for(q)
                st.markdown(f":orange[**Hint used. This is recorded.**] {text}")
                if gone is not None:
                    styles += (f".stApp .st-key-{prefix}_{gone} button[data-testid^='stBaseButton'] "
                               f"{{opacity: 0.4; text-decoration: line-through; pointer-events: none;}}")
            if res.get("notes"):
                st.markdown(":orange[**Notes used for this question. This is recorded.**]")
            if run.get("part") in ("speed", "closed"):           # a speed round is answered on instinct and a closed-book round with the notes shut: no notes, no hint
                continue
            with st.container(horizontal=True, gap="small", key=f"qhelp_{cid}_{run['stamp']}_{qi}"):
                st.button("Show Notes" if res.get("notes") else "Check Notes", key=f"{prefix}_notes", type="tertiary",
                          icon=":material/menu_book:", on_click=_use_notes, args=(run_key, qi), disabled=locked,
                          help="opens the note on the right. it is recorded that you used it")
                if q["kind"] == "mc":
                    st.button("Hint", key=f"{prefix}_hint", type="tertiary", icon=":material/lightbulb:",
                              on_click=_use_hint, args=(run_key, qi), disabled=bool(res.get("hint")) or locked,
                              help="gives a hint and crosses out one wrong option. it is recorded that you used it")
    return styles


@st.fragment(run_every=1)
def _speed_clock(course, chapter, run_key):
    """The countdown of a speed round, redrawn every second; when it reaches zero the round is scored (what was not answered is missed)."""
    run = st.session_state.get(run_key)
    if not run or run.get("phase") != "run" or run.get("part") != "speed":
        return
    left = run["limit"] - (time.time() - run["t0"])
    if left <= 0:
        _finish(course, chapter, run)
        st.rerun()
    st.markdown(f"**:material/timer: {int(left) // 60}:{int(left) % 60:02d}**" + ("  :red[hurry]" if left < 15 else ""))


def _run(course, chapter, run, run_key):
    qs, order, cid = run.get("qs") or chapter["questions"], run["order"], course["id"]
    head, save, back = st.columns([5, 1.8, 1.6], vertical_alignment="center")
    part = run.get("part", "concept")
    head.subheader(chapter["name"] + (f" · {PART_LABEL[part]}" if part != "concept" else ""))
    if run["phase"] == "run" and part != "speed":
        save.button("Save For Later", key=f"quiz_save_{cid}", width="stretch", icon=":material/bookmark_add:",
                    on_click=_save_for_later, args=(run_key, cid),
                    help="keeps this quiz as it is (the questions, your answers, the notes and hints used) so you can resume it later")
    back.button("Back To Quizzes" if run["phase"] in ("done", "view") else "Leave Quiz", key=f"quiz_back_{cid}", width="stretch",
                on_click=_leave, args=(run_key,))
    if run["phase"] == "done":
        _done(chapter, run, run_key)
        return
    if run["phase"] == "view":
        _view(course, chapter, run_key)
        return

    res_all = run["res"]
    answered = sum(1 for qi in order if (res_all.get(qi) or {}).get("chosen") is not None or (res_all.get(qi) or {}).get("got") is not None)
    notes = sum(1 for qi in order if (res_all.get(qi) or {}).get("notes"))
    hints = sum(1 for qi in order if (res_all.get(qi) or {}).get("hint"))
    if part == "closed":
        st.caption(f"{answered} of {len(order)} answered. Notes shut: write each equation on paper, open the model answer to check, then press I Had It only if you had it exactly, or Not Yet.")
    elif run.get("mode") == "each":
        right = sum(1 for qi in order if _is_right(qs[qi], res_all.get(qi)))
        st.caption(f"{answered} of {len(order)} answered · {right} right so far · {notes} with notes · {hints} with hints (both recorded). "
                   f"Press an option to answer; it is marked at once and cannot be changed.")
    else:
        st.caption(f"{answered} of {len(order)} answered · {notes} with notes · {hints} with hints (both recorded). Press an "
                   f"option to choose it; you can change it until you finish. Answers are marked at the end.")
    if part == "speed":
        _speed_clock(course, chapter, run_key)
        st.caption("Answer on instinct. Time is up after the limit; the questions not answered then are missed.")
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
    st.button("Retake", key=f"quiz_again_{chapter['book']['id']}", on_click=_start, args=(run_key, chapter, run.get("part", "concept")))
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
                if not r["ok"] and r["chosen"] is not None and (q.get("ofb") or [None] * 9)[r["chosen"]]:
                    st.warning(q["ofb"][r["chosen"]])
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
        return f"{when} · {PART_LABEL.get(a['part'], a['part'])} · {a['correct']} / {a['total']}"

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
