"""Courses (native): the course tiles (Recent, All, Active, Self-Study, Completed; category and sort), the page of one course with its Overview, Homework, Exams, Outline, Resources and Quiz, and adding, editing and deleting
courses. What is still on the classic page (reached from buttons here): the tree of knowledge, merging courses, adding and editing the syllabus, editing the outline, equation sheets, the guided tour."""
import re
from datetime import date
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QProgressBar, QPushButton, QScrollArea, QTabWidget, QTableWidget,
                               QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from core import crud, settings
from library import coursedata as cd
from library import photos, syllabus
from qtui.course_dialogs import AddCourseDialog, AddLinkDialog, EditCourseDialog
from qtui.covers import CoverCache
from qtui.flow import FlowLayout
from qtui.library_dialogs import ImportDialog
from qtui.pages.library_page import BookCard
from qtui.widgets import Segmented
from study import quizrun
from views import library_import as LI

STATUS_COLORS = {"done": "#2e9e5b", "late": "#d64545", "open": "#3b82f6", "none": "#6b7280"}
FILTERS = ["Recent", "All"] + list(crud.STATUSES)
_PIX = {}


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


def _photo(course_id, width):
    p = photos.photo_path(course_id)
    if not p:
        return None
    key = (str(p), p.stat().st_mtime, width)
    if key not in _PIX:
        pm = QPixmap(str(p))
        _PIX[key] = None if pm.isNull() else pm.scaledToWidth(width, Qt.SmoothTransformation)
    return _PIX[key]


def _white(text, css=""):
    lab = QLabel(text)
    lab.setStyleSheet(f"color: #ffffff; background: transparent; {css}")
    lab.setWordWrap(True)
    return lab


class PhotoCard(QFrame):
    """A rounded card in the color of a course, with its photo showing through a tint (the tile of the list and the banner of a course page)."""

    def __init__(self, course, w, h, hero=False):
        super().__init__()
        self.course, self.hero = course, hero
        self.color = crud.course_color(course)
        self.dark = crud.darken(self.color)
        self.photo = _photo(course["id"], 1600 if hero else 500)
        if w:
            self.setFixedSize(w, h)
        else:
            self.setFixedHeight(h)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, 14, 14)
        p.setClipPath(path)
        if self.photo:
            pm = self.photo
            scale = max(r.width() / pm.width(), r.height() / pm.height())
            w, h = pm.width() * scale, pm.height() * scale
            p.drawPixmap(QRectF((r.width() - w) / 2, (r.height() - h) / 2, w, h).toRect(), pm)
            g = QLinearGradient(0, r.height(), 0, 0) if self.hero else QLinearGradient(0, 0, r.width(), r.height())
            if self.hero:
                g.setColorAt(0, QColor(0, 0, 0, 184))
                g.setColorAt(1, QColor(0, 0, 0, 30))
            else:
                a, b = QColor(self.color), QColor(self.dark)
                a.setAlpha(196)
                b.setAlpha(230)
                g.setColorAt(0, a)
                g.setColorAt(1, b)
            p.fillRect(self.rect(), QBrush(g))
        else:
            g = QLinearGradient(0, 0, r.width(), r.height())
            g.setColorAt(0, QColor(self.color))
            g.setColorAt(1, QColor(self.dark))
            p.fillRect(self.rect(), QBrush(g))
        p.end()


class CourseTile(PhotoCard):
    clicked = Signal(int)

    def __init__(self, course):
        super().__init__(course, 250, 176)
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(2)
        code = crud.show_code(course["code"])
        lay.addWidget(_white(code or course["name"], "font-size: 20px; font-weight: 800;"))
        if code and course["name"] and course["name"] != course["code"]:
            lay.addWidget(_white(course["name"], "font-size: 14px; font-weight: 600;"))
        lay.addStretch(1)
        if course.get("category"):
            lay.addWidget(_white(course["category"], "font-size: 11px; font-weight: 700; opacity: 0.8;"))
        for x in (course["semester"], course.get("school")):
            if x:
                lay.addWidget(_white(x, "font-size: 12px;"))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.course["id"])


