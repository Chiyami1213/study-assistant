"""The Task List without Streamlit and without Qt: which tasks are shown (by course or personal, by search), in which order, and in which groups. The classic page (`views/tasklist_view.py`) and the
native one (`qtui/pages/tasklist_page.py`) both use it."""
from datetime import timedelta

from core import crud
from planner import tasks as T, timeutil

SORTS = ["Due Date", "Category", "Course", "Title", "Time Left", "Cushion"]


GROUPS = ["None", "Course", "Category", "Due Week"]


NO_COURSE = "Personal / No Course"


def course_label(courses, task):
    if task.personal:
        return "Personal"
    c = courses.get(task.course_id)
    return (crud.show_code(c["code"]) or c["name"]) if c else ""


def filter_tasks(tasks, courses, which="all", query="", show_done=False):
    """`which`: "all", "course:<id>" or "personal" (a personal task, or one with no course). `query`: part of the title, the course or the category."""
    out = []
    q = (query or "").strip().lower()
    for t in tasks:
        if t.is_done and not show_done:
            continue
        if which == "personal" and not (t.personal or t.course_id is None):
            continue
        if which.startswith("course:") and t.course_id != int(which.split(":")[1]):
            continue
        if q and q not in f"{t.title} {course_label(courses, t)} {t.category}".lower():
            continue
        out.append(t)
    return out


def sort_tasks(tasks, key="Due Date", descending=False, courses=None, cushions=None):
    """Sorted by the chosen key (ties by due date, then title). A task without a due date is always last when sorting by date. `cushions`: {task id: minutes of cushion};
    ascending puts the tightest first, a task with no cushion (no due date) last."""
    courses, cushions = courses or {}, cushions or {}
    keys = {"Due Date": None, "Category": lambda t: T.CATEGORIES.index(t.category), "Course": lambda t: course_label(courses, t).lower() or chr(0xFFFF),
            "Title": lambda t: t.title.lower(), "Time Left": lambda t: t.remaining_minutes, "Cushion": lambda t: cushions.get(t.id, 10 ** 9)}
    if key not in keys:
        raise ValueError(f"Sort by one of: {', '.join(SORTS)}.")
    if key == "Due Date":
        dated = sorted((t for t in tasks if t.due is not None), key=lambda t: (t.due, t.title.lower(), t.id), reverse=descending)
        return dated + sorted((t for t in tasks if t.due is None), key=lambda t: (t.title.lower(), t.id))
    tie = lambda t: (t.due is None, t.due.timestamp() if t.due else 0, t.title.lower(), t.id)
    return sorted(tasks, key=lambda t: (keys[key](t),) + tie(t), reverse=False) if not descending else \
        sorted(sorted(tasks, key=tie), key=keys[key], reverse=True)


def _week_start(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def group_tasks(tasks, group="None", courses=None, tz=None, today=None):
    """[(heading, [tasks])] in the order of `tasks` inside each group; the groups are ordered by course, category or week. "None": one group with no heading."""
    courses = courses or {}
    if group == "None":
        return [("", list(tasks))]
    buckets = {}
    for t in tasks:
        if group == "Course":
            label = course_label(courses, t) or NO_COURSE
            order = (label == NO_COURSE or label == "Personal", label.lower())
        elif group == "Category":
            label, order = t.category, T.CATEGORIES.index(t.category)
        elif group == "Due Week":
            if t.due is None:
                label, order = "No Due Date", (1, "")
            else:
                first = _week_start(timeutil.local_day(t.due, tz))
                this = _week_start(today) if today else None
                last = first + timedelta(days=6)
                label = ("This Week · " if first == this else "") + f"{first:%b} {first.day} – {last:%b} {last.day}"
                order = (0, first.isoformat())
        else:
            raise ValueError(f"Group by one of: {', '.join(GROUPS)}.")
        buckets.setdefault(label, (order, []))[1].append(t)
    return [(label, rows) for label, (order, rows) in sorted(buckets.items(), key=lambda kv: kv[1][0])]
