"""The windows of the Library: file details, the confirmation of an import and removing files."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from core import crud
from core.database import data_path
from library import browse, covers, syllabus
from views import library_import as LI


def _courses():
    return {c["id"]: crud.label(c) for c in crud.list_courses(section=None)}


def remove_book(book):
    """Takes a file out of the Library: its row, its cover and the stored copy (the original file on the student's drive is never touched)."""
    p = data_path(book["pdf_path"])
    crud.delete_book(book["id"])
    covers.remove_cover(book["id"])
    try:
        if p.exists():
            p.unlink()
    except OSError:
        pass


class EditBookDialog(QDialog):
    """Title, type, lecture, author, edition, year and courses of a file; Remove from Library."""

    def __init__(self, book, parent=None):
        super().__init__(parent)
        self.book = book
        self.removed = False
        self.setWindowTitle("Edit Details")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        stored = QLabel(f"Stored File: {book['pdf_path']}")
        stored.setObjectName("muted")
        lay.addWidget(stored)
        form = QFormLayout()
        self.kind = QComboBox()
        self.kind.addItems(browse.KINDS)
        self.kind.setCurrentText(book["kind"] if book["kind"] in browse.KINDS else "Textbook")
        self.title = QLineEdit(book["title"])
        self.lecture = QLineEdit(book.get("lecture") or "")
        self.lecture_label = QLabel()
        self.author = QLineEdit(book["author"] or "")
        self.edition = QLineEdit(book["edition"] or "")
        self.year = QLineEdit(book.get("year") or "")
        form.addRow("Type", self.kind)
        form.addRow("Title", self.title)
        form.addRow(self.lecture_label, self.lecture)
        form.addRow("Author", self.author)
        form.addRow("Edition", self.edition)
        form.addRow("Year", self.year)
        lay.addLayout(form)
        lay.addWidget(QLabel("Courses (Optional)"))
        self.courses = QListWidget()
        self.courses.setMaximumHeight(150)
        for cid, label in _courses().items():
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, cid)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if cid in book["course_ids"] else Qt.Unchecked)
            self.courses.addItem(item)
        lay.addWidget(self.courses)
        row = QHBoxLayout()
        remove = QPushButton("Remove from Library")
        remove.clicked.connect(self._remove)
        row.addWidget(remove)
        row.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        lay.addLayout(row)
        self.kind.currentTextChanged.connect(self._kind_changed)
        self._kind_changed(self.kind.currentText())

    def _kind_changed(self, kind):
        shown = kind in ("Lecture Notes", "Notes") + browse.HW_KINDS
        self.lecture.setVisible(shown)
        self.lecture_label.setVisible(shown)
        self.lecture_label.setText("Homework Number" if kind in browse.HW_KINDS else "Lecture")

    def _save(self):
        ids = [self.courses.item(i).data(Qt.UserRole) for i in range(self.courses.count()) if self.courses.item(i).checkState() == Qt.Checked]
        kind = self.kind.currentText()
        lecture = self.lecture.text().strip() if self.lecture.isVisible() else ""
        crud.update_book(self.book["id"], self.title.text().strip() or self.book["title"], self.author.text().strip(), self.edition.text().strip(), kind, ids,
                         self.year.text().strip(), lecture)
        if kind == "Syllabus" and self.book["pdf_path"].lower().endswith(".pdf"):
            try:
                syllabus.auto_build(ids, self.book["id"], data_path(self.book["pdf_path"]))
            except Exception:
                pass
        self.accept()

    def _remove(self):
        ask = QMessageBox.question(self, "Remove from Library", "This also deletes the stored copy in the data folder. Your original file is not touched. Remove it?")
        if ask == QMessageBox.Yes:
            remove_book(self.book)
            self.removed = True
            self.accept()


