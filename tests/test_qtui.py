"""The native (Qt) interface: its pure parts (colors, the eye rest logic) and a smoke test of the window drawn without a screen."""
import os

import pytest

from qtui import theme
from qtui.eyerest import EyeRest

CFG = {"rest_seconds": 20, "sound": False, "max_skips": 2, "required_minutes": 5}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_the_palette_follows_the_appearance_and_the_color_theme():
    assert theme.resolve_mode("light", True) == "light" and theme.resolve_mode("dark", False) == "dark"
    assert theme.resolve_mode("device", True) == "dark" and theme.resolve_mode("device", False) == "light"
    dark, light = theme.colors("dark", "ocean"), theme.colors("light", "ocean")
    assert dark["mode"] == "dark" and light["mode"] == "light" and dark["bg"] != light["bg"]
    assert theme.colors("dark", "plum")["primary"] != theme.colors("dark", "forest")["primary"]
    sheet = theme.stylesheet(dark)
    assert dark["bg"] in sheet and dark["primary"] in sheet and "QPushButton#nav" in sheet


def test_the_eye_rest_asks_after_twenty_minutes_and_forces_a_rest_after_too_many_skips():
    clock = Clock()
    er = EyeRest(CFG, clock)
    assert er.tick() is None
    clock.t += 1199
    assert er.tick() is None
    clock.t += 2
    assert er.tick() == "ask" and er.tick() is None                  # one offer at a time
    assert er.refuse() is False                                       # first skip
    clock.t += 1201
    assert er.tick() == "ask"
    assert er.refuse() is True                                        # the second skip in a row: a warning
    clock.t += 1201
    assert er.tick() == "force" and er.forced_left() == 300           # the third reminder is a required rest
    clock.t += 301
    assert er.forced_left() == 0
    er.end_force()
    assert er.refused == 0 and er.tick() is None


def test_taking_a_rest_forgets_the_skips_and_restarts_the_twenty_minutes():
    clock = Clock()
    er = EyeRest(CFG, clock)
    clock.t += 1201
    assert er.tick() == "ask"
    er.refuse()
    clock.t += 600
    assert er.rest_now() is True                                      # Rest Now: counts as the eye rest
    assert er.refused == 0 and er.next == clock.t + 1200
    er.finished()
    clock.t += 1199
    assert er.tick() is None                                          # the 20 minutes started again at that moment
    clock.t += 2
    assert er.tick() == "ask"


def test_rest_now_cannot_replace_a_required_rest():
    clock = Clock()
    er = EyeRest({**CFG, "max_skips": 0}, clock)
    clock.t += 1201
    assert er.tick() == "force"
    assert er.rest_now() is False


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_the_window_has_the_menu_the_settings_page_and_rest_now(qapp, fresh_data):
    from core import crud, settings
    from qtui.window import MainWindow
    cid = crud.add_course("QT 1", "Native", "Fall 2026", 0, "Active")
    w = MainWindow(use_server=False)
    w.show()
    qapp.processEvents()
    assert set(w.sidebar.buttons) == {"Home", "Calendar", "Library", "Note Reader", "Quiz", "Courses", "Rest Now", "Settings"}
    w.choose_course(cid)
    assert w.page == "Courses" and w.course == cid and cid in w.sidebar.courses.course_buttons and w.sidebar.courses.isVisibleTo(w.sidebar)
    w.show_page("Settings")
    assert w.stack.currentWidget() is w.settings_page
    # a change on the Settings page is saved
    from PySide6.QtWidgets import QSpinBox
    spins = w.settings_page.findChildren(QSpinBox)
    assert len(spins) == 4                                            # rest length, skips, required rest, seconds per question
    spins[3].setValue(9)
    assert settings.get_quiz()["speed_seconds"] == 9
    settings.set_quiz(speed_seconds=5)
    w.settings_page._set_theme("plum")
    assert settings.get_color_theme() == "plum"
    settings.set_color_theme("graphite")
    # Rest Now starts the rest card at once and the reminder starts again
    w.rest.rest_now()
    assert w.rest.mode == "rest" and w.rest.overlay.isVisibleTo(w) and w.rest.logic.refused == 0
    w.close()


