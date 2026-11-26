"""The windows of the Courses page: add a course, edit it (and delete it), add a web link."""
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout)

from core import crud
from library import photos

NEW_CATEGORY = "New Category…"


class _CourseForm(QDialog):
    """The fields a course has: status, name, number, semester, school, category, photo (and a tile color when editing)."""

    def __init__(self, title, course=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.course = course
        self.photo_bytes = None
        self.remove_photo = False
        self.color = crud.course_color(course) if course else None
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.status = QComboBox()
        self.status.addItems(list(crud.STATUSES))
        if course:
            self.status.setCurrentText(crud.course_status(course))
        self.name = QLineEdit(course["name"] if course and course["name"] != course["code"] else "")
        self.code = QLineEdit(course["code"] or "" if course else "")
        self.code.setPlaceholderText("MATH 101")
        self.sem = QLineEdit(course["semester"] or "" if course else "Fall 2026")
        self.school = QLineEdit(course.get("school") or "" if course else "")
        self.school.setPlaceholderText("Your University")
        self.category = QComboBox()
        self.category.setEditable(False)
        self.category.addItem("None")
        self.category.addItems(crud.all_categories())
        self.category.addItem(NEW_CATEGORY)
        cur = course.get("category") if course else None
        self.category.setCurrentText(cur if cur else "None")
        self.new_category = QLineEdit()
        self.new_category.setPlaceholderText("New category name")
        self.new_category.hide()
        self.category.currentTextChanged.connect(lambda t: self.new_category.setVisible(t == NEW_CATEGORY))
        form.addRow("Status", self.status)
        form.addRow("Name", self.name)
        form.addRow("Course Number (Optional for Self-Study)", self.code)
        form.addRow("Semester", self.sem)
        form.addRow("School", self.school)
        form.addRow("Category (Optional)", self.category)
        form.addRow("", self.new_category)
        if course:
            self.color_btn = QPushButton("Choose Tile Color")
            self._paint_color()
            self.color_btn.clicked.connect(self._pick_color)
            form.addRow("Tile Color", self.color_btn)
        row = QHBoxLayout()
        self.photo_label = QLabel("No photo chosen" if not (course and photos.photo_path(course["id"])) else "A photo is set")
        pick = QPushButton("Choose Photo…")
        pick.clicked.connect(self._pick_photo)
        row.addWidget(pick)
        if course and photos.photo_path(course["id"]):
            rm = QPushButton("Remove Photo")
            rm.clicked.connect(self._remove_photo)
            row.addWidget(rm)
        row.addWidget(self.photo_label, 1)
        form.addRow("Photo (Optional)", row)
        lay.addLayout(form)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        self.extra_row = QHBoxLayout()
        lay.addLayout(self.extra_row)
        lay.addWidget(self.buttons)
        for w in (self.name, self.code):
            w.textChanged.connect(self._ready)
        self.status.currentTextChanged.connect(self._ready)
        self._ready()

    def _ready(self, *_):
        ok = bool((self.name.text().strip() or self.code.text().strip()) and (self.code.text().strip() or self.status.currentText() == "Self-Study"))
        if not self.course:
            ok = bool(self.name.text().strip() and (self.code.text().strip() or self.status.currentText() == "Self-Study"))
        self.buttons.button(QDialogButtonBox.Save).setEnabled(ok)

    def _paint_color(self):
        self.color_btn.setStyleSheet(f"QPushButton {{ background: {self.color}; color: #ffffff; border: none; border-radius: 8px; padding: 7px 16px; }}")

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.color), self, "Tile Color")
        if c.isValid():
            self.color = c.name()
            self._paint_color()

    def _pick_photo(self):
        f, _ = QFileDialog.getOpenFileName(self, "Choose Photo", str(Path.home()), "Images (*.png *.jpg *.jpeg *.webp *.heic *.heif *.bmp *.gif)")
        if f:
            self.photo_bytes = Path(f).read_bytes()
            self.remove_photo = False
            self.photo_label.setText(Path(f).name)

    def _remove_photo(self):
        self.remove_photo, self.photo_bytes = True, None
        self.photo_label.setText("The photo will be removed")

    def category_value(self):
        t = self.category.currentText()
        if t == NEW_CATEGORY:
            return crud.normalize_category(self.new_category.text())
        return None if t == "None" else t

    def _save(self):
        raise NotImplementedError


class AddCourseDialog(_CourseForm):
    def __init__(self, parent=None):
        super().__init__("Add Course", None, parent)
        self.buttons.button(QDialogButtonBox.Save).setText("Add Course")
        self.course_id = None

    def _save(self):
        status = self.status.currentText()
        cid = crud.add_course(self.code.text().strip(), self.name.text().strip(), self.sem.text().strip(), 0, status, self.school.text().strip(), self.category_value())
        if self.photo_bytes and not photos.save_photo(cid, self.photo_bytes):
            QMessageBox.information(self, "Photo", "The course was added, but that photo could not be read.")
        self.course_id = cid
        self.accept()


class EditCourseDialog(_CourseForm):
    def __init__(self, course, parent=None):
        super().__init__("Edit Course", course, parent)
        self.deleted = False
        delete = QPushButton("Delete Course")
        delete.clicked.connect(self._delete)
        self.extra_row.addWidget(delete)
        self.extra_row.addStretch(1)

    def _save(self):
        c, cid = self.course, self.course["id"]
        code, name = self.code.text().strip(), self.name.text().strip()
        crud.update_course_fields(cid, code, name or code, self.sem.text().strip(), self.school.text().strip(), self.category_value())
        photos.rename_photo(cid)
        status = self.status.currentText()
        if status != crud.course_status(c):
            crud.set_course_status(cid, status)
        crud.set_course_color(cid, self.color if self.color != crud.course_color({**c, "color": None}) else None)
        if self.remove_photo:
            photos.remove_photo(cid)
        if self.photo_bytes and not photos.save_photo(cid, self.photo_bytes):
            QMessageBox.information(self, "Photo", "That photo could not be read.")
        self.accept()

    def _delete(self):
        ask = QMessageBox.question(self, "Delete Course", "This also deletes the course's notes, homework, flashcards and errata. It cannot be undone. Delete it?")
        if ask == QMessageBox.Yes:
            cid = self.course["id"]
            crud.delete_course(cid)
            photos.remove_photo(cid)
            self.deleted = True
            self.accept()


class AddLinkDialog(QDialog):
    def __init__(self, course_id, parent=None):
        super().__init__(parent)
        self.course_id = course_id
        self.setWindowTitle("Add Link")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://")
        self.title = QLineEdit()
        self.title.setPlaceholderText("Class Page")
        form.addRow("URL", self.url)
        form.addRow("Title (Optional)", self.title)
        lay.addLayout(form)
        self.hint = QLabel()
        self.hint.setObjectName("muted")
        lay.addWidget(self.hint)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Save).setText("Add Link")
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self.url.textChanged.connect(self._check)
        self._check()

    def _check(self, *_):
        text = self.url.text().strip()
        bad = bool(text) and not crud.normalize_url(text)
        self.hint.setText("That does not look like a web address." if bad else "")
        self.buttons.button(QDialogButtonBox.Save).setEnabled(bool(text) and not bad)

    def _save(self):
        crud.add_link(self.course_id, self.title.text(), self.url.text())
        self.accept()
