"""Grading breakdown and letter-grade scale of each course, read from its syllabus.

Kept per course in data/syllabus/<course id>.json:
  {"book": Library id of the syllabus file, "page": page of the grading policy, "note": text,
   "rows": [{"item", "percent", "kind"}], "scale": [{"grade", "rule"}]}
"kind" says where "your score so far" comes from: "homework", "midterms", "final", "exams", "event:<event title>" or null."""
import json
import re

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


# ---------- Built from the syllabus file when it is added to the Library ----------
_NAME = r"[A-Z][\w.'\u2019-]*(?:\s+[A-Z][\w.'\u2019-]*){0,3}"


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _kind_of(label):
    """Where 'your score so far' of a grading row comes from, read from its name."""
    t = label.lower()
    if re.search(r"homework|\bhw\b|\bps\b|problem set|assignment", t):
        return "homework"
    m = re.search(r"(midterm|mid-term)\s*(?:exam|test|quiz)?\s*#?\s*(\d)", t)
    if m:
        return f"event:Midterm {m.group(2)}"
    if "midterm" in t or "mid-term" in t:
        return "midterms"
    if "final" in t:
        return "final"
    if re.search(r"exam|test|quiz", t):
        return "exams"
    return None


def _label(raw):
    raw = _clean(raw).strip(" :-\u2013*(")
    raw = re.sub(r"(?i)^.*\b(?:based on|consists? of|made up of|comprised of)\s+", "", raw)
    raw = re.sub(r"(?i)^(?:and|the|a)\s+", "", raw)
    raw = re.sub(r"(?i)\s+(?:of|is|are|worth|will be|counts?)$", "", raw).strip()
    if raw.upper() == "PS":
        return "Problem Sets (PS)"
    if raw.upper() == "HW":
        return "Homework (HW)"
    return raw[:1].upper() + raw[1:]


_COUNTS = {"two": 2, "three": 3, "four": 4, "2": 2, "3": 3, "4": 4}
_ROW = re.compile(r"(?P<label>[A-Za-z][A-Za-z0-9 ./&*'\u2019()-]{1,40}?)\s*[:\-\u2013(]?\s*(?P<pct>\d{1,3}(?:\.\d+)?)\s*%(?=(?P<after>[^\n]{0,14}))")


def _grade_rows(text):
    """The parts of the grade [{item, percent, kind}] from the first place that lists parts adding up to about 100%, and the index
    of that place. Reads 'Homework 25%', 'Homework: 40% of course grade', 'Final Exam' / '50%' on the next line and
    'assignments (30%) and two quizzes (35% each)'."""
    starts = [m.start() for m in re.finditer(r"(?i)grad(?:e|es|ing)\b", text)][:12] or [0]
    for start in starts:
        rows, total = [], 0.0
        window = re.sub(r"(?i)\(?\s*@?\s*[\d.]+\s*%\s*each\s*\)?", "", text[start:start + 1200])
        for m in _ROW.finditer(window):
            label = _label(m.group("label"))
            pct = float(m.group("pct"))
            if not label or len(label) < 2 or re.fullmatch(r"(?i)\W*(?:above|below|and above|or above|grade|to|a|b|c|d|f)\W*", label) or pct > 100:
                continue
            if re.search(r"\d\s*/\s*\d", label) or re.match(r"(?i)or\b", label):
                rows, total = None, 0.0
                break
            if re.search(r"(?i)\b(will|each|be|weighted|counted|count|if|you|your|scor\w*|are|is|than|less|more|at least)\b", label) \
                    and not re.fullmatch(r"(?i)(?:comprehensive |final |midterm |first |second |third |online |written |in-class )*exams?(?: \d)?", label):
                rows, total = None, 0.0                                   # a sentence, not a name of a part: not a grading table
                break
            word = label.split()[0].lower() if label.split() else ""
            n = _COUNTS.get(word, 1) if "each" in m.group("after").lower() else 1
            if n > 1:
                base = re.sub(r"(?i)(?:zzes|(?<=[^s])ses|s)$", lambda m: {"zzes": "zz", "ses": "s"}.get(m.group(0).lower(), ""), " ".join(label.split()[1:])).strip() or label
                parts = [f"{base[:1].upper() + base[1:]} {i + 1}" for i in range(n)]
            else:
                parts = [label]
            for part in parts:
                if total < 99.5:
                    rows.append({"item": part, "percent": int(pct) if pct == int(pct) else pct, "kind": _kind_of(part)})
                    total += pct
            if total >= 99.5:
                break
        if rows and 95 <= total <= 105:
            return rows, start
    return [], None


