"""Grading breakdown and letter-grade scale of each course, read from its syllabus.

Kept per course in data/syllabus/<course id>.json:
  {"book": Library id of the syllabus file, "page": page of the grading policy, "note": text,
   "rows": [{"item", "percent", "kind"}], "scale": [{"grade", "rule"}]}
"kind" says where "your score so far" comes from: "homework", "midterms", "final", "exams", "event:<event title>" or null."""
import json

from database import BASE_DIR

DIR = BASE_DIR / "data" / "syllabus"


def load(course_id):
    try:
        return json.loads((DIR / f"{course_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(course_id, data):
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"{course_id}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def score(kind, homework, events):
    """Average fraction (0-1) of the graded items behind a grading row, or None when nothing is graded yet.
    homework and events are lists of rows with score/points (homework_pairs, events)."""
    def avg(items):
        marks = [i["score"] / i["points"] for i in items if i.get("score") is not None and i.get("points")]
        return sum(marks) / len(marks) if marks else None

    kind = kind or ""
    if kind == "homework":
        return avg(homework)
    if kind == "midterms":
        return avg([e for e in events if "midterm" in e["title"].lower()])
    if kind == "final":
        return avg([e for e in events if "final" in e["title"].lower()])
    if kind == "exams":
        return avg(events)
    if kind.startswith("event:"):
        return avg([e for e in events if e["title"].lower() == kind[6:].lower()])
    return None


DEFAULT_SCALE = [("A", 90), ("B", 80), ("C", 70), ("D", 60)]


def standing(data, homework, events):
    """(percent, share of the course graded so far) from the graded parts, each weighted as the syllabus says; None when nothing
    is graded. The weights of the graded parts are rescaled to 100%, so it is the grade you have if the rest goes the same way."""
    got = weight = total = 0.0
    for r in data.get("rows") or []:
        total += r["percent"]
        value = score(r.get("kind"), homework, events)
        if value is not None:
            got += r["percent"] * value
            weight += r["percent"]
    if not weight:
        return None
    return got / weight * 100, weight / total if total else 0


def letter(percent, data):
    """(letter, assumed): the letter for a percent from the syllabus scale; assumed is True when the syllabus gives none and the
    usual 90 / 80 / 70 / 60 cutoffs are used."""
    scale = [(r["grade"], r["min"]) for r in (data.get("scale") or []) if r.get("min") is not None]
    assumed = not scale
    for grade, low in sorted(scale or DEFAULT_SCALE, key=lambda x: -x[1]):
        if percent >= low:
            return grade, assumed
    return "F" if assumed else "Below " + min(scale or DEFAULT_SCALE, key=lambda x: x[1])[0], assumed


def _parts(data, homework, events):
    """The graded parts as [(weight fraction, [(score fraction or None, group)])], group "hw", "exam" or "other"; None = not graded."""
    total = sum(r["percent"] for r in data.get("rows") or []) or 1
    out = []
    for r in data.get("rows") or []:
        kind = r.get("kind") or ""
        if kind == "homework":
            items = [(h["score"] / h["points"] if h.get("score") is not None and h.get("points") else None, "hw") for h in homework]
        else:
            if kind == "midterms":
                pool = [e for e in events if "midterm" in e["title"].lower()]
            elif kind == "final":
                pool = [e for e in events if "final" in e["title"].lower()]
            elif kind == "exams":
                pool = list(events)
            elif kind.startswith("event:"):
                pool = [e for e in events if e["title"].lower() == kind[6:].lower()]
            else:
                pool = []
            group = "exam" if kind else "other"
            items = [(e["score"] / e["points"] if e.get("score") is not None and e.get("points") else None, group) for e in pool]
        out.append((r["percent"] / total, items or [(None, "exam" if kind else "other")]))
    return out


def needed(data, homework, events, target):
    """The least average, as a fraction, the work still to come must earn to reach `target` (a fraction of the whole grade).
    Returns (every_item, exams_only): every remaining item at the same score; or the remaining exams and other parts at one score
    while the remaining homework stays at your homework average. None when nothing is left to grade, or no homework to compare."""
    parts = _parts(data, homework, events)
    base = left = 0.0
    base_hw = left_other = 0.0
    graded_hw = [v for w, items in parts for v, g in items if g == "hw" and v is not None]
    hw_avg = sum(graded_hw) / len(graded_hw) if graded_hw else None
    for w, items in parts:
        n = len(items)
        got = sum(v for v, g in items if v is not None)
        pending = [g for v, g in items if v is None]
        base += w * got / n
        left += w * len(pending) / n
        pending_hw = sum(1 for g in pending if g == "hw")
        base_hw += w * (got + (pending_hw * hw_avg if hw_avg is not None else 0)) / n
        left_other += w * (len(pending) - pending_hw) / n
    if left <= 0:
        return None
    every = (target - base) / left
    exams = (target - base_hw) / left_other if left_other > 0 and hw_avg is not None else None
    return every, exams, hw_avg
