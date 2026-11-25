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

from core import crud
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
PART_LABEL = {"concept": "Conceptual Questions", "speed": "Speed Round", "guided": "Guided Practice"}      # the three quizzes of a chapter; their scores count in total

# The written questions put the right answer second most of the time, so the options are shuffled for every attempt. A question is left in
# its order when an option points at the others ("All of the above", "Both A and B", "option C") or when its choices are a row of numbers;
# an "It depends" style option stays last.
_ANCHOR = re.compile(r"(all|none|both|neither).{0,25}(above|these|the others|of them)|[A-D]\s+(and|&|or)\s+[A-D]|"
                     r"depends on|cannot be determined|not enough information|none of the", re.I)
_LETTER_REF = re.compile(r"(option|choice|answer)\s+\(?[A-Da-d]\)?(?![a-z])", re.I)
_NUMBER = re.compile(r"[\d.,\s\-−+]+")


def shuffled(q, rng):
    """The question with its options in a random order (the index of the right one follows); unchanged when shuffling would break it."""
    o = q.get("o") or []
    if q.get("noshuffle") or q.get("kind") != "mc" or len(o) < 2 or q.get("a") is None or _LETTER_REF.search(q["q"] + " " + (q.get("e") or "")):
        return q
    pinned = [i for i, x in enumerate(o) if _ANCHOR.search(x)]
    if pinned and pinned != list(range(len(o) - len(pinned), len(o))):
        return q                                          # an option that refers to the others has to stay where it is
    free = [i for i in range(len(o)) if i not in pinned]
    if len(free) < 2 or all(_NUMBER.fullmatch(o[i].replace("$", "").strip()) for i in free):
        return q
    rng.shuffle(free)
    order = free + pinned
    return {**q, "o": [o[i] for i in order], "a": order.index(q["a"])}


@st.cache_data(show_spinner=False, max_entries=64)
def _questions(path, mtime):
    # only real questions: the open "think of an answer" items of some notes are replaced by written multiple-choice ones
    return [x for x in quizzes.parse(open(path, encoding="utf-8", errors="replace").read()) if x["kind"] == "mc"]


@st.cache_data(show_spinner=False, max_entries=64)
def _extra_parts(path, mtime):
    """{"speed": {questions, n, limit} or None, "guided": [step questions of the guided practice, in order]} of a note: its speed round and its guided numerical practice."""
    text = open(path, encoding="utf-8", errors="replace").read()
    defs = macros.from_html(text)
    return {"speed": quizparts.speed(text, defs), "guided": [q for g in quizparts.guided(text, defs) for q in g["questions"]]}


def chapter_parts(chapter):
    """{part: questions} of the quizzes a chapter has: conceptual questions, the speed round (the whole bank; a round asks `n` of them) and the guided practice (its steps)."""
    out = {}
    if chapter["questions"]:
        out["concept"] = chapter["questions"]
    if chapter.get("speed"):
        out["speed"] = chapter["speed"]["questions"]
    if chapter.get("guided"):
        out["guided"] = chapter["guided"]
    return out


def _count(chapter, part, qs):
    """How many questions a quiz asks: a speed round asks `n` of its bank."""
    return chapter["speed"]["n"] if part == "speed" else len(qs)


@st.cache_data(show_spinner=False, max_entries=64)
def _sections(path, mtime):
    return quizgen.sections_of(open(path, encoding="utf-8", errors="replace").read())


