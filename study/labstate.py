"""What the Note Reader remembers (its windows, their widths, the note and the tab each course was left on, the page of each file) and which notes a course has. No Streamlit and no Qt: the classic page
(`views/lab_view.py`) and the native one (`qtui/pages/notereader_page.py`) both use it, and they share the saved state (`settings.get_lab`)."""
import re

from core import crud
from core import settings

MAX_WINDOWS = 3


def _weights(wins):
    """Relative widths of the windows (dragged by the user; equal by default), by window id."""
    saved = settings.get_lab().get("widths", {})
    return [max(0.1, float(saved.get(w["id"], 1.0))) for w in wins]


def _windows():
    """Open windows in left-to-right order: [{'id', 'type': 'notes' | 'reference', 'book'}]."""
    wins = settings.get_lab().get("windows")
    if not wins:
        old = settings.get_lab()
        wins = [{"id": "r1", "type": "reference", "book": old.get("book")}, {"id": "n1", "type": "notes"}]
    return wins


def _save_windows(wins):
    _remember(windows=wins)


def _remember(**values):
    lab = settings.get_lab()
    if any(lab.get(k) != v for k, v in values.items()):
        settings.set_lab({**lab, **values})


def _course_notes(course_id):
    """The course's HTML notes in the Library (type Notes), in lecture order."""
    def order(b):
        nums = [int(n) for n in re.findall(r"\d+", b.get("lecture") or "")]
        return (nums[0] if nums else 999, nums[1:] or [0], b["title"].lower())

    return sorted((b for b in crud.list_books() if course_id in b["course_ids"] and b["kind"] == "Notes"
                   and b["pdf_path"].lower().endswith((".html", ".htm"))), key=order)
