"""Home (native): the week of the term, the progress of each course, the work that is due next (a check marks it done, in the Task List too) and what was completed lately.
The getting-started tutorial is still the classic page's (a button opens it there)."""
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget

from core import crud, settings
from library import homedata as hd

PILL = {"late": "#d64545", "open": "#3b82f6"}


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


class HomePage(QWidget):
    course_requested = Signal(int)
    classic_requested = Signal(str)
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.open_completed = False
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 28, 40, 16)
        top = QHBoxLayout()
        title = QLabel("Home")
        title.setObjectName("h1")
        top.addWidget(title)
        top.addStretch(1)
        tut = QPushButton("Show the Tutorial")
        tut.setToolTip("the getting-started tutorial (classic page)")
        tut.clicked.connect(lambda: self.classic_requested.emit("tutorial"))
        top.addWidget(tut)
        root.addLayout(top)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.body = QWidget()
        self.body.setObjectName("page")
        self.lay = QVBoxLayout(self.body)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(10)
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)
        self.refresh()

    def _h(self, text):
        lab = QLabel(text)
        lab.setObjectName("h2")
        return lab

    def refresh(self):
        _clear(self.lay)
        today = date.today()
        if settings.semester_set():
            row = QHBoxLayout()
            for big, small in hd._term_stats(today):
                box = QFrame()
                box.setObjectName("card")
                bl = QVBoxLayout(box)
                bl.setContentsMargins(16, 8, 16, 8)
                b = QLabel(big)
                b.setStyleSheet("font-size: 22px; font-weight: 700; background: transparent;")
                bl.addWidget(b)
                s = QLabel(small)
                s.setObjectName("muted")
                bl.addWidget(s)
                row.addWidget(box)
            row.addStretch(1)
            self.lay.addLayout(row)
        courses = crud.list_courses(active_only=True)
        if not courses:
            hint = QLabel("Add a course under Courses to get started. Set the term dates in the Calendar (Edit Schedule) to see the week and the days left in the term.")
            hint.setWordWrap(True)
            self.lay.addWidget(hint)
            self.lay.addStretch(1)
            return
        homework = {c["id"]: crud.list_homework(c["id"]) for c in courses}
        cols = QHBoxLayout()
        cols.setSpacing(30)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.addWidget(self._h("Progress"))
        for c, done, total in hd.progress(courses, homework):
            text = f"{c['code']}: {c['name']} · {done}/{total} homework" if total else f"{c['code']}: {c['name']} · no homework yet"
            lab = QLabel(text)
            lab.setCursor(Qt.PointingHandCursor)
            lab.mousePressEvent = lambda e, cid=c["id"]: self.course_requested.emit(cid)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(round(100 * done / total) if total else 0)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            left.addWidget(lab)
            left.addWidget(bar)
        left.addStretch(1)
        right.addWidget(self._h("Upcoming Work"))
        items = hd.upcoming_items(courses, homework, today)
        if not items:
            right.addWidget(QLabel("Nothing due. Enjoy the free time."))
        else:
            for day, time, title, kind, c, covers, item_id in items[:hd.SHOWN]:
                right.addWidget(self._item(day, time, title, kind, c, covers, item_id, today))
            if len(items) > hd.SHOWN:
                more = QLabel(f"{len(items) - hd.SHOWN} more in the Calendar and on each course page.")
                more.setObjectName("muted")
                right.addWidget(more)
        self._completed(right, courses, homework, today)
        right.addStretch(1)
        cols.addLayout(left, 4)
        cols.addLayout(right, 5)
        self.lay.addLayout(cols)
        self.lay.addStretch(1)

    def _item(self, day, time, title, kind, course, covers, item_id, today):
        label, css = hd._countdown(day, today)
        frame = QFrame()
        frame.setObjectName("card")
        h = QHBoxLayout(frame)
        h.setContentsMargins(14, 8, 10, 8)
        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(f"<b>{title}</b>")
        name.setCursor(Qt.PointingHandCursor)
        name.mousePressEvent = lambda e, cid=course["id"]: self.course_requested.emit(cid)
        col.addWidget(name)
        meta = QHBoxLayout()
        color = crud.course_color(course)
        chip = QLabel(crud.show_code(course["code"]) or course["name"])
        chip.setStyleSheet(f"background: {color}; color: #ffffff; border-radius: 9px; padding: 1px 9px; font-size: 11px; font-weight: 600;")
        meta.addWidget(chip)
        if kind != "Homework":
            k = QLabel(kind)
            k.setStyleSheet("border: 1px solid rgba(128,128,128,0.5); border-radius: 9px; padding: 1px 8px; font-size: 11px;")
            meta.addWidget(k)
        when = QLabel(hd._when(day, time))
        when.setObjectName("muted")
        meta.addWidget(when)
        meta.addStretch(1)
        col.addLayout(meta)
        if covers:
            c = QLabel(f"Covers {covers}")
            c.setObjectName("muted")
            col.addWidget(c)
        h.addLayout(col, 1)
        pill = QLabel(label)
        pill.setStyleSheet(f"border: 1px solid {PILL[css]}; color: {PILL[css]}; border-radius: 10px; padding: 1px 10px; font-size: 12px;")
        h.addWidget(pill)
        check = QPushButton("✓")
        check.setFixedWidth(40)
        check.setToolTip(f"mark this {kind.lower()} as complete")
        check.clicked.connect(lambda _=False, k=kind, i=item_id: self._complete(k, i))
        h.addWidget(check)
        return frame

    def _completed(self, lay, courses, homework, today):
        rows = hd.completed_items(courses, homework, today)
        if not rows:
            return
        head = QToolButton()
        head.setStyleSheet("QToolButton { border: none; background: transparent; font-weight: 700; font-size: 15px; padding: 6px 0; }")
        head.setCursor(Qt.PointingHandCursor)
        head.setText(f"{'▾' if self.open_completed else '▸'}  Completed ({len(rows)})")
        head.clicked.connect(self._toggle_completed)
        lay.addWidget(head, 0, Qt.AlignLeft)
        if not self.open_completed:
            return
        for day, title, kind, c, item_id in rows:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{title}</b> · {c['code']} · {hd._when(day, '')}"), 1)
            undo = QPushButton("Undo")
            undo.setToolTip(f"put this {kind.lower()} back in the list")
            undo.clicked.connect(lambda _=False, k=kind, i=item_id: self._undo(k, i))
            row.addWidget(undo)
            holder = QWidget()
            holder.setLayout(row)
            lay.addWidget(holder)

    def _toggle_completed(self):
        self.open_completed = not self.open_completed
        self.refresh()

    def _complete(self, kind, item_id):
        hd._complete(kind, item_id)
        self.refresh()
        self.changed.emit()

    def _undo(self, kind, item_id):
        hd._undo(kind, item_id)
        self.refresh()
        self.changed.emit()
