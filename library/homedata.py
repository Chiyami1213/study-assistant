"""What the Home page shows, without Streamlit and without Qt: the week of the term, the unfinished homework, exams, labs and projects soonest first, what was completed lately, and marking work done or not done
(the Task List follows). The classic page (`views/home_view.py`) and the native one (`qtui/pages/home_page.py`) both use it."""
import re
from datetime import date, timedelta

from core import crud
from core import settings

def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _term_stats(today):
    """[(big text, small text)] for the term: current week number (holidays count) and days until winter break.

    Winter break starts the day after the last day of finals (the end of the exam period)."""
    sem = settings.get_semester()
    start, exam_end = date.fromisoformat(sem["start"]), date.fromisoformat(sem["exam_end"])
    break_start = exam_end + timedelta(days=1)
    day = lambda d: f"{d.strftime('%a, %b')} {d.day}"
    if today < start:
        return [(_plural((start - today).days, "Day"), f"Until Classes Start · {day(start)}")]
    if today >= break_start:
        return [("Winter Break", f"Started {day(break_start)}")]
    week = (today - start).days // 7 + 1           # week 1 is the week classes start; holiday weeks are counted
    total = (exam_end - start).days // 7 + 1
    return [(f"Week {week}", f"Of {total}"),
            (_plural((break_start - today).days, "Day"), f"Until Winter Break · {day(break_start)}")]


EXAM_RE = re.compile(r"midterm|final|exam", re.I)


SHOWN = 8


TASK_KINDS = ("Lab", "Project")                  # work that is not homework or an exam but is due: a lab report, a project (the planner's tasks of these categories)


def _tasks(by_id, done):
    """[(day, time, title, kind, course, id)] of the Lab and Project tasks of the active courses that are done (or not): the due day and time in the term's zone."""
    from planner import store, task_store
    zone = store.get_term().zone
    out = []
    for t in task_store.list_tasks():
        if t.category in TASK_KINDS and t.course_id in by_id and t.is_done == done and t.due:
            local = t.due.astimezone(zone)
            out.append((local.date().isoformat(), local.strftime("%H:%M"), t.title, t.category, by_id[t.course_id], t.id))
    return out


def _when(day, time):
    d = date.fromisoformat(day)
    return f"{d.strftime('%a, %b')} {d.day}" + (f" · {time}" if time else "")


def _countdown(day, today):
    n = (date.fromisoformat(day) - today).days
    if n < 0:
        return "Overdue", "late"
    if n == 0:
        return "Today", "late"
    if n == 1:
        return "Tomorrow", "open"
    return f"In {n} Days", "open"


def _complete(kind, item_id):
    from planner import linkdone, task_store
    if kind in TASK_KINDS:
        task_store.set_done(item_id, True)
        return
    if kind == "Homework":
        crud.set_homework_status(item_id, "verified")
    else:
        crud.set_event_done(item_id, True)
    linkdone.from_home(kind, item_id, True)                  # the same piece of work in the Task List is done too


def _undo(kind, item_id):
    from planner import linkdone, task_store
    if kind in TASK_KINDS:
        task_store.set_done(item_id, False)
        return
    if kind == "Homework":
        crud.set_homework_status(item_id, "todo")
    else:
        crud.set_event_done(item_id, False)
    linkdone.from_home(kind, item_id, False)


def upcoming_items(courses, homework, today=None):
    """[(day, time, title, kind, course, covers, id)] of the unfinished homework (overdue ones first), the coming midterms and finals, and the open labs and projects of the active courses, soonest first."""
    today = today or date.today()
    by_id = {c["id"]: c for c in courses}
    items = [(h["due_date"], h.get("due_time") or "", h["title"], "Homework", by_id[cid], None, h["id"])
             for cid, rows in homework.items() for h in rows if h["status"] != "verified" and h["due_date"]]
    items += [(e["date"], e.get("time") or "", e["title"], "Exam", by_id[e["course_id"]], e.get("covers"), e["id"])
              for e in crud.list_events(today.isoformat(), "2100-12-31")
              if e["course_id"] in by_id and EXAM_RE.search(e["title"]) and not e.get("done")]
    items += [(day, time, title, kind, c, None, tid) for day, time, title, kind, c, tid in _tasks(by_id, False)]
    items.sort(key=lambda x: (x[0], x[1]))
    return items


def completed_items(courses, homework, today=None):
    """[(day, title, kind, course, id)] recently completed (due in the last week or still to come), the earliest first."""
    today = today or date.today()
    since = (today - timedelta(days=7)).isoformat()
    by_id = {c["id"]: c for c in courses}
    rows = [(h["due_date"], h["title"], "Homework", by_id[cid], h["id"]) for cid, hs in homework.items() for h in hs
            if h["status"] == "verified" and h["due_date"] and h["due_date"] >= since]
    rows += [(e["date"], e["title"], "Exam", by_id[e["course_id"]], e["id"]) for e in crud.list_events(since, "2100-12-31")
             if e["course_id"] in by_id and EXAM_RE.search(e["title"]) and e.get("done")]
    rows += [(day, title, kind, c, tid) for day, _time, title, kind, c, tid in _tasks(by_id, True) if day >= since]
    return sorted(rows, key=lambda r: (r[0], r[1]))


def progress(courses, homework):
    """[(course, homework done, homework total)] for the Progress list."""
    return [(c, sum(x["status"] == "verified" for x in homework[c["id"]]), len(homework[c["id"]])) for c in courses]
