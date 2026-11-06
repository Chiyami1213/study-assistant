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
