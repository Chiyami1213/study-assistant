"""The window to add or change a task of the planner (title, course or personal, category, due date and time, estimate, start ahead)."""
from datetime import date, time, timedelta

from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QSpinBox, QTimeEdit, QVBoxLayout)

from core import crud
from planner import store, task_store, tasks as T, timeutil
from planner.models import PlannerError


class TaskDialog(QDialog):
    def __init__(self, task_id=None, default_course=None, default_personal=False, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.editing = task_store.get_task(task_id) if task_id is not None else None
        e = self.editing
        self.setWindowTitle("Task")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(e.title if e else "")
        self.title.setPlaceholderText("Homework 6")
        form.addRow("Title", self.title)
        self.personal = QCheckBox("Personal (Not for School)")
        self.personal.setToolTip("a personal task has no course, and it can be planned in a break and outside the term")
        self.personal.setChecked(bool(e.personal) if e else bool(default_personal))
        form.addRow("", self.personal)
        self.course = QComboBox()
        self.course.addItem("No Course", 0)
        for c in crud.list_courses(section=None):
            if crud.course_status(c) != "Completed" or (e and e.course_id == c["id"]):
                self.course.addItem(crud.label(c), c["id"])
        want = e.course_id if e else default_course
        self.course.setCurrentIndex(max(0, self.course.findData(want or 0)))
        form.addRow("Course", self.course)
        self.category = QComboBox()
        self.category.addItems(list(T.CATEGORIES))
        self.category.setCurrentText(e.category if e else "Homework")
        form.addRow("Category", self.category)
        tz = store.get_term().zone
        due = timeutil.to_local(e.due, tz) if e and e.due else None
        self.has_due = QCheckBox("Has a Due Date")
        self.has_due.setChecked(bool(due) if e else True)
        d = due.date() if due else date.today() + timedelta(days=7)
        t = due.time().replace(second=0, microsecond=0) if due else time(23, 59)
        self.due_date = QDateEdit(QDate(d.year, d.month, d.day))
        self.due_date.setCalendarPopup(True)
        self.due_time = QTimeEdit(QTime(t.hour, t.minute))
        row = QHBoxLayout()
        row.addWidget(self.has_due)
        row.addWidget(self.due_date)
        row.addWidget(self.due_time)
        form.addRow("Due", row)
        self.estimate = QSpinBox()
        self.estimate.setRange(*T.ESTIMATE_RANGE)
        self.estimate.setSingleStep(5)
        self.estimate.setSuffix(" min")
        form.addRow("Estimate", self.estimate)
        self.default_note = QLabel()
        self.default_note.setObjectName("muted")
        form.addRow("", self.default_note)
        self.ahead_on = QCheckBox("Start Ahead")
        self.ahead_on.setToolTip("plan work only from this many days before the due date")
        self.ahead = QSpinBox()
        self.ahead.setRange(0, T.MAX_START_AHEAD)
        self.ahead.setSuffix(" days before the due date")
        self.ahead.setValue(e.start_ahead_days if e and e.start_ahead_days is not None else 3)
        self.ahead_on.setChecked(bool(e and e.start_ahead_days is not None))
        row2 = QHBoxLayout()
        row2.addWidget(self.ahead_on)
        row2.addWidget(self.ahead)
        form.addRow("", row2)
        lay.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Save Task" if e else "Add Task")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.buttons = buttons
        self._default = None
        self.course.currentIndexChanged.connect(self._defaults)
        self.category.currentTextChanged.connect(self._defaults)
        self.personal.toggled.connect(self._refresh)
        self.has_due.toggled.connect(self._refresh)
        self.ahead_on.toggled.connect(self._refresh)
        self.title.textChanged.connect(self._refresh)
        self.estimate.setValue(e.estimate_minutes if e else task_store.estimate_for(self._course_id() or None, self.category.currentText()))
        self._defaults(keep=bool(e))
        self._refresh()

    def _course_id(self):
        return 0 if self.personal.isChecked() else (self.course.currentData() or 0)

    def _defaults(self, *_, keep=False):
        self._default = task_store.estimate_for(self._course_id() or None, self.category.currentText())
        self.default_note.setText(f"The default for this course and category is {self._default} minutes; change it for this task only.")
        if not keep:
            self.estimate.setValue(self._default)

    def _refresh(self, *_):
        self.course.setEnabled(not self.personal.isChecked())
        due = self.has_due.isChecked()
        self.due_date.setEnabled(due)
        self.due_time.setEnabled(due)
        self.ahead_on.setEnabled(due)
        self.ahead.setEnabled(due and self.ahead_on.isChecked())
        self.buttons.button(QDialogButtonBox.Save).setEnabled(bool(self.title.text().strip()))
        self._defaults(keep=True)

    def _save(self):
        tz = store.get_term().zone
        course_id = self._course_id()
        due = timeutil.to_utc(self.due_date.date().toPython(), self.due_time.time().toPython(), tz) if self.has_due.isChecked() else None
        days = int(self.ahead.value()) if (self.has_due.isChecked() and self.ahead_on.isChecked()) else None
        est = int(self.estimate.value())
        try:
            if self.editing:
                task_store.update_task(self.task_id, title=self.title.text().strip(), course_id=course_id or None, category=self.category.currentText(), due=due, estimate=est,
                                       start_ahead_days=days, personal=self.personal.isChecked())
            else:
                task_store.add_task(self.title.text().strip(), course_id or None, self.category.currentText(), due, None if est == self._default else est, days, personal=self.personal.isChecked())
        except PlannerError as err:
            QMessageBox.warning(self, "Task", str(err))
            return
        self.accept()