def _books(n, kind="Homework", course=None):
    from core import crud
    from core.database import DATA_DIR, stored_path
    (DATA_DIR / "pdfs").mkdir(parents=True, exist_ok=True)
    ids = []
    for i in range(n):
        f = DATA_DIR / "pdfs" / f"qt_{kind}_{i}.html"
        f.write_text("<html><body>x</body></html>", encoding="utf-8")
        ids.append(crud.add_book(f"{kind} {i + 1}", "", "", stored_path(f), None, [course] if course else [], kind, "2026", str(i + 1)))
    return ids


def test_the_library_page_groups_searches_edits_and_removes(qapp, fresh_data, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from core import crud
    from qtui.library_dialogs import EditBookDialog, RemoveDialog
    from qtui.pages.library_page import BookCard, LibraryPage
    cid = crud.add_course("QT 2", "Library", "Fall 2026", 0, "Active")
    hw = _books(3, "Homework", cid)
    notes = _books(2, "Notes", cid)
    page = LibraryPage()
    assert page.count.text().startswith("5 Titles")
    # the overview is a tile for each type; a click on a tile shows its files, grouped by course
    page._open_tile("Homework")
    cards = page.body.findChildren(BookCard)
    assert sorted(c.book["title"] for c in cards) == ["Homework 1", "Homework 2", "Homework 3"]
    page._set_view("Details")
    assert page.body.findChildren(__import__("PySide6.QtWidgets", fromlist=["QTableWidget"]).QTableWidget)
    # the search looks at titles, types, authors and courses, whatever is open
    page._search("notes 2")
    assert page.count.text().startswith("1 Title")
    page._search("")
    # edit: the details are saved, the courses too
    dlg = EditBookDialog(crud.get_book(hw[0]))
    dlg.title.setText("Problem Set One")
    dlg.kind.setCurrentText("Homework")
    dlg.lecture.setText("1")
    dlg._save()
    assert crud.get_book(hw[0])["title"] == "Problem Set One"
    # remove many: the rows, the stored copies
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    rm = RemoveDialog()
    rm.ticked = {hw[1], hw[2]}
    rm._remove()
    assert rm.removed == 2 and crud.get_book(hw[1]) is None and crud.get_book(hw[0]) is not None
    page.refresh()
    page._back()
    assert page.count.text().startswith("3 Titles")


def test_the_import_confirmation_returns_what_was_edited_and_ticked(qapp, fresh_data, tmp_path):
    from core import crud
    from qtui.library_dialogs import ImportDialog
    from views import library_import as LI
    course = crud.add_course("QT 3", "Import", "Fall 2026", 0, "Active")
    files = []
    for name in ("QT3 Homework 4.html", "QT3 Lecture 2 Notes.html"):
        p = tmp_path / name
        p.write_text("<html><title>x</title><body>hello</body></html>", encoding="utf-8")
        st = p.stat()
        files.append((p.name, p.name, st.st_size, st.st_mtime, (lambda p=p: p.read_bytes())))
    candidates = LI.classify(files, {}, course)
    assert len(candidates) == 2 and all(c.status == "New" for c in candidates)
    dlg = ImportDialog(candidates)
    names = {c.name: r for r, c in enumerate(dlg.candidates)}
    r = names["QT3 Homework 4.html"]
    dlg.table.cellWidget(r, 4).setText("Homework Four")                 # the title is edited
    dlg.table.cellWidget(names["QT3 Lecture 2 Notes.html"], 0).setChecked(False)           # this one is not imported
    chosen = dlg.chosen()
    assert [c.name for c in chosen] == ["QT3 Homework 4.html"] and chosen[0].title == "Homework Four"
    added, replaced, problems = LI.import_all(chosen, False, course)
    assert (added, replaced, problems) == (1, 0, [])
    assert [b["title"] for b in crud.list_books() if course in b["course_ids"]] == ["Homework Four"]


def test_question_text_keeps_its_math_for_mathjax_and_cards_show_their_state():
    from qtui import quizhtml
    assert quizhtml.md("Find **x** if $a<b$ and `y`") == "Find <b>x</b> if $a&lt;b$ and <code>y</code>"
    assert quizhtml.md("one\n\ntwo") == "one<br><br>two"
    q = {"kind": "mc", "q": "What is $x$?", "o": ["one", "two"], "a": 1, "e": "Because.", "ofb": ["wrong because", ""]}
    run = {"qs": [q], "order": [0], "res": {0: {"chosen": 0}}, "mode": "each", "part": "concept"}
    locked = quizhtml.card_inner(run, 0)
    assert "opt wrong" in locked and "opt right" in locked and "Not correct." in locked and "wrong because" in locked and "Because." in locked and "disabled" in locked
    run["mode"], run["res"] = "end", {0: {"chosen": 1, "hint": True}}
    open_ = quizhtml.card_inner(run, 0)
    assert "opt chosen" in open_ and "Not correct" not in open_ and "Hint used" in open_ and "Check Notes" in open_
    run["part"] = "speed"
    assert "Check Notes" not in quizhtml.card_inner(run, 0)                      # no notes and no hint in a speed round
    page = quizhtml.page({"bg": "#000", "bg2": "#111", "text": "#fff", "border": "#333", "card": "#222", "accent": "#48f", "primary": "#f44", "input": "#222"}, "<p>x</p>")
    assert "qwebchannel.js" in page and "mathjax" in page


def test_the_quiz_page_takes_a_quiz_saves_it_for_later_and_records_the_attempt(qapp, fresh_data):
    from core import crud
    from core.database import DATA_DIR, stored_path
    from qtui import theme
    from qtui.pages.quiz_page import QuizPage
    cid = crud.add_course("QT 4", "Quiz", "Fall 2026", 0, "Active")
    f = DATA_DIR / "pdfs" / "qt_quiz_note.html"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text('<html><body><section id="s1"><h2>One</h2></section><script>const Q=[["What?",["a","b"],0,"because"],["Why?",["c","d"],1,"since"],["Who?",["e","f"],0,"so"]];</script></body></html>', encoding="utf-8")
    bid = crud.add_book("Chapter 1 Notes", "", "", stored_path(f), None, [cid], "Notes", "2026", "1")
    page = QuizPage(theme.colors("dark", "graphite"))
    page.set_course(cid)
    page.reload_courses(select=cid)
    assert page.course["id"] == cid
    chapters = page_chapters = __import__("study.quizrun", fromlist=["x"]).course_chapters(page.course)
    assert len(chapters) == 1 and len(chapters[0]["questions"]) == 3
    page.start(chapters[0], "concept")
    run = page.run
    assert run["phase"] == "run" and len(run["order"]) == 3
    page.on_act("pick", run["order"][0], 1)
    page.on_act("hint", run["order"][1], 0)
    assert run["res"][run["order"][0]]["chosen"] == 1 and run["res"][run["order"][1]]["hint"]
    page.save_for_later()                                                         # kept in the data folder, resumable
    assert page.run is None and page.stack.currentWidget() is page.scroll
    page.show_list()
    page.resume(chapters[0], "concept")
    assert page.run is not None and page.run["res"][page.run["order"][0]]["chosen"] == 1
    for qi in page.run["order"]:                                                  # answer everything, the right answer each time
        page.on_act("pick", qi, page.run["qs"][qi]["a"])
    page.finish()
    assert page.run["phase"] == "done" and page.run["correct"] == 3
    s = crud.quiz_stats(cid)[bid]
    assert (s["last_correct"], s["last_total"]) == (3, 3) and set(s["parts"]) == {"concept"}
    from study import quizrun
    assert quizrun.saved_progress(cid, bid, "concept") is None                    # the saved copy went when the resumed quiz was finished
    page.leave()
    page.view_attempts(chapters[0])
    assert page.run == {"phase": "view"}
    page.leave()


def test_the_courses_page_lists_filters_opens_a_course_and_edits_it(qapp, fresh_data):
    from core import crud
    from qtui.course_dialogs import AddCourseDialog, EditCourseDialog
    from qtui.pages.courses_page import CourseTile, CoursesPage
    a = crud.add_course("QT 10", "Alpha", "Fall 2026", 0, "Active")
    crud.add_course("QT 11", "Beta", "Fall 2026", 0, "Completed")
    page = CoursesPage()
    assert [t.course["id"] for t in page.findChildren(CourseTile)] == [a]                 # the Active tab is the usual one
    page._set_filter("All")
    assert len(page.findChildren(CourseTile)) == 2
    page._set_filter("Completed")
    assert [t.course["name"] for t in page.findChildren(CourseTile)] == ["Beta"]
    # a course page with its six tabs; each is built when it is chosen
    page.open_course(a)
    assert [page.tabs.tabText(i) for i in range(page.tabs.count())] == ["Overview", "Homework", "Exams", "Outline", "Resources", "Quiz"]
    for i in range(page.tabs.count()):
        page.tabs.setCurrentIndex(i)
    crud.add_homework(a, "HW 1", "2099-12-01", "", "")
    page.tabs.setCurrentIndex(1)
    # adding and editing
    add = AddCourseDialog()
    add.name.setText("Gamma")
    add.code.setText("QT 12")
    add._save()
    assert crud.get_course(add.course_id)["name"] == "Gamma"
    edit = EditCourseDialog(crud.get_course(add.course_id))
    edit.name.setText("Gamma Two")
    edit.sem.setText("Spring 2027")
    edit._save()
    assert crud.get_course(add.course_id)["name"] == "Gamma Two" and crud.get_course(add.course_id)["semester"] == "Spring 2027"
    edit2 = EditCourseDialog(crud.get_course(add.course_id))
    edit2.status.setCurrentText("Self-Study")
    edit2._save()
    assert crud.course_status(crud.get_course(add.course_id)) == "Self-Study"
    page.show_grid()


def test_the_window_opens_a_course_from_the_menu_and_its_quiz(qapp, fresh_data):
    from core import crud
    from qtui.window import MainWindow
    cid = crud.add_course("QT 13", "Menu", "Fall 2026", 0, "Active")
    w = MainWindow(use_server=False)
    w.choose_course(cid)
    assert w.page == "Courses" and w.courses.course["id"] == cid and w.stack.currentWidget() is w.courses
    w.courses.quiz_requested.emit(cid)
    assert w.page == "Quiz" and w.quiz.course["id"] == cid


def test_home_lists_the_work_due_and_a_check_marks_it_done_and_undo_puts_it_back(qapp, fresh_data):
    from core import crud
    from library import homedata
    from qtui.pages.home_page import HomePage
    cid = crud.add_course("QT 20", "Home", "Fall 2026", 0, "Active")
    hid = crud.add_homework(cid, "HW 9", "2099-12-01", "", "")
    page = HomePage()
    courses = crud.list_courses(active_only=True)
    homework = {c["id"]: crud.list_homework(c["id"]) for c in courses}
    items = homedata.upcoming_items(courses, homework)
    assert [(i[2], i[3]) for i in items] == [("HW 9", "Homework")]
    assert homedata.progress(courses, homework)[0][1:] == (0, 1)
    assert "HW 9" in "".join(l.text() for l in page.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel))
    page._complete("Homework", hid)                                     # the check: done on Home, and in the Task List when it is the same work
    assert crud.list_homework(cid)[0]["status"] == "verified"
    homework = {c["id"]: crud.list_homework(c["id"]) for c in courses}
    assert homedata.upcoming_items(courses, homework) == [] and [r[1] for r in homedata.completed_items(courses, homework)] == ["HW 9"]
    page._undo("Homework", hid)
    assert crud.list_homework(cid)[0]["status"] == "todo"


