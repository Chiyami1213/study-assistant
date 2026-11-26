"""The quizzes of a course, without Streamlit and without Qt: which chapters and parts a note has, how a quiz is started, scored and saved for later. The classic page (`views/quiz_view.py`) and the native one
(`qtui/pages/quiz_page.py`) both use it. See quiz_view.py for what the quizzes do (modes, notes and hints, the three scores)."""
import json
import random
import re
import time
from datetime import datetime
from functools import lru_cache

from core import crud, settings
from core.database import DATA_DIR, data_path
from library import browse
from study import macros
from study import quizgen
from study import quizparts
from study import quizzes

PASS, STRONG = 60, 80          # percent: below PASS the quiz is failed
MODE_END, MODE_EACH = "Check After Finishing", "Check After Each Answer"

PART_LABEL = {"concept": "Conceptual Questions", "speed": "Speed Round", "guided": "Guided Practice", "closed": "Closed-Book Round"}      # the quizzes of a chapter; their scores count in total

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


@lru_cache(maxsize=64)
def _questions(path, mtime):
    # only real questions: the open "think of an answer" items of some notes are replaced by written multiple-choice ones; a guide that has only open (essay) questions keeps them
    found = quizzes.parse(open(path, encoding="utf-8", errors="replace").read())
    return [x for x in found if x["kind"] == "mc"] or [x for x in found if x["kind"] == "open"]


@lru_cache(maxsize=64)
def _extra_parts(path, mtime):
    """{"speed": {questions, n, limit} or None, "guided": [step questions of the guided practice, in order], "closed": [equations of the closed-book round]} of a note."""
    text = open(path, encoding="utf-8", errors="replace").read()
    try:
        defs = macros.from_html(text)
        out = {"speed": None, "guided": [], "closed": []}
        for key, read in (("speed", lambda: quizparts.speed(text, defs)), ("guided", lambda: [q for g in quizparts.guided(text, defs) for q in g["questions"]]),
                          ("closed", lambda: quizparts.closed(text, defs))):
            try:
                out[key] = read()
            except Exception:                          # a quiz written in a form this app does not know is left out (the others stay), never an error on the course page
                pass
        return out
    except Exception:
        return {"speed": None, "guided": [], "closed": []}


def chapter_parts(chapter):
    """{part: questions} of the quizzes a chapter has: conceptual questions, the speed round (the whole bank; a round asks `n` of them) and the guided practice (its steps)."""
    out = {}
    if chapter["questions"]:
        out["concept"] = chapter["questions"]
    if chapter.get("speed"):
        out["speed"] = chapter["speed"]["questions"]
    if chapter.get("guided"):
        out["guided"] = chapter["guided"]
    if chapter.get("closed"):
        out["closed"] = chapter["closed"]
    return out


def speed_limit(chapter):
    """Seconds of a speed round of this chapter: the seconds per question of Settings > Quizzes times the questions of the round (so rounds differ in length), or the guide's own limit when Settings says so."""
    q = settings.get_quiz()
    return chapter["speed"]["limit"] if q["use_guide_time"] else chapter["speed"]["n"] * q["speed_seconds"]


def _count(chapter, part, qs):
    """How many questions a quiz asks: a speed round asks `n` of its bank."""
    return chapter["speed"]["n"] if part == "speed" else len(qs)


@lru_cache(maxsize=64)
def _sections(path, mtime):
    return quizgen.sections_of(open(path, encoding="utf-8", errors="replace").read())


def course_chapters(course):
    """[{book, name, questions, path}] for the course's HTML notes that have questions, in lecture order."""
    out = []
    for b in sorted((b for b in crud.list_books() if course["id"] in b["course_ids"] and crud.in_part(b["title"], course.get("part"))
                     and b["kind"] in ("Notes", "Lecture Notes") and b["pdf_path"].lower().endswith((".html", ".htm"))),
                    key=browse._course_order):
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
        if qs or extra["speed"] or extra["guided"] or extra["closed"]:
            out.append({"book": b, "questions": qs, "path": path, "speed": extra["speed"], "guided": extra["guided"], "closed": extra["closed"],
                        "name": (f"Lec {b['lecture']} · " if b.get("lecture") else "") + b["title"]})
    return out




def _pct(correct, total):
    return round(100 * correct / total) if total else 0


def _level(pct):
    return ("Strong", "done") if pct >= STRONG else ("Passed", "open") if pct >= PASS else ("Failed", "late")


def _unaided(s):
    return s["last_correct"] - s["last_assisted"]



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




def _hint_for(q):
    """(hint text, index of the option crossed out). A question may carry its own hint; one wrong option always goes."""
    wrong = [i for i in range(len(q["o"])) if i != q["a"]]
    gone = random.Random(q["q"]).choice(wrong) if wrong else None
    own = (q.get("h") or "").strip()
    text = own or ("Think about the section named above." if q.get("tag") else "")
    return (text + " One wrong option is crossed out.").strip(), gone




def _is_right(q, res):
    if not res:
        return False
    return res.get("chosen") == q["a"] if q["kind"] == "mc" else bool(res.get("got"))


def book_questions(book, seed):
    """The quiz questions of an HTML note (the same set the Quiz tab asks), in an order that depends on `seed` (the same all session, another next time), or None when it has none."""
    for cid in book["course_ids"]:
        course = crud.get_course(cid)
        for ch in course_chapters(course) if course else []:
            if ch["book"]["id"] == book["id"]:
                rng = random.Random(seed * 1000003 + book["id"])
                return [shuffled(q, rng) for q in ch["questions"]]
    return None


def new_run(chapter, part="concept", mode=MODE_END):
    """A quiz of one part of a chapter, started: the questions (their options in a new order), the order they are asked in, and nothing answered yet."""
    pool = chapter_parts(chapter).get(part) or []
    if part == "speed":
        pool = random.sample(pool, chapter["speed"]["n"])             # a round asks some of the bank, in a new draw each time
    order = list(range(len(pool)))
    rng = random.Random()
    qs = [shuffled(q, rng) for q in pool]                           # this attempt's options, in a new random order
    if part != "guided":                                            # the steps of a guided practice keep their order
        random.shuffle(order)
    run = {"book": chapter["book"]["id"], "order": order, "phase": "run", "res": {}, "part": part,
           "stamp": random.randint(1, 10 ** 9), "qs": qs, "mode": "each" if mode == MODE_EACH or part in ("speed",) else "end"}      # a speed round marks each answer at once
    if part == "speed":
        run.update(t0=time.time(), limit=speed_limit(chapter))
    return run


def finish_run(course_id, chapter, run):
    """Scores a quiz, records the attempt and puts the review into `run` (phase 'done')."""
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
    crud.add_quiz_attempt(course_id, chapter["book"]["id"], correct, len(review), json.dumps(review), assisted, notes_used, hints_used, part=part)
    saved = saved_progress(course_id, chapter["book"]["id"], part)
    if saved and saved.get("stamp") == run.get("stamp"):
        _drop_progress(course_id, chapter["book"]["id"], part)   # this quiz was resumed and is now finished
    run.update(phase="done", correct=correct, assisted=assisted, notes_used=notes_used, hints_used=hints_used, review=review)
    return run