class Banner(PhotoCard):
    """The top of a course page."""

    def __init__(self, course):
        super().__init__(course, 0, 170, hero=True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 18, 26, 18)
        lay.addStretch(1)
        row = QHBoxLayout()
        for x in (crud.course_status(course), course.get("category")):
            if x:
                chip = _white(x, "font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 10px; background: rgba(255,255,255,0.28);")
                chip.setWordWrap(False)
                row.addWidget(chip)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(_white(crud.label(course), "font-size: 26px; font-weight: 800;"))
        meta = crud.term_label(course)
        if meta:
            lay.addWidget(_white(meta, "font-size: 14px;"))


class Row(QFrame):
    """A line of a list: the title (with the files that belong to it as links), the date, a status and the grade."""
    open_book = Signal(int)

    def __init__(self, title, when="", status="", css="none", detail="", links=(), grade="", sub=""):
        super().__init__()
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 9, 14, 9)
        col = QVBoxLayout()
        col.setSpacing(2)
        head = QHBoxLayout()
        name = QLabel(f"<b>{title}</b>")
        head.addWidget(name)
        for label, book_id in links:
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setFlat(True)
            b.setStyleSheet("QPushButton { border: none; color: #4c8dff; padding: 0 6px; background: transparent; } QPushButton:hover { text-decoration: underline; }")
            b.clicked.connect(lambda _=False, i=book_id: self.open_book.emit(i))
            head.addWidget(b)
        head.addStretch(1)
        col.addLayout(head)
        for text in (detail, sub, grade):
            if text:
                lab = QLabel(text)
                lab.setObjectName("muted")
                lab.setWordWrap(True)
                col.addWidget(lab)
        lay.addLayout(col, 1)
        if when:
            lay.addWidget(QLabel(when))
        if status:
            pill = QLabel(status)
            pill.setStyleSheet(f"border: 1px solid {STATUS_COLORS.get(css, '#6b7280')}; color: {STATUS_COLORS.get(css, '#6b7280')}; border-radius: 10px; padding: 1px 10px; font-size: 12px;")
            lay.addWidget(pill)


def _grade_text(item):
    if item.get("score") is None or not item.get("points"):
        return "Not graded"
    n = lambda x: f"{x:g}"
    text = f"Grade {n(item['score'])}/{n(item['points'])} ({item['score'] / item['points']:.0%})"
    notes = [ln.strip() for ln in (item.get("grade_note") or "").splitlines() if ln.strip()]
    return text + ("\n" + "\n".join(notes) if notes else "")