def test_the_calendar_draws_week_day_and_month_and_the_task_list_works(qapp, fresh_data):
    from datetime import date, timedelta
    from core import crud
    from planner import task_store, timeutil, store as planner_store
    from qtui import theme
    from qtui.pages.calendar_page import CalendarPage
    from qtui.task_dialogs import TaskDialog
    cid = crud.add_course("QT 30", "Calendar", "Fall 2026", 0, "Active")
    tz = planner_store.get_term().zone
    due = timeutil.to_utc(date.today() + timedelta(days=3), __import__("datetime").time(23, 0), tz)
    tid = task_store.add_task("Read Chapter 2", cid, "Reading", due)
    page = CalendarPage(theme.colors("dark", "graphite"))
    page.refresh()
    assert page.grid.data is not None and len(page.grid.days) == 7                       # the week
    page._set_view("Day")
    assert len(page.grid.days) == 1
    page._set_view("Month")
    assert page.cstack.currentWidget() is page.mscroll and page.span.text()              # the month
    page._step(1)
    page._today()
    page._set_view("Week")
    page._step(-1)
    assert page.grid.days[0] < date.today()
    # the Task List: the task is listed with its time left and cushion, and a check marks it done
    page._set_page("Task List")
    assert page.stack.currentWidget() is page.tasks
    labels = "".join(l.text() for l in page.tasks.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel))
    assert "Read Chapter 2" in labels and "left" in labels
    page.tasks._done(task_store.get_task(tid), True)
    assert task_store.get_task(tid).is_done
    # add a task through the window
    dlg = TaskDialog(None, cid, False)
    dlg.title.setText("Lab Report")
    dlg.category.setCurrentText("Lab")
    dlg._save()
    assert [t.title for t in task_store.list_tasks() if t.category == "Lab"] == ["Lab Report"]
    edit = TaskDialog(task_store.list_tasks()[-1].id, None, False)
    edit.title.setText("Lab Report 1")
    edit.estimate.setValue(90)
    edit._save()
    assert task_store.list_tasks()[-1].title == "Lab Report 1" and task_store.list_tasks()[-1].estimate_minutes == 90


