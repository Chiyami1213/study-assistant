"""What the course pages show, without Streamlit and without Qt: the order of courses, homework and exams with their dates and files, what is due next, the syllabus data. The classic page
(`views/courses_view.py`) and the native one (`qtui/pages/courses_page.py`) both use it."""
import re
from datetime import date

from core import crud
from library import syllabus

SORTS = ["Default", "Course Number", "Name", "Category", "Semester", "School", "Status"]


TERM_RANK = {"winter": 0, "spring": 1, "summer": 2, "fall": 3}


def _semester_key(course):
    """Newest semester first; unrecognized and blank semesters go last."""
    m = re.match(r"\s*(winter|spring|summer|fall)\s*(\d{4})", course["semester"] or "", re.I)
    return (0, -int(m.group(2)), -TERM_RANK[m.group(1).lower()]) if m else (1, 0, 0)


def _sorted_groups(courses, sort_by):
    """[(heading, courses)] - one unlabeled group for flat sorts, headed groups for label sorts."""
    if sort_by == "Course Number":
        return [("", sorted(courses, key=lambda c: (not c["code"], crud._natural_key(crud.show_code(c["code"]) or c["name"]))))]
    if sort_by == "Name":
        return [("", sorted(courses, key=lambda c: c["name"].lower()))]
    if sort_by == "Default":
        return [("", courses)]
    if sort_by == "Category":
        order = {name: i for i, name in enumerate(crud.all_categories())}
        key = lambda c: (order.get(c.get("category"), len(order)), crud._natural_key(crud.show_code(c["code"]) or c["name"]))
        label = lambda c: c.get("category") or "No category"
    elif sort_by == "Semester":
        key = lambda c: (_semester_key(c), crud._natural_key(crud.show_code(c["code"]) or c["name"]))
        label = lambda c: c["semester"] or "No semester"
    elif sort_by == "School":
        key = lambda c: (not c.get("school"), (c.get("school") or "").lower(), crud._natural_key(crud.show_code(c["code"]) or c["name"]))
        label = lambda c: c.get("school") or "No school"
    else:  # Status
        key = lambda c: (crud.STATUSES.index(crud.course_status(c)), crud._natural_key(crud.show_code(c["code"]) or c["name"]))
        label = crud.course_status
    groups = {}
    for c in sorted(courses, key=key):
        groups.setdefault(label(c), []).append(c)
    return list(groups.items())


def _when(day, time):
    """'Mon, Nov 9 · 22:00' (the year is added only when it is not the current year)."""
    if not day:
        return "No date"
    d = date.fromisoformat(day)
    text = f"{d.strftime('%a, %b')} {d.day}" + (f", {d.year}" if d.year != date.today().year else "")
    return text + (f" · {time}" if time else "")


def _homework_book(course_id, hw_title, kind="Homework"):
    """The Library homework file whose number matches this homework ("HW 4" -> the file numbered 4), or None."""
    num = re.search(r"\d+", crud.strip_part(hw_title))
    if not num:
        return None
    for b in crud.list_books():
        if b["kind"] == kind and course_id in b["course_ids"] and crud.part_tag(b["title"]) == crud.part_tag(hw_title):      # the same part of a merged course
            n = re.search(r"\d+", b.get("lecture") or crud.strip_part(b["title"]))
            if n and int(n.group()) == int(num.group()):
                return b
    return None


def _exam_book(course_id, event_title, kind="Exam", word=None):
    """The Library exam file of this course for an event like "Midterm 2" or "Final Exam" (same kind of exam, same number);
    with `word`, only a file whose title contains it ("Reflection", "Statistics")."""
    def key(text):
        t = crud.strip_part(text).lower()
        kind = "midterm" if re.search(r"mid[\s_\-]*term", t) else "final" if "final" in t else "exam"
        n = re.search(r"\d+", t)
        return kind, (n.group() if n else None), crud.part_tag(text)

    want = key(event_title)
    for b in crud.list_books():
        if (b["kind"] == kind and course_id in b["course_ids"] and key(b["title"]) == want and "practice" not in b["title"].lower()
                and (word is None or word.lower() in b["title"].lower())):
            return b
    return None


def _percent(items):
    """Average percentage of the graded items (score/points), or None when none is graded."""
    marks = [i["score"] / i["points"] for i in items if i.get("score") is not None and i.get("points")]
    return sum(marks) / len(marks) if marks else None


def _homework_status(h, today):
    if h["status"] == "verified":
        return "Done", "done"
    if not h["due_date"]:
        return "No Date", "none"
    if h["due_date"] < today:
        return "Overdue", "late"
    return "Open", "open"


def homework_groups(homework, today, finished=False):
    """(upcoming, not_graded, past) of a course's homework in date order. Not graded: handed in (marked done) and no grade yet, whatever its date,
    so Upcoming holds only what is still to do. Upcoming: not handed in and due today or later (or no date); a completed course has none.
    Past: the rest (due before today, or graded)."""
    def ungraded(h):
        return h["status"] == "verified" and (h.get("score") is None or not h.get("points"))

    not_graded = [h for h in homework if ungraded(h)]
    rest = [h for h in homework if not ungraded(h)]
    upcoming = [] if finished else [h for h in rest if not h["due_date"] or h["due_date"] >= today]
    past = [h for h in rest if h not in upcoming]
    return upcoming, not_graded, past


def _homework_items(course):
    return sorted((h for h in crud.list_homework(course["id"]) if crud.in_part(h["title"], course.get("part"))),
                  key=lambda h: (h["due_date"] or "9999-12-31", crud._natural_key(h["title"])))


def _exam_items(course):
    return sorted((e for e in crud.list_events("2000-01-01", "2100-12-31")
                   if e["course_id"] == course["id"] and re.search(r"midterm|final|exam", e["title"], re.I) and crud.in_part(e["title"], course.get("part"))),
                  key=lambda e: (e["date"], e.get("time") or ""))


def _syllabus_data(course):
    """The syllabus data of the course, or of the chosen part of a merged course (none while all parts are shown: each part has its own grading)."""
    if course.get("parts") and not course.get("part"):
        return None
    return syllabus.load(course["id"], course.get("part"))


def coming_up(course, today=None, limit=8):
    """What is due next in a course, from all three places it is kept: homework not yet graded, exams still ahead, and the Task List's open tasks.
    [(date text 'YYYY-MM-DD', time or '', title, kind)] in date order; a task that is the same work as a homework or an exam (same title) is listed once."""
    today = (today or date.today()).isoformat()
    rows, seen = [], set()
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    for h in _homework_items(course):
        if h["due_date"] and h["due_date"] >= today and h.get("score") is None and h["status"] != "verified":
            rows.append((h["due_date"], h.get("due_time") or "", h["title"], "Homework"))
            seen.add(norm(h["title"]))
    for e in _exam_items(course):
        if e["date"] >= today and e.get("score") is None:
            rows.append((e["date"], e.get("time") or "", e["title"], "Exam"))
            seen.add(norm(e["title"]))
    try:
        from planner import store as planner_store, task_store, timeutil
        zone = planner_store.get_term().zone
        for k in task_store.list_tasks(course_id=course["id"], include_done=False):
            if k.due is None:
                continue
            local = timeutil.to_local(k.due, zone)
            if local.date().isoformat() >= today and norm(k.title) not in seen:
                rows.append((local.date().isoformat(), local.strftime("%H:%M"), k.title, "Task"))
    except Exception:
        pass
    return sorted(rows, key=lambda r: (r[0], r[1], r[2]))[:limit]