def course_chapters(course):
    """[{book, name, questions, path}] for the course's HTML notes that have questions, in lecture order."""
    out = []
    for b in sorted((b for b in crud.list_books() if course["id"] in b["course_ids"] and crud.in_part(b["title"], course.get("part"))
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
        labels = {x["id"]: x.get("label") for x in secs}
        ref = lambda n: f"{b['lecture']}.{n}" if b.get("lecture") and n else f"§{n}" if n else ""     # "10.2": lecture, section
        for qq in own:
            if qq.get("_num"):
                qq["tag"] = (labels.get(qq.get("sec")) or ref(qq["_num"])) + " · " + qq["tag"].replace("Self-check · ", "") + " (self-check)"
        qs = own
        extra = _extra_parts(str(path), path.stat().st_mtime)
        if qs or extra["speed"] or extra["guided"]:
            out.append({"book": b, "questions": qs, "path": path, "speed": extra["speed"], "guided": extra["guided"],
                        "name": (f"Lec {b['lecture']} · " if b.get("lecture") else "") + b["title"]})
    return out


def book_questions(book):
    """The quiz questions of an HTML note (the same set the Quiz tab asks), or None if it has none."""
    for cid in book["course_ids"]:
        course = crud.get_course(cid)
        for ch in course_chapters(course) if course else []:
            if ch["book"]["id"] == book["id"]:
                seed = st.session_state.setdefault("_quiz_seed", random.randint(1, 10 ** 9))      # the same order all session, another next time
                rng = random.Random(seed * 1000003 + book["id"])
                return [shuffled(q, rng) for q in ch["questions"]]
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
            pct, label, css, detail = 0, "Not Taken", "none", f"{sum(_count(c, p, q) for p, q in chapter_parts(c).items())} questions in {len(chapter_parts(c))} quiz{'zes' if len(chapter_parts(c)) != 1 else ''}"
        rows += (f'<div class="und-row"><div class="und-name">{html.escape(c["name"])}'
                 f'<div class="und-detail">{detail}</div></div>'
                 f'<div class="und-bar"><i class="{css}" style="width:{pct}%"></i></div>'
                 f'<div class="und-pct">{pct}%</div><span class="dl-pill {css}">{label}</span></div>')
    st.markdown(f'<div class="dl-list">{rows}</div>', unsafe_allow_html=True)


# ---------- Quiz tab ----------
def _start(run_key, chapter, part="concept"):
    pool = chapter_parts(chapter).get(part) or []
    if part == "speed":
        pool = random.sample(pool, chapter["speed"]["n"])             # a round asks some of the bank, in a new draw each time
    order = list(range(len(pool)))
    rng = random.Random()
    qs = [shuffled(q, rng) for q in pool]                           # this attempt's options, in a new random order
    if part != "guided":                                            # the steps of a guided practice keep their order
        random.shuffle(order)
    mode = st.session_state.get(run_key + "_mode") or MODE_END
    st.session_state[run_key + "_modepref"] = mode                  # remembered for the next quiz (the radio is not drawn during a quiz)
    run = {"book": chapter["book"]["id"], "order": order, "phase": "run", "res": {}, "part": part,
           "stamp": random.randint(1, 10 ** 9), "qs": qs, "mode": "each" if mode == MODE_EACH or part == "speed" else "end"}      # a speed round marks each answer at once
    if part == "speed":
        run.update(t0=time.time(), limit=chapter["speed"]["limit"])
    st.session_state[run_key] = run


def _open_view(run_key, chapter):
    st.session_state[run_key] = {"book": chapter["book"]["id"], "phase": "view", "order": []}


# ---------- Save for later: a quiz that is not finished is kept in the data folder and can be resumed ----------
PROGRESS_DIR = DATA_DIR / "quiz_progress"


def _progress_file(course_id, book_id, part="concept"):
    return PROGRESS_DIR / (f"{course_id}_{book_id}.json" if part == "concept" else f"{course_id}_{book_id}_{part}.json")


def saved_progress(course_id, book_id, part="concept"):
    """The saved, unfinished run of a quiz (of one part) as a run dict, or None."""
    try:
        d = json.loads(_progress_file(course_id, book_id, part).read_text(encoding="utf-8"))
        d["res"] = {int(k): v for k, v in d["res"].items()}
        d["phase"] = "run"
        assert d["order"] and d["qs"]
        return d
    except (OSError, ValueError, KeyError, AssertionError, TypeError):
        return None


def _save_progress(course_id, run):
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    keep = {k: run[k] for k in ("book", "order", "res", "stamp", "qs", "mode", "part") if k in run}
    keep["saved_at"] = datetime.now().isoformat(timespec="seconds")
    f = _progress_file(course_id, run["book"], run.get("part", "concept"))
    tmp = f.with_name(f.name + ".part")
    tmp.write_text(json.dumps(keep), encoding="utf-8")
    tmp.replace(f)


def _drop_progress(course_id, book_id, part="concept"):
    try:
        _progress_file(course_id, book_id, part).unlink()
    except OSError:
        pass


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
    if st.session_state.get("quiz_notice"):
        st.toast(st.session_state.pop("quiz_notice"))
    pref = st.session_state.get(run_key + "_modepref") or MODE_END
    st.radio("Checking Mode", [MODE_END, MODE_EACH], index=[MODE_END, MODE_EACH].index(pref), horizontal=True, key=run_key + "_mode",
             help="check after finishing: nothing is marked until you finish. check after each answer: an answer is marked right away "
                  "and cannot be changed; check notes and hint are not available")
    st.caption(f"Pick a chapter or lecture. Each chapter has up to three quizzes (conceptual questions, a speed round, guided practice): take them separately; their scores count together in the total. "
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
        else:
            meta.caption("Not taken yet")
        if s:
            view.button("View", key=f"quiz_view_{course['id']}_{c['book']['id']}", width="stretch", icon=":material/visibility:",
                        on_click=_open_view, args=(run_key, c), help="opens a finished attempt again: the questions, your answers and the explanations")
        cells = st.columns([2] * len(parts) + [max(1, 6 - 2 * len(parts))], vertical_alignment="top")
        for (part, qs), cell in zip(parts.items(), cells):
            ps = (s or {}).get("parts", {}).get(part)
            saved = saved_progress(course["id"], c["book"]["id"], part)
            unit = "steps" if part == "guided" else "questions"
            cell.caption(f"**{PART_LABEL[part]}** · {_count(c, part, qs)} {unit}" + (f" · last {ps['last_correct'] - ps['last_assisted']}/{ps['last_total']}" if ps else " · not taken")
                         + (f" · {int(c['speed']['limit'])} s" if part == "speed" else ""))
            suffix = "" if part == "concept" else f"_{part}"
            cell.button("Retake" if ps else "Start", key=f"quiz_go_{course['id']}_{c['book']['id']}{suffix}", type="primary" if not ps and not saved else "secondary",
                        width="stretch", on_click=_start, args=(run_key, c, part))
        for part in parts:
            saved = saved_progress(course["id"], c["book"]["id"], part)
            if saved:
                suffix = "" if part == "concept" else f"_{part}"
                done_n = sum(1 for v in saved["res"].values() if v.get("chosen") is not None)
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


def _is_right(q, res):
    if not res:
        return False
    return res.get("chosen") == q["a"] if q["kind"] == "mc" else bool(res.get("got"))


def _finish(course, chapter, run):
    qs = run.get("qs") or chapter["questions"]
    review = []
    for qi in run["order"]:
        res = run["res"].get(qi) or {}
        q = qs[qi]
        review.append({"q": qi, "chosen": res.get("chosen"), "ok": _is_right(q, res), "notes": bool(res.get("notes")),
                       "hint": bool(res.get("hint")),
                       "snap": {"kind": q["kind"], "q": q["q"], "o": q["o"], "a": q["a"], "e": q.get("e") or "", "tag": q.get("tag"), "ofb": q.get("ofb")}})   # kept so the attempt can be viewed later
    correct = sum(r["ok"] for r in review)
    assisted = sum(r["ok"] and (r["notes"] or r["hint"]) for r in review)       # right, but with notes or a hint
    notes_used, hints_used = sum(r["notes"] for r in review), sum(r["hint"] for r in review)
    part = run.get("part", "concept")
    crud.add_quiz_attempt(course["id"], chapter["book"]["id"], correct, len(review), json.dumps(review), assisted,
                          notes_used, hints_used, part=part)
    saved = saved_progress(course["id"], chapter["book"]["id"], part)
    if saved and saved.get("stamp") == run.get("stamp"):
        _drop_progress(course["id"], chapter["book"]["id"], part)   # this quiz was resumed and is now finished
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
            if q["kind"] == "mc" and res.get("hint"):
                text, gone = _hint_for(q)
                st.markdown(f":orange[**Hint used. This is recorded.**] {text}")
                if gone is not None:
                    styles += (f".stApp .st-key-{prefix}_{gone} button[data-testid^='stBaseButton'] "
                               f"{{opacity: 0.4; text-decoration: line-through; pointer-events: none;}}")
            if res.get("notes"):
                st.markdown(":orange[**Notes used for this question. This is recorded.**]")
            if run.get("part") == "speed":                       # a speed round is answered on instinct: no notes, no hint
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