def test_a_note_for_the_native_reader_keeps_its_highlights_in_the_stored_page(qapp, fresh_data):
    import base64
    import json
    from core import crud
    from core.database import DATA_DIR, data_path, stored_path
    from qtui import notehtml
    f = DATA_DIR / "pdfs" / "qt_hl_note.html"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("<html><head><title>T</title></head><body><section id='s1'><h2>One</h2></section></body></html>", encoding="utf-8")
    cid = crud.add_course("QT 40", "Notes", "Fall 2026", 0, "Active")
    bid = crud.add_book("Guide", "", "", stored_path(f), None, [cid], "Notes", "2026", "1")
    book = crud.get_book(bid)
    page = notehtml.note_html(book, f.read_text(encoding="utf-8"), "s1")
    assert "qwebchannel.js" in page and "highlight(BOOK" in page and "RESTORED = null" in page          # nothing saved yet
    # the page reports a highlight: it is written into the stored page
    key = "sg:T:highlights"
    msg = base64.b64encode(json.dumps({"key": key, "value": "[1,2]"}).encode()).decode()
    notehtml.HighlightBridge().highlight(str(bid), msg)
    assert 'id="sa-highlights"' in data_path(book["pdf_path"]).read_text(encoding="utf-8")
    again = notehtml.note_html(crud.get_book(bid), data_path(book["pdf_path"]).read_text(encoding="utf-8"), "s1")
    assert '"value": "[1,2]"' in again and "sa-highlights" not in again.split("RESTORED")[0]          # handed back to the page, and the block is not shown twice