class ImportDialog(QDialog):
    """The page where the student confirms an import: every file found with its guessed type, title, lecture and course (all editable); unchecked files are not imported.
    `chosen()` returns the checked candidates with what was edited."""
    COLS = ["Import", "Status", "File", "Type", "Title", "Lecture / HW No.", "Course", "If in Library"]

    def __init__(self, candidates, parent=None, heading="Import Files"):
        super().__init__(parent)
        self.candidates = candidates
        self.setWindowTitle(heading)
        self.resize(1180, 640)
        self.courses = _courses()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"{len(candidates)} file{'s' if len(candidates) != 1 else ''} found. Untick the ones you do not want; change the type, title, lecture or course where the guess is wrong."))
        bar = QHBoxLayout()
        for text, which, tip in (("Select All", "all", "ticks every file in the list"), ("Deselect All", "none", "unticks every file in the list"),
                                 ("Changed Only", "changed", "ticks only the files that changed since they were imported"),
                                 ("Replace Existing", "replace", "the files the Library has already replace its stored copies"),
                                 ("Keep Existing", "keep", "the Library's copies of the files it has already stay as they are")):
            if which == "changed" and not any(c.status == "Changed" for c in candidates):
                continue
            if which in ("replace", "keep") and not any(c.book_id for c in candidates):
                continue
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, w=which: self._select(w))
            bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)
        self.table = QTableWidget(len(candidates), len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QTableWidget.NoSelection)
        head = self.table.horizontalHeader()
        head.setSectionResizeMode(QHeaderView.Interactive)
        for i, w in enumerate((60, 90, 280, 150, 240, 110, 150, 110)):
            self.table.setColumnWidth(i, w)
        head.setStretchLastSection(True)
        lay.addWidget(self.table, 1)
        self._fill()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Import")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _fill(self):
        self.table.setRowCount(len(self.candidates))
        for r, c in enumerate(self.candidates):
            box = QCheckBox()
            box.setChecked(c.picked if c.picked is not None else c.status != "In Library")
            holder = QTableWidgetItem()
            self.table.setItem(r, 0, holder)
            self.table.setCellWidget(r, 0, box)
            for col, text in ((1, c.status), (2, c.key if len(c.key) < 90 else "..." + c.key[-87:])):
                it = QTableWidgetItem(text)
                it.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(r, col, it)
            kind = QComboBox()
            kind.addItems(browse.KINDS)
            kind.setCurrentText(c.kind if c.kind in browse.KINDS else "Textbook")
            self.table.setCellWidget(r, 3, kind)
            self.table.setCellWidget(r, 4, QLineEdit(c.title))
            self.table.setCellWidget(r, 5, QLineEdit(c.lecture or ""))
            course = QComboBox()
            course.addItem("(none)", None)
            for cid, label in self.courses.items():
                course.addItem(label, cid)
            course.setCurrentIndex(max(0, course.findData(c.course_ids[0])) if c.course_ids else 0)
            self.table.setCellWidget(r, 6, course)
            existing = QComboBox()
            existing.addItems(["Replace", "Keep"])
            existing.setCurrentText(c.existing)
            existing.setEnabled(bool(c.book_id))
            self.table.setCellWidget(r, 7, existing)

    def _read(self):
        """What the table says now, written back to the candidates."""
        for r, c in enumerate(self.candidates):
            c.picked = self.table.cellWidget(r, 0).isChecked()
            c.kind = self.table.cellWidget(r, 3).currentText()
            c.title = self.table.cellWidget(r, 4).text().strip() or c.title
            c.lecture = self.table.cellWidget(r, 5).text().strip()
            cid = self.table.cellWidget(r, 6).currentData()
            c.course_ids = [cid] if cid else []
            if c.book_id:
                c.existing = self.table.cellWidget(r, 7).currentText()

    def _select(self, which):
        self._read()
        LI.select(self.candidates, which)
        self._fill()

    def chosen(self):
        self._read()
        return [c for c in self.candidates if c.picked]


class RemoveDialog(QDialog):
    """Tick many files and remove them from the Library at once (the original files are never touched)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Remove Files")
        self.resize(720, 640)
        self.books = sorted(crud.list_books(), key=lambda b: b["title"].lower())
        self.courses = crud.list_courses(section=None)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Tick the files to remove from the Library. Only the Library's stored copies are deleted; your original files are never touched."))
        row = QHBoxLayout()
        self.course = QComboBox()
        self.course.addItem("All Courses", None)
        for c in self.courses:
            self.course.addItem(crud.label(c), c["id"])
        self.kind = QComboBox()
        self.kind.addItem("All Types", None)
        self.kind.addItems(browse.KINDS)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")
        for w in (self.course, self.kind, self.search):
            row.addWidget(w)
        lay.addLayout(row)
        bar = QHBoxLayout()
        for text, fn in (("Select All", lambda: self._tick(True)), ("Deselect All", lambda: self._tick(False))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)
        self.list = QListWidget()
        lay.addWidget(self.list, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._remove)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self.ticked = set()
        for w in (self.course, self.kind):
            w.currentIndexChanged.connect(self._fill)
        self.search.textChanged.connect(self._fill)
        self.list.itemChanged.connect(self._changed)
        self.removed = 0
        self._fill()

    def _visible(self):
        text, cid, kind = self.search.text().strip().lower(), self.course.currentData(), self.kind.currentData() if self.kind.currentIndex() else None
        out = []
        for b in self.books:
            if cid and cid not in b["course_ids"]:
                continue
            if kind and b["kind"] != kind:
                continue
            if text and text not in b["title"].lower() and text not in b["kind"].lower():
                continue
            out.append(b)
        return out

    def _fill(self, *_):
        self.list.blockSignals(True)
        self.list.clear()
        self.shown = self._visible()
        for b in self.shown:
            item = QListWidgetItem(f"{b['title']}   ·   {b['kind']}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if b["id"] in self.ticked else Qt.Unchecked)
            item.setData(Qt.UserRole, b["id"])
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._count()

    def _changed(self, item):
        (self.ticked.add if item.checkState() == Qt.Checked else self.ticked.discard)(item.data(Qt.UserRole))
        self._count()

    def _tick(self, on):
        for b in self.shown:
            (self.ticked.add if on else self.ticked.discard)(b["id"])
        self._fill()

    def _count(self):
        ok = self.buttons.button(QDialogButtonBox.Ok)
        ok.setText(f"Remove {len(self.ticked)} File{'s' if len(self.ticked) != 1 else ''}")
        ok.setEnabled(bool(self.ticked))

    def _remove(self):
        n = len(self.ticked)
        if QMessageBox.question(self, "Remove Files", f"Remove {n} file{'s' if n != 1 else ''} from the Library? This cannot be undone.") != QMessageBox.Yes:
            return
        for b in self.books:
            if b["id"] in self.ticked:
                remove_book(b)
                self.removed += 1
        self.accept()
