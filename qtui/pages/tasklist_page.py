"""The Task List (native): every task in one list, by course, grouped and sorted, with a check to mark it done (the homework or exam of Home follows), the time left and the cushion before the deadline.
Importing tasks from a syllabus or a calendar and the default estimates are still on the classic page."""
from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget)

from core import crud, settings
from planner import linkdone, service, session_store, store as planner_store, task_store, timeutil
from planner import tasklist as TL
from qtui.task_dialogs import TaskDialog
from views import plan_grid


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


def _cushion_text(minutes):
    return ("+" if minutes > 0 else "") + plan_grid.fmt_minutes(minutes)


class TaskListPage(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.which = "all"
        self.group, self.sort, self.desc, self.query = "None", "Due Date", False, ""
        self.open_done = False
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)
        self.side = QListWidget()
        self.side.setFixedWidth(230)
        self.side.currentRowChanged.connect(self._pick)
        root.addWidget(self.side)
        main = QVBoxLayout()
        main.setSpacing(8)
        head = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("h2")
        head.addWidget(self.title, 1)
        self.group_box = QComboBox()
        self.group_box.addItems([f"Group: {g}" for g in TL.GROUPS])
        self.group_box.currentTextChanged.connect(lambda t: self._set("group", t.replace("Group: ", "")))
        self.sort_box = QComboBox()
        self.sort_box.addItems([f"Sort: {s}" for s in TL.SORTS])
        self.sort_box.currentTextChanged.connect(lambda t: self._set("sort", t.replace("Sort: ", "")))
        self.desc_btn = QPushButton("↑")
        self.desc_btn.setFixedWidth(40)
        self.desc_btn.setToolTip("reverse the order")
        self.desc_btn.clicked.connect(self._reverse)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search Tasks")
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(lambda t: self._set("query", t))
        add = QPushButton("Add New Task")
        add.setObjectName("primary")
        add.clicked.connect(self.add_task)
        for w in (self.group_box, self.sort_box, self.desc_btn, self.search, add):
            head.addWidget(w)
        main.addLayout(head)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.body = QWidget()
        self.body.setObjectName("page")
        self.lay = QVBoxLayout(self.body)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(4)
        self.scroll.setWidget(self.body)
        main.addWidget(self.scroll, 1)
        root.addLayout(main, 1)
        self._filling = False

    @staticmethod
    def _fmt_due(due, tz):
        if due is None:
            return "No due date"
        local = timeutil.to_local(due, tz)
        return f"{local:%b} {local.day}, {local:%I:%M %p}".replace(" 0", " ")

    def _set(self, name, value):
        setattr(self, name, value)
        self.refresh()

    def _reverse(self):
        self.desc = not self.desc
        self.desc_btn.setText("↓" if self.desc else "↑")
        self.refresh()

    def _pick(self, row):
        if self._filling or row < 0:
            return
        self.which = self.side.item(row).data(Qt.UserRole)
        self.refresh()

    def _term_courses(self, courses):
        term = settings.get_active_term()
        active = {cid: c for cid, c in courses.items() if crud.course_status(c) == "Active"}
        named = {cid: c for cid, c in active.items() if term and (c.get("semester") or "").strip().lower() == term["name"].strip().lower()}
        return named or active

    def refresh(self):
        courses = {c["id"]: c for c in crud.list_courses(section=None)}
        shown_courses = self._term_courses(courses)
        tasks = task_store.list_tasks()
        open_tasks = [t for t in tasks if not t.is_done]
        self._filling = True
        self.side.clear()
        entries = [("all", f"All Tasks ({len(open_tasks)})"), ("personal", f"Personal / No Course ({sum(1 for t in open_tasks if t.personal or t.course_id is None)})")]
        entries += [(f"course:{cid}", f"{crud.show_code(c['code']) or c['name']} ({sum(1 for t in open_tasks if t.course_id == cid)})") for cid, c in shown_courses.items()]
        if self.which not in [k for k, _ in entries]:
            self.which = "all"
        for key, label in entries:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, key)
            self.side.addItem(it)
            if key == self.which:
                self.side.setCurrentItem(it)
        self._filling = False
        course_id = int(self.which.split(":")[1]) if self.which.startswith("course:") else None
        self.title.setText("Personal / No Course" if self.which == "personal" else (crud.show_code(courses[course_id]["code"]) or courses[course_id]["name"]) if course_id else "All Tasks")
        try:
            report = service.cushion_report()
        except Exception:
            report = None
        cushions = {c.task_id: c for c in report.items} if report else {}
        tz = planner_store.get_term().zone
        now = datetime.now(timezone.utc)
        sessions = session_store.list_sessions()
        _clear(self.lay)
        shown = TL.sort_tasks(TL.filter_tasks(tasks, courses, self.which, self.query, False), self.sort, self.desc, courses, {k: v.cushion_minutes for k, v in cushions.items()})
        finished = TL.sort_tasks([t for t in TL.filter_tasks(tasks, courses, self.which, self.query, True) if t.is_done], "Due Date", True, courses)
        if not shown and not finished:
            self.lay.addWidget(QLabel("No tasks here. Add one with Add New Task, or read them from a course syllabus on the classic page." if not tasks else "No task matches."))
        prefs = settings.get_block_colors()
        for heading, rows in TL.group_tasks(shown, self.group, courses, tz, timeutil.local_day(now, tz)):
            if heading:
                h = QLabel(f"<b>{heading}</b> · {len(rows)}")
                self.lay.addWidget(h)
            for t in rows:
                self.lay.addWidget(self._row(t, courses, prefs, cushions, sessions, tz, now, course_id is None))
        if finished:
            head = QToolButton()
            head.setStyleSheet("QToolButton { border: none; background: transparent; font-weight: 700; font-size: 15px; padding: 8px 0; }")
            head.setText(f"{'▾' if self.open_done else '▸'}  Completed ({len(finished)} task{'s' if len(finished) != 1 else ''})")
            head.clicked.connect(self._toggle_done)
            self.lay.addWidget(head, 0, Qt.AlignLeft)
            if self.open_done:
                for t in finished:
                    self.lay.addWidget(self._row(t, courses, prefs, cushions, sessions, tz, now, course_id is None))
        self.lay.addStretch(1)

    def _toggle_done(self):
        self.open_done = not self.open_done
        self.refresh()

    def _row(self, t, courses, prefs, cushions, sessions, tz, now, show_course):
        frame = QFrame()
        frame.setObjectName("card")
        h = QHBoxLayout(frame)
        h.setContentsMargins(12, 6, 10, 6)
        box = QCheckBox()
        box.setChecked(t.is_done)
        box.setToolTip("open it again" if t.is_done else "mark it done")
        box.toggled.connect(lambda on, task=t: self._done(task, on))
        h.addWidget(box)
        color = prefs.get(f"task:{t.id}") or (crud.course_color(courses[t.course_id]) if t.course_id in courses else "#6b7280")
        title = QLabel(f"<span style='color:{color}'>●</span> " + (f"<s>{t.title}</s>" if t.is_done else f"<b>{t.title}</b>"))
        h.addWidget(title, 4)
        if show_course:
            h.addWidget(QLabel(f"<span style='color:{color}'>●</span> {TL.course_label(courses, t) or '–'}"), 2)
        h.addWidget(QLabel(t.category), 1)
        h.addWidget(QLabel(self._fmt_due(t.due, tz)), 2)
        planned = sum(s.minutes for s in sessions if s.task_id == t.id and s.end > now)
        time_text = plan_grid.fmt_minutes(t.remaining_minutes) + " left" + (f"<br>{plan_grid.fmt_minutes(planned)} planned" if planned else "") + (f"<br>{plan_grid.fmt_minutes(t.logged_minutes)} used" if t.logged_minutes else "")
        h.addWidget(QLabel(time_text), 2)
        c = cushions.get(t.id)
        if c is not None and not t.is_done:
            pill = QLabel(_cushion_text(c.cushion_minutes))
            pill.setStyleSheet(f"background: {plan_grid.LEVEL_COLORS[c.level]}; color: #ffffff; border-radius: 10px; padding: 1px 10px; font-weight: 600;")
            pill.setToolTip("the free time left before the deadline, after the work that is due by then")
            h.addWidget(pill, 1)
        else:
            h.addWidget(QLabel(f"{t.start_ahead_days} days ahead" if t.start_ahead_days is not None else ""), 1)
        menu = QToolButton()
        menu.setText("···")
        menu.setPopupMode(QToolButton.InstantPopup)
        menu.setStyleSheet("QToolButton { border: none; background: transparent; font-size: 16px; } QToolButton::menu-indicator { image: none; }")
        pop = QMenu(menu)
        pop.addAction("Edit Task…", lambda task=t: self.edit_task(task.id))
        if planned:
            pop.addAction("Remove Planned Sessions", lambda task=t: self._unplan(task.id))
        pop.addAction("Delete Task…", lambda task=t: self.delete_task(task))
        menu.setMenu(pop)
        h.addWidget(menu)
        return frame

    def _done(self, task, on):
        task_store.set_done(task.id, on)
        linkdone.from_task(task, on)
        self.refresh()
        self.changed.emit()

    def add_task(self):
        course = int(self.which.split(":")[1]) if self.which.startswith("course:") else None
        if TaskDialog(None, course, self.which == "personal", self.window()).exec():
            self.refresh()
            self.changed.emit()

    def edit_task(self, task_id):
        if TaskDialog(task_id, None, False, self.window()).exec():
            self.refresh()
            self.changed.emit()

    def delete_task(self, task):
        if QMessageBox.question(self.window(), "Delete Task", f"Delete “{task.title}”? Its planned study sessions go with it.") == QMessageBox.Yes:
            task_store.delete_task(task.id)
            self.refresh()
            self.changed.emit()

    def _unplan(self, task_id):
        service.unplan_task(task_id)
        self.refresh()
        self.changed.emit()