def test_the_note_reader_shows_notes_with_tabs_and_a_pdf_and_remembers_them(qapp, fresh_data):
    import pymupdf
    from core import crud, settings
    from core.database import DATA_DIR, stored_path
    from qtui.pages.notereader_page import NoteReaderPage
    cid = crud.add_course("QT 41", "Reader", "Fall 2026", 0, "Active")
    note = DATA_DIR / "pdfs" / "qt_reader_note.html"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text('<html><body><section id="s1"><h2>One</h2><p>text</p></section><section id="quiz"><h2>Quiz</h2></section>'
                    '<section id="errata"><h2>Errata</h2></section></body></html>', encoding="utf-8")
    nid = crud.add_book("Chapter 1 Notes", "", "", stored_path(note), None, [cid], "Notes", "2026", "1")
    pdf = DATA_DIR / "pdfs" / "qt_reader_book.pdf"
    doc = pymupdf.open()
    for i in range(3):
        doc.new_page().insert_text((72, 72), f"page {i + 1}")
    doc.save(str(pdf))
    doc.close()
    pid = crud.add_book("The Book", "", "", stored_path(pdf), 3, [cid], "Textbook", "2026")
    settings.set_lab({"windows": [{"id": "r1", "type": "reference", "book": pid}, {"id": "n1", "type": "notes"}], "course": cid})
    page = NoteReaderPage()
    kinds = {w.win["type"]: w for w in page.windows}
    nw, rw = kinds["notes"], kinds["reference"]
    assert [nw.tabs.tabText(i) for i in range(nw.tabs.count())] == ["Notes", "Quiz", "Errata"] and nw.book["id"] == nid
    nw.tabs.setCurrentIndex(2)
    assert settings.get_lab()["tabs"][str(nid)] == "Errata"                             # the tab the note was left on is remembered
    assert rw.book["id"] == pid and rw.pdf.doc.pageCount() == 3
    rw._remember_page(2)
    assert settings.get_lab()["pages"][str(pid)] == 2
    # windows: a third can be added, and the saved list follows
    page._add("reference")
    assert len(page.windows) == 3 and not page.add.isEnabled() and [w["id"] for w in settings.get_lab()["windows"]] == ["r1", "n1", "r2"]
    page._close("r2")
    assert len(page.windows) == 2 and page.add.isEnabled()