class CoursesPage(QWidget):
    open_book = Signal(int)
    quiz_requested = Signal(int)
    classic_requested = Signal(str, object)
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.cache = CoverCache()
        self.filter, self.category, self.sort = "Active", "All Categories", "Default"
        self.course = None
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(40, 28, 40, 16)
        self.holder = QWidget()
        self.outer.addWidget(self.holder)
        self.show_grid()

    def _reset(self):
        old = self.holder
        self.outer.removeWidget(old)
        old.hide()
        old.setParent(None)
        old.deleteLater()
        self.holder = QWidget()
        self.outer.addWidget(self.holder, 1)
        lay = QVBoxLayout(self.holder)
        lay.setContentsMargins(0, 0, 0, 0)
        return lay

    # ---------------------------------------------------------------- the list of courses
    def show_grid(self):
        self.course = None
        lay = self._reset()
        top = QHBoxLayout()
        title = QLabel("Courses")
        title.setObjectName("h1")
        top.addWidget(title)
        top.addStretch(1)
        merge = QPushButton("Merge Courses")
        merge.setToolTip("make two or more courses one (MA 266 / MA 303), with each part's files, homework and exams kept apart by a tag (classic page)")
        merge.clicked.connect(lambda: self.classic_requested.emit("merge", None))
        add = QPushButton("Add Course")
        add.clicked.connect(self.add_course)
        top.addWidget(merge)
        top.addWidget(add)
        lay.addLayout(top)
        groups = {s: crud.courses_by_status(s) for s in crud.STATUSES}
        everyone = [c for s in crud.STATUSES for c in groups[s]]
        opened = settings.get_recent_courses()
        recent = sorted((c for c in everyone if str(c["id"]) in opened), key=lambda c: opened[str(c["id"])], reverse=True)
        groups = {"Recent": recent, "All": everyone, **groups}
        bar = QHBoxLayout()
        seg = Segmented([(k, f"{k} ({len(groups[k])})") for k in FILTERS], self.filter)
        seg.changed.connect(self._set_filter)
        bar.addWidget(seg)
        bar.addStretch(1)
        cat = QComboBox()
        cat.addItems(["All Categories"] + crud.all_categories())
        cat.setCurrentText(self.category if self.category in ["All Categories"] + crud.all_categories() else "All Categories")
        cat.currentTextChanged.connect(self._set_category)
        srt = QComboBox()
        srt.addItems([f"Sort: {s}" for s in cd.SORTS])
        srt.setCurrentText(f"Sort: {self.sort}")
        srt.currentTextChanged.connect(self._set_sort)
        bar.addWidget(cat)
        bar.addWidget(srt)
        lay.addLayout(bar)
        courses = groups[self.filter]
        if self.category != "All Categories":
            courses = [c for c in courses if c.get("category") == self.category]
        if self.filter == "All":
            tree = QPushButton("Tree of Knowledge (Classic Page)")
            tree.clicked.connect(lambda: self.classic_requested.emit("tree", None))
            lay.addWidget(tree, 0, Qt.AlignLeft)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("page")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(0, 0, 0, 0)
        if not courses:
            blay.addWidget(QLabel("No courses opened yet." if self.filter == "Recent" and self.category == "All Categories"
                                  else f"No {self.filter.lower()} courses" + ("" if self.category == "All Categories" else f" in {self.category}") + "."))
        for heading, items in ([("", courses)] if self.filter == "Recent" else cd._sorted_groups(courses, self.sort)):
            if heading:
                h = QLabel(f"{heading} ({len(items)})")
                h.setObjectName("h2")
                blay.addWidget(h)
            host = QWidget()
            flow = FlowLayout(host, 16, 16)
            for c in items:
                t = CourseTile(c)
                t.clicked.connect(self.open_course)
                flow.addWidget(t)
            blay.addWidget(host)
        blay.addStretch(1)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)

    def _set_filter(self, key):
        self.filter = key
        self.show_grid()

    def _set_category(self, text):
        self.category = text
        self.show_grid()

    def _set_sort(self, text):
        self.sort = text.replace("Sort: ", "")
        self.show_grid()

    def add_course(self):
        dlg = AddCourseDialog(self.window())
        if dlg.exec() and dlg.course_id:
            c = crud.get_course(dlg.course_id)
            self.filter = crud.course_status(c)
            self.changed.emit()
            self.open_course(dlg.course_id)

    # ---------------------------------------------------------------- one course
    def open_course(self, course_id):
        course = crud.get_course(course_id)
        if not course:
            self.show_grid()
            return
        settings.touch_course(course_id)
        self.course = course
        lay = self._reset()
        bar = QHBoxLayout()
        back = QPushButton("← All Courses")
        back.clicked.connect(self.show_grid)
        update = QPushButton("Update Files")
        update.setToolTip("reads the folder your files are kept in and lists the new and the changed ones for this course")
        update.clicked.connect(self.update_files)
        edit = QPushButton("Edit Course")
        edit.clicked.connect(self.edit_course)
        tour = QPushButton("Set Up Tour")
        tour.setToolTip("a guided tour: add the syllabus, bring in the files and make helpers with your ai (classic page)")
        tour.clicked.connect(lambda: self.classic_requested.emit("tour", course_id))
        for w in (back, update, edit, tour):
            bar.addWidget(w)
        bar.addStretch(1)
        lay.addLayout(bar)
        lay.addWidget(Banner(course))
        self.tabs = QTabWidget()
        self.tab_scrolls = {}
        for name in ("Overview", "Homework", "Exams", "Outline", "Resources", "Quiz"):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            body = QWidget()
            body.setObjectName("page")
            QVBoxLayout(body).setContentsMargins(4, 14, 4, 20)
            scroll.setWidget(body)
            self.tabs.addTab(scroll, name)
            self.tab_scrolls[name] = body
        self.tabs.currentChanged.connect(self._build_tab)
        lay.addWidget(self.tabs, 1)
        self._build_tab(0)

    def edit_course(self):
        dlg = EditCourseDialog(self.course, self.window())
        if dlg.exec():
            self.changed.emit()
            if dlg.deleted:
                self.show_grid()
            else:
                self.open_course(self.course["id"])

    def update_files(self):
        folder = QFileDialog.getExistingDirectory(self.window(), "Update Files", str(Path.home()))
        if not folder:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            candidates = LI.folder_candidates(folder, self.course["id"])
        finally:
            QApplication.restoreOverrideCursor()
        if not candidates:
            QMessageBox.information(self.window(), "Update Files", "No files were found.")
            return
        dlg = ImportDialog(candidates, self.window(), "Update Files")
        if dlg.exec():
            chosen = dlg.chosen()
            if chosen:
                notices = []
                added, replaced, problems = LI.import_all(chosen, True, self.course["id"], [], notices)
                QMessageBox.information(self.window(), "Update Files", f"Imported {added} file{'s' if added != 1 else ''}" + (f" and replaced {replaced}" if replaced else "") + "."
                                        + (("\n\nNot imported:\n" + "\n".join(problems[:6])) if problems else "")
                                        + (("\n\nQuiz changes found:\n" + "\n".join(notices)) if notices else ""))
                self.open_course(self.course["id"])

    def _build_tab(self, index):
        name = self.tabs.tabText(index)
        body = self.tab_scrolls[name]
        lay = body.layout()
        _clear(lay)
        getattr(self, "_tab_" + name.lower())(lay, self.course)
        lay.addStretch(1)

    def _h(self, text):
        lab = QLabel(text)
        lab.setObjectName("h2")
        return lab

    def _row(self, *args, **kw):
        r = Row(*args, **kw)
        r.open_book.connect(self.open_book)
        return r

    # ---- Overview
    def _tab_overview(self, lay, course):
        homework, exams = cd._homework_items(course), cd._exam_items(course)
        data = cd._syllabus_data(course)
        finished = crud.course_status(course) == "Completed"
        rows = [] if finished else cd.coming_up(course)
        try:
            from planner import task_store
            open_tasks = len(task_store.list_tasks(course_id=course["id"], include_done=False))
        except Exception:
            open_tasks = 0
        graded = sum(1 for h in homework if h.get("score") is not None) + sum(1 for e in exams if e.get("score") is not None)
        est = syllabus.standing(data, homework, exams) if data else None
        nxt = rows[0] if rows else None
        glance = QHBoxLayout()
        for label, value in (("Next Due", cd._when(nxt[0], nxt[1]).split(" · ")[0] if nxt else "Nothing"), ("Open Tasks", str(open_tasks)),
                             ("Graded", f"{graded} of {len(homework) + len(exams)}"), ("Grade So Far", f"{syllabus.letter(est[0], data)[0]}  ({est[0]:.1f}%)" if est else "None")):
            box = QFrame()
            box.setObjectName("card")
            bl = QVBoxLayout(box)
            bl.addWidget(QLabel(label))
            big = QLabel(value)
            big.setStyleSheet("font-size: 24px; font-weight: 700; background: transparent;")
            bl.addWidget(big)
            glance.addWidget(box)
        lay.addLayout(glance)
        if not finished:
            lay.addWidget(self._h("Coming Up"))
            if rows:
                for day, time, title, kind in rows:
                    lay.addWidget(self._row(title, cd._when(day, time), kind, "none"))
            else:
                lay.addWidget(QLabel("Nothing is due soon."))
        lay.addWidget(self._h("Grades"))
        hw_avg, ex_avg = cd._percent(homework), cd._percent(exams)
        if hw_avg is None and ex_avg is None:
            lay.addWidget(QLabel("No grades yet. Homework and exam grades appear here."))
        else:
            g = QHBoxLayout()
            items = [("Homework Average", f"{hw_avg:.0%}" if hw_avg is not None else "None"), ("Exam Average", f"{ex_avg:.0%}" if ex_avg is not None else "None")]
            if est:
                grade, assumed = syllabus.letter(est[0], data)
                items.append(("Estimated Letter Grade", f"{grade}  ({est[0]:.1f}%)"))
            for label, value in items:
                box = QFrame()
                box.setObjectName("card")
                bl = QVBoxLayout(box)
                bl.addWidget(QLabel(label))
                big = QLabel(value)
                big.setStyleSheet("font-size: 22px; font-weight: 700; background: transparent;")
                bl.addWidget(big)
                g.addWidget(box)
            lay.addLayout(g)
        if data and data.get("rows"):
            t = QTableWidget(len(data["rows"]), 3)
            t.setHorizontalHeaderLabels(["Part of the Grade", "Weight", "Your Score So Far"])
            t.verticalHeader().hide()
            t.setEditTriggers(QTableWidget.NoEditTriggers)
            t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            t.horizontalHeader().setStretchLastSection(False)
            t.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            for i, r in enumerate(data["rows"]):
                got = syllabus.score(r.get("kind"), homework, exams)
                for c, text in enumerate((r["item"], f"{r['percent']:g}%", f"{got:.0%}" if got is not None else ("Not graded" if r.get("kind") else "None"))):
                    t.setItem(i, c, QTableWidgetItem(text))
            t.setFixedHeight(34 + 30 * len(data["rows"]))
            lay.addWidget(t)
        lay.addWidget(self._h("Syllabus"))
        files = [b for b in crud.list_books() if course["id"] in b["course_ids"] and b["kind"] == "Syllabus" and crud.in_part(b["title"], course.get("part"))]
        row = QHBoxLayout()
        for b in files:
            btn = QPushButton(f"Open {b['title']}")
            btn.clicked.connect(lambda _=False, i=b["id"]: self.open_book.emit(i))
            row.addWidget(btn)
        edit = QPushButton("Add or Edit Syllabus (Classic Page)")
        edit.clicked.connect(lambda: self.classic_requested.emit("course", course["id"]))
        row.addWidget(edit)
        row.addStretch(1)
        lay.addLayout(row)
        self._understanding(lay, course)

    def _understanding(self, lay, course):
        chapters = quizrun.course_chapters(course)
        if not chapters:
            return
        stats = crud.quiz_stats(course["id"])
        taken = [stats[c["book"]["id"]] for c in chapters if c["book"]["id"] in stats]
        lay.addWidget(self._h("Understanding"))
        if taken:
            avg = round(sum(quizrun._pct(quizrun._unaided(s), s["last_total"]) for s in taken) / len(taken))
            cap = f"{avg}% average unaided score · {len(taken)} of {len(chapters)} chapters quizzed. Answers that used the notes are recorded and do not count."
        else:
            cap = "No quizzes taken yet. Take one in the Quiz tab to see how well you know each chapter."
        c = QLabel(cap)
        c.setObjectName("muted")
        c.setWordWrap(True)
        lay.addWidget(c)
        for ch in chapters:
            s = stats.get(ch["book"]["id"])
            frame = QFrame()
            frame.setObjectName("card")
            h = QHBoxLayout(frame)
            if s:
                pct = quizrun._pct(quizrun._unaided(s), s["last_total"])
                level = quizrun._level(pct)[0]
                detail = f"{quizrun._unaided(s)}/{s['last_total']} unaided · best {s['best']}% · {s['attempts']} attempt{'s' if s['attempts'] != 1 else ''}"
            else:
                pct, level = 0, "Not Taken"
                detail = f"{sum(quizrun._count(ch, p, q) for p, q in quizrun.chapter_parts(ch).items())} questions"
            name = QLabel(f"<b>{ch['name']}</b><br><span style='opacity:0.7'>{detail}</span>")
            h.addWidget(name, 3)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            h.addWidget(bar, 2)
            h.addWidget(QLabel(f"{pct}%"))
            pill = QLabel(level)
            color = {"Strong": "#2e9e5b", "Passed": "#3b82f6", "Failed": "#d64545"}.get(level, "#6b7280")
            pill.setStyleSheet(f"border: 1px solid {color}; color: {color}; border-radius: 10px; padding: 1px 10px;")
            h.addWidget(pill)
            lay.addWidget(frame)

    # ---- Homework and Exams
    def _tab_homework(self, lay, course):
        today = date.today().isoformat()
        homework = cd._homework_items(course)
        if not homework:
            lay.addWidget(self._h("Homework"))
            lay.addWidget(QLabel("No homework yet."))
            return
        finished = crud.course_status(course) == "Completed"
        upcoming, not_graded, past = cd.homework_groups(homework, today, finished)

        def row(h):
            status, css = cd._homework_status(h, today)
            links = [(label, b["id"]) for label, kind in (("Problem", "Homework"), ("Solution", "Homework Solution"), ("Graded", "Graded Homework"), ("Helper", "Homework Helper"),
                                                          ("Grade Explanation", "Grade Explanation")) if (b := cd._homework_book(course["id"], h["title"], kind))]
            return self._row(h["title"], cd._when(h["due_date"], h.get("due_time")), status, css, (h.get("problem_md") or "").strip(), links, _grade_text(h))

        if not finished:
            lay.addWidget(self._h(f"Upcoming Homework ({len(upcoming)})"))
            for h in upcoming:
                lay.addWidget(row(h))
            if not upcoming:
                lay.addWidget(QLabel("Nothing due."))
        if not_graded:                                                         # handed in, waiting for a grade
            lay.addWidget(self._h(f"Not Graded ({len(not_graded)})"))
            for h in not_graded:
                lay.addWidget(row(h))
        lay.addWidget(self._h(f"Past Homework ({len(past)})"))
        for h in reversed(past):
            lay.addWidget(row(h))
        if not past:
            lay.addWidget(QLabel("None yet."))

    def _tab_exams(self, lay, course):
        today = date.today().isoformat()
        exams = cd._exam_items(course)
        finished = crud.course_status(course) == "Completed"
        upcoming = [] if finished else [e for e in exams if e["date"] >= today and not e.get("done")]
        past = list(exams) if finished else [e for e in exams if e["date"] < today or e.get("done")]

        def row(e, done):
            links = []
            for label, kind, word in (("Exam", "Exam", None), ("Solution", "Exam Solution", None), ("Graded", "Graded Exam", None), ("Preparation", "Exam Preparation", None),
                                      ("Reflection", "Exam Reflection", "Reflection"), ("Statistics", "Exam Reflection", "Statistics")):
                if word and not done:
                    continue
                b = cd._exam_book(course["id"], e["title"], kind, word)
                if b:
                    links.append((label, b["id"]))
            return self._row(e["title"], cd._when(e["date"], e.get("time")), "Done" if done else "Upcoming", "done" if done else "open", f"Covers {e['covers']}" if e.get("covers") else "", links, _grade_text(e))

        if not exams:
            lay.addWidget(self._h("Exams"))
            lay.addWidget(QLabel("No midterms or finals yet."))
        else:
            if not finished:
                lay.addWidget(self._h(f"Upcoming Exams ({len(upcoming)})"))
                for e in upcoming:
                    lay.addWidget(row(e, False))
                if not upcoming:
                    lay.addWidget(QLabel("No exams left this term."))
            lay.addWidget(self._h(f"Past Exams ({len(past)})"))
            for e in reversed(past):
                lay.addWidget(row(e, True))
            if not past:
                lay.addWidget(QLabel("None yet."))
        practice = [b for b in crud.list_books() if b["kind"] == "Practice Exam" and course["id"] in b["course_ids"] and crud.in_part(b["title"], course.get("part"))]
        if practice:
            lay.addWidget(self._h(f"Practice Exams ({len(practice)})"))
            for b in sorted(practice, key=lambda b: crud._natural_key(b["title"])):
                lay.addWidget(self._row(b["title"], "", "", "none", "", [("Open", b["id"])]))
        note = QPushButton("Equation Sheets (Classic Page)")
        note.clicked.connect(lambda: self.classic_requested.emit("course", course["id"]))
        lay.addWidget(note, 0, Qt.AlignLeft)

    # ---- Outline
    def _tab_outline(self, lay, course):
        from library import courseoutline
        part = course.get("part")
        state = courseoutline.ensure(course["id"], part)
        items = crud.list_outline(course["id"], part)
        made = {"syllabus": "Built from the syllabus", "titles": "Built from the lecture and chapter titles"}.get(state.get("source"))
        note = (f"{made}. It follows your Library until you edit it." if made else "Edited by you." if items else
                "No outline yet: add lectures or a syllabus with a topic list to the Library, or build one with Edit Outline.")
        row = QHBoxLayout()
        cap = QLabel(note)
        cap.setObjectName("muted")
        cap.setWordWrap(True)
        row.addWidget(cap, 1)
        edit = QPushButton("Edit Outline (Classic Page)")
        edit.clicked.connect(lambda: self.classic_requested.emit("course", course["id"]))
        row.addWidget(edit)
        lay.addLayout(row)
        if not items:
            return
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setStyleSheet("QTreeWidget { background: transparent; border: none; }")
        stack = []

        def make(it, parent):
            marker = it["marker"] + ("." if re.fullmatch(r"[IVXLCDM]+|[A-Z]|\d+|[a-z]", it["marker"]) else "")
            node = QTreeWidgetItem(parent or tree, [f"{marker}  {it['title']}"])
            node.setData(0, Qt.UserRole, (it.get("book_id"), it.get("page"), it.get("url")))
            return node

        depth = {"I": 0, "L": 0, "A": 1, "1": 2, "a": 3}
        for it in items:
            d = depth.get(it["level"], 0)
            parent = stack[d - 1] if d and len(stack) >= d else None
            node = make(it, parent)
            del stack[d:]
            stack.append(node)
        tree.expandToDepth(0)
        tree.setMinimumHeight(560)

        def clicked(node, _col):
            book_id, page, url = node.data(0, Qt.UserRole)
            if book_id:
                self.open_book.emit(book_id)
            elif url:
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl(url))
        tree.itemClicked.connect(clicked)
        lay.addWidget(tree)

    # ---- Resources and Quiz
    def _tab_resources(self, lay, course):
        links = crud.list_links(course["id"])
        lay.addWidget(self._h(f"Links ({len(links)})"))
        if not links:
            lay.addWidget(QLabel("No links yet."))
        for ln in links:
            row = QHBoxLayout()
            b = QPushButton(ln["title"])
            b.setFlat(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton { border: none; color: #4c8dff; text-align: left; } QPushButton:hover { text-decoration: underline; }")
            b.setToolTip(ln["url"])
            b.clicked.connect(lambda _=False, u=ln["url"]: self._open_url(u))
            rm = QPushButton("Remove")
            rm.clicked.connect(lambda _=False, i=ln["id"]: (crud.delete_link(i), self._build_tab(self.tabs.currentIndex())))
            row.addWidget(b, 1)
            row.addWidget(rm)
            holder = QWidget()
            holder.setLayout(row)
            lay.addWidget(holder)
        add = QPushButton("Add Link")
        add.clicked.connect(self._add_link)
        lay.addWidget(add, 0, Qt.AlignLeft)
        files = [b for b in crud.list_books() if course["id"] in b["course_ids"] and crud.in_part(b["title"], course.get("part"))]
        order = lambda b: ((0, crud._natural_key(b["lecture"])) if b.get("lecture") else (1, []), crud._natural_key(b["title"]))
        courses = {c["id"]: c for c in crud.list_courses(section=None)}
        for heading, kinds, empty in (("Course Notes", ("Lecture Notes",), "No course notes yet."), ("Notes", ("Notes",), "No notes yet."), ("Textbooks", ("Textbook",), "No textbooks yet.")):
            items = sorted((b for b in files if b["kind"] in kinds), key=order)
            lay.addWidget(self._h(f"{heading} ({len(items)})"))
            if not items:
                lay.addWidget(QLabel(f"{empty} Add a file in the Library and choose this course."))
                continue
            host = QWidget()
            flow = FlowLayout(host, 14, 14)
            for b in items:
                card = BookCard(b, courses, self.cache)
                card.open_requested.connect(self.open_book)
                card.edit_requested.connect(lambda _=None: None)
                card.remove_requested.connect(lambda _=None: None)
                flow.addWidget(card)
            lay.addWidget(host)

    def _open_url(self, url):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(url))

    def _add_link(self):
        if AddLinkDialog(self.course["id"], self.window()).exec():
            self._build_tab(self.tabs.currentIndex())

    def _tab_quiz(self, lay, course):
        lay.addWidget(self._h("Quiz"))
        chapters = quizrun.course_chapters(course)
        lay.addWidget(QLabel(f"{len(chapters)} chapter{'s' if len(chapters) != 1 else ''} with questions." if chapters else
                             "No quiz questions yet. Quizzes come from the conceptual checks and the Self-check section of this course's HTML notes in the Library."))
        go = QPushButton("Open the Quizzes of This Course")
        go.setObjectName("primary")
        go.setEnabled(bool(chapters))
        go.clicked.connect(lambda: self.quiz_requested.emit(course["id"]))
        lay.addWidget(go, 0, Qt.AlignLeft)
