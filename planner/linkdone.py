"""Done in one place, done in the other. The Home page lists the homework (`homework_pairs`) and the exams (`events`) of a course and has a check button; the Task List has its own tasks (`tasks`).
A homework or an exam that has a task of the same course and title is the same piece of work, so marking one done (or open again) does the same for the other.
Touches the database (it is a store-level helper, not pure)."""
import re

from core import crud
from planner import task_store

HOMEWORK_STATES = ("verified", "todo")


def _key(title):
    return re.sub(r"\s+", "", title or "").lower()


def _tasks(course_id, title, categories):
    return [t for t in task_store.list_tasks() if t.course_id == course_id and t.category in categories and _key(t.title) == _key(title)]


def from_home(kind, item_id, done):
    """The Home page marked a homework ("Homework") or an exam ("Exam") done or open again: the same for its tasks. Returns how many tasks changed."""
    if kind == "Homework":
        rows = crud._all("SELECT course_id, title FROM homework_pairs WHERE id=?", (item_id,))
        categories = ("Homework",)
    else:
        rows = crud._all("SELECT course_id, title FROM events WHERE id=?", (item_id,))
        categories = ("Exam", "Quiz")
    if not rows or rows[0]["course_id"] is None:
        return 0
    n = 0
    for t in _tasks(rows[0]["course_id"], rows[0]["title"], categories):
        if t.is_done != done:
            task_store.set_done(t.id, done)
            n += 1
    return n


def from_task(task, done):
    """The Task List marked a task done or open again: the homework of that course and title (and the exam event) follow. Returns how many were changed."""
    if task.course_id is None:
        return 0
    n = 0
    if task.category == "Homework":
        for h in crud.list_homework(task.course_id):
            if _key(h["title"]) == _key(task.title) and (h["status"] == "verified") != done:
                crud.set_homework_status(h["id"], "verified" if done else "todo")
                n += 1
    elif task.category in ("Exam", "Quiz"):
        for e in crud._all("SELECT id, title, done FROM events WHERE course_id=?", (task.course_id,)):
            if _key(e["title"]) == _key(task.title) and bool(e["done"]) != done:
                crud.set_event_done(e["id"], done)
                n += 1
    return n