def _scale(text):
    """Letter-grade cutoffs: lines like 'A 90-100' or 'B: 80%', and sentences like '90% or above for an A grade, 80% to 89% for a B'."""
    found = {}
    for line in text.split("\n"):
        m = re.match(r"^\s*([ABCDF][+-]?)\s*[:=\-\u2013]?\s*(\d{2,3}(?:\.\d+)?)\s*%?\s*(?:(?:-|\u2013|to|and above|or above|\+)\s*(\d{2,3}(?:\.\d+)?)?\s*%?)?\s*$", line)
        if m:
            nums = [float(x) for x in (m.group(2), m.group(3)) if x]
            found.setdefault(m.group(1), (min(nums), _clean(line)))
    for m in re.finditer(r"(\d{2,3}(?:\.\d+)?)\s*%(?:\s*(?:or above|and above|or higher|\+))?(?:\s*(?:to|-|\u2013)\s*(\d{2,3}(?:\.\d+)?)\s*%)?\s*(?:for|=|:)?\s*(?:an?\s+|the\s+)?[\u2018'\"\u201c]?([ABCDF][+-]?)[\u2019'\"\u201d]?(?:\s+grade)?\b",
                         text):
        nums = [float(x) for x in (m.group(1), m.group(2)) if x]
        found.setdefault(m.group(3), (min(nums), _clean(m.group(0))))
    for m in re.finditer(r"(?m)^\s*(\d{2,3}(?:\.\d+)?)\s*[\u2013-]\s*(\d{2,3}(?:\.\d+)?)\s*%?\s*:?\s+([ABCDF][+-]?)\s*$", text):
        found.setdefault(m.group(3), (min(float(m.group(1)), float(m.group(2))), _clean(m.group(0))))
    for m in re.finditer(r"(?m)^\s*([ABCDF][+-]?)\s+(\d{2,3}(?:\.\d+)?)\s*[\u2013-]\s*(\d{2,3}(?:\.\d+)?)\s*%?\s*$", text):
        found.setdefault(m.group(1), (min(float(m.group(2)), float(m.group(3))), _clean(m.group(0))))
    scale = [{"grade": g, "rule": rule, "min": int(low) if low == int(low) else low} for g, (low, rule) in found.items()]
    return sorted(scale, key=lambda r: -r["min"]) if len(scale) >= 2 else []


def parse(pages):
    """What the syllabus says, from its text (one string per page): instructor and e-mail, the parts of the grade with their percent,
    the letter-grade scale, how it is curved, and the page of the grading policy. Anything not found is left out."""
    text = "\n".join(pages)
    out = {}
    m = re.search(r"(Professor|Prof\.|Instructor|Dr\.)[: ]+(" + _NAME + ")", text)
    if m:
        name = re.sub(r"(?:\s+(?:Office|Email|E-mail|Phone|Tel|Room|Contact|Hours|Dept|Department|School))+.*$", "", _clean(m.group(2)))
        name = " ".join(w for w in name.split() if w.lower() not in ("information", "name", "contact", "instructor", "evaluations", "of", "the"))
        if len(name.split()) >= 2 or (name and "." in name):
            out["instructor"] = ("Prof. " if m.group(1).startswith("Prof") else "Dr. " if m.group(1).startswith("Dr") else "") + name
        near = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text[m.end():m.end() + 400])
        if near:
            out["email"] = near.group(0)
    out["rows"], start = _grade_rows(text)
    out["scale"] = _scale(text)
    curve = next((s for s in re.split(r"(?<=[.!?])\s+", _clean(text)) if re.search(r"\bcurv", s, re.I)), None)
    if curve:
        out["curve"] = re.sub(r"^\(\w\)\s*", "", curve)[:300]
    out["page"] = 1
    if start is not None:
        pos = 0
        for i, pg in enumerate(pages):
            if pos <= start < pos + len(pg) + 1:
                out["page"] = i + 1
                break
            pos += len(pg) + 1
    return out


def auto_build(course_ids, book_id, path):
    """Add the syllabus section of a course page when a syllabus file is added to the Library: read the file and keep what it says in
    data/syllabus/<course id>.json. A course whose syllabus data already comes from this file is left as it is, and nothing that could
    not be read replaces what a course already has. Returns the course ids that were built."""
    import pymupdf
    try:
        doc = pymupdf.open(str(path))
        pages = [p.get_text() for p in doc]
    except Exception:
        return []
    found = parse(pages)
    built = []
    for cid in course_ids or []:
        have = load(cid)
        if have and have.get("book") == book_id:
            continue
        if have and not (found.get("rows") or found.get("scale")):
            continue
        data = {"book": book_id, "page": found.get("page", 1), "rows": found.get("rows") or [], "scale": found.get("scale") or []}
        if not data["rows"]:
            data["note"] = "The grading breakdown could not be read from the syllabus; open it to see the grading policy."
        for k in ("instructor", "email", "curve"):
            if found.get(k):
                data[k] = found[k]
        save(cid, data)
        built.append(cid)
    return built
