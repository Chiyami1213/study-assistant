"""The Note Reader (native): up to three windows side by side, each reading a Library file. A Notes window shows one of the course's HTML notes with a tab for each part it has (notes, mind map, equation sheet,
assumptions, quiz, errata); a Reference window shows any file of the Library: a PDF in the native reader, an HTML page in a web view. What is open is remembered (the same saved state as the classic reader).
Not native yet: the links from a note to the slides of its lecture and to the source of an equation in the textbook, the errata marks on a PDF, full screen, and dragging a window out."""
import re

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QSplitter, QStackedWidget, QTabBar, QToolButton, QVBoxLayout, QWidget)

from core import crud, settings
from core.database import data_path
from qtui import notehtml
from qtui.pages.pdf_page import PdfPage
from study import outline
from study import labstate as LS

BASE = QUrl("https://localhost/")
KIND_ORDER = ["Textbook", "Lecture Notes", "Notes", "Homework", "Homework Solution", "Exam", "Graded Homework", "Practice Exam", "Exam Solution", "Graded Exam", "Exam Preparation", "Exam Reflection"]


class NoteView(QWebEngineView):
    """A web view that reports the highlights of a guide (Qt WebChannel)."""

    def __init__(self):
        super().__init__()
        self.channel = QWebChannel(self)
        self.bridge = notehtml.HighlightBridge()
        self.channel.registerObject("bridge", self.bridge)
        self.page().setWebChannel(self.channel)


def _course_name(courses, i):
    return (crud.show_code(courses[i]["code"]) or courses[i]["name"]) if i in courses else "No Course"


class ReaderWindow(QFrame):
    """One window of the reader. `kind` is 'notes' or 'reference'; `changed` is emitted when it should be remembered."""
    changed = Signal()
    close_requested = Signal(str)

    def __init__(self, win, closable):
        super().__init__()
        self.win = win
        self.setObjectName("card")
        self.book = None
        self.parts = []
        self.text = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        bar = QHBoxLayout()
        self.course = QComboBox()
        self.course.setMinimumWidth(110)
        self.kind = QComboBox()
        self.file = QComboBox()
        self.file.setMinimumWidth(180)
        self.file.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.file.setMinimumContentsLength(14)
        self.kind.setVisible(win["type"] == "reference")
        for w in (self.course, self.kind):
            bar.addWidget(w)
        bar.addWidget(self.file, 1)
        close = QToolButton()
        close.setText("✕")
        close.setToolTip("close this window")
        close.setVisible(closable)
        close.clicked.connect(lambda: self.close_requested.emit(win["id"]))
        bar.addWidget(close)
        lay.addLayout(bar)
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setVisible(win["type"] == "notes")
        self.tabs.currentChanged.connect(self._tab)
        lay.addWidget(self.tabs)
        self.stack = QStackedWidget()
        self.web = NoteView()
        self.pdf = PdfPage(has_back=False, margins=(0, 0, 0, 0))
        self.pdf.page_changed.connect(self._remember_page)
        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        for w in (self.web, self.pdf, self.empty):
            self.stack.addWidget(w)
        lay.addWidget(self.stack, 1)
        self._loading = True
        self._fill_courses()
        self.course.currentIndexChanged.connect(self._course_changed)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.file.currentIndexChanged.connect(self._file_changed)
        self._loading = False
        self._file_changed()

    # ---------------------------------------------------------------- the pickers
    def _courses(self):
        return {c["id"]: c for s in crud.STATUSES for c in crud.courses_by_status(s)}

    def _books(self):
        return crud.list_books()

    def _fill_courses(self):
        courses = {c["id"]: c for c in crud.list_courses(section=None)}
        self.courses_by_id = courses
        order = {c["id"]: n for n, c in enumerate(c for s in crud.STATUSES for c in crud.courses_by_status(s))}
        if self.win["type"] == "notes":
            ids = [i for i in order if LS._course_notes(i)]
        else:
            own = lambda b: next((i for i in b["course_ids"] if i in courses), 0)
            ids = sorted({own(b) for b in self._books()}, key=lambda i: (order.get(i, 999), i))
        self.course.blockSignals(True)
        self.course.clear()
        for i in ids:
            self.course.addItem(_course_name(courses, i), i)
        want = None
        lab = settings.get_lab()
        if self.win["type"] == "notes":
            want = lab.get("course")
        elif self.win.get("book"):
            b = crud.get_book(self.win["book"])
            if b:
                want = next((i for i in b["course_ids"] if i in courses), 0)
        if self.course.findData(want) >= 0:
            self.course.setCurrentIndex(self.course.findData(want))
        self.course.blockSignals(False)
        self._fill_kinds()

    def _fill_kinds(self):
        if self.win["type"] != "reference":
            self._fill_files()
            return
        cid = self.course.currentData()
        own = lambda b: next((i for i in b["course_ids"] if i in self.courses_by_id), 0)
        in_course = [b for b in self._books() if own(b) == cid]
        kinds = [k for k in KIND_ORDER if any(b["kind"] == k for b in in_course)] + sorted({b["kind"] for b in in_course} - set(KIND_ORDER))
        self.kind.blockSignals(True)
        self.kind.clear()
        self.kind.addItems(kinds)
        cur = crud.get_book(self.win.get("book")) if self.win.get("book") else None
        if cur and cur["kind"] in kinds:
            self.kind.setCurrentText(cur["kind"])
        self.kind.blockSignals(False)
        self._fill_files()

    def _fill_files(self):
        cid = self.course.currentData()
        self.file.blockSignals(True)
        self.file.clear()
        if self.win["type"] == "notes":
            files = LS._course_notes(cid)
            label = lambda b: (f"Lec {b['lecture']} · " if b.get("lecture") else "") + b["title"]
        else:
            own = lambda b: next((i for i in b["course_ids"] if i in self.courses_by_id), 0)
            lec = lambda b: (tuple(int(n) for n in re.findall(r"\d+", b.get("lecture") or "")), b["title"].lower())
            files = sorted((b for b in self._books() if own(b) == cid and b["kind"] == self.kind.currentText()), key=lec)
            label = lambda b: (("HW " if b["kind"] == "Homework" else "Lec ") + b["lecture"] + " · " if b.get("lecture") else "") + b["title"]
        for b in files:
            self.file.addItem(label(b), b["id"])
        want = self.win.get("book") if self.win["type"] == "reference" else settings.get_lab().get("notes", {}).get(str(cid))
        if self.file.findData(want) >= 0:
            self.file.setCurrentIndex(self.file.findData(want))
        self.file.blockSignals(False)

    def _course_changed(self, *_):
        if self._loading:
            return
        self._fill_kinds()
        self._file_changed()

    def _kind_changed(self, *_):
        if self._loading:
            return
        self._fill_files()
        self._file_changed()

    # ---------------------------------------------------------------- showing a file
    def _file_changed(self, *_):
        if self._loading:
            return
        bid = self.file.currentData()
        book = crud.get_book(bid) if bid else None
        self.book = book
        if not book:
            self.tabs.blockSignals(True)
            while self.tabs.count():
                self.tabs.removeTab(0)
            self.tabs.blockSignals(False)
            self.empty.setText("This course has no HTML notes yet. Add a note to the Library (type Notes) and it can be read here." if self.win["type"] == "notes" else "Add a file in the Library to read it here.")
            self.stack.setCurrentWidget(self.empty)
            return
        path = data_path(book["pdf_path"])
        if not path.exists():
            self.empty.setText("The stored file is missing.")
            self.stack.setCurrentWidget(self.empty)
            return
        if self.win["type"] == "notes":
            LS._remember(course=self.course.currentData(), notes={**settings.get_lab().get("notes", {}), str(self.course.currentData()): book["id"]})
        else:
            self.win["book"] = book["id"]
            self.changed.emit()
        if book["pdf_path"].lower().endswith((".html", ".htm")):
            self.text = path.read_text(encoding="utf-8", errors="replace")
            if self.win["type"] == "notes":
                self.parts = outline.parts(self.text)
                last = settings.get_lab().get("tabs", {}).get(str(book["id"]))
                self.tabs.blockSignals(True)
                while self.tabs.count():
                    self.tabs.removeTab(0)
                for p in self.parts:
                    self.tabs.addTab(p["label"])
                labels = [p["label"] for p in self.parts]
                self.tabs.setCurrentIndex(labels.index(last) if last in labels else 0)
                self.tabs.blockSignals(False)
                self._show_part()
            else:
                self.web.setHtml(notehtml.note_html(book, self.text), BASE)
                self.stack.setCurrentWidget(self.web)
        else:
            page = settings.get_lab().get("pages", {}).get(str(book["id"]), 1)
            self.pdf.open(book, page)
            self.stack.setCurrentWidget(self.pdf)

    def _show_part(self):
        i = self.tabs.currentIndex()
        if self.book is None or not (0 <= i < len(self.parts)):
            return
        part = self.parts[i]
        self.web.setHtml(notehtml.note_html(self.book, self.text, part["section"]), BASE)
        self.stack.setCurrentWidget(self.web)

    def _tab(self, i):
        if self.book is None or not (0 <= i < len(self.parts)):
            return
        lab = settings.get_lab()
        LS._remember(tabs={**lab.get("tabs", {}), str(self.book["id"]): self.parts[i]["label"]})
        self._show_part()

    def _remember_page(self, page):
        if self.book is None:
            return
        pages = settings.get_lab().get("pages", {})
        if pages.get(str(self.book["id"])) != page:
            LS._remember(pages={**pages, str(self.book["id"]): page})


class NoteReaderPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 12)
        top = QHBoxLayout()
        title = QLabel("Note Reader")
        title.setObjectName("h1")
        top.addWidget(title)
        top.addStretch(1)
        self.add = QToolButton()
        self.add.setText("+ Add Window")
        self.add.setPopupMode(QToolButton.InstantPopup)
        self.add.setStyleSheet("QToolButton { border: 1px solid rgba(128,128,128,0.5); border-radius: 8px; padding: 7px 16px; } QToolButton::menu-indicator { image: none; }")
        menu = QMenu(self.add)
        menu.addAction("Reference Window (Any File)", lambda: self._add("reference"))
        menu.addAction("Notes Window (a Course's Notes)", lambda: self._add("notes"))
        self.add.setMenu(menu)
        top.addWidget(self.add)
        root.addLayout(top)
        self.split = QSplitter(Qt.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.split.splitterMoved.connect(self._moved)
        root.addWidget(self.split, 1)
        self.windows = []
        self.reload()

    def reload(self):
        """Opens the windows that were left open."""
        for w in self.windows:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self.windows = []
        wins = LS._windows()
        for win in wins[:LS.MAX_WINDOWS]:
            self._build(dict(win), len(wins) > 1)
        self._sizes()
        self.add.setEnabled(len(self.windows) < LS.MAX_WINDOWS)

    def _build(self, win, closable):
        w = ReaderWindow(win, closable)
        w.changed.connect(self._save)
        w.close_requested.connect(self._close)
        self.split.addWidget(w)
        self.windows.append(w)

    def _sizes(self):
        weights = LS._weights([w.win for w in self.windows])
        total = sum(weights) or 1
        width = max(self.split.width(), 1200)
        self.split.setSizes([int(width * x / total) for x in weights])

    def _moved(self, *_):
        sizes = self.split.sizes()
        total = sum(sizes) or 1
        lab = settings.get_lab()
        LS._remember(widths={**lab.get("widths", {}), **{w.win["id"]: round(s * len(sizes) / total, 3) for w, s in zip(self.windows, sizes)}})

    def _save(self):
        LS._save_windows([w.win for w in self.windows])

    def _add(self, kind):
        if len(self.windows) >= LS.MAX_WINDOWS:
            return
        ids = {w.win["id"] for w in self.windows}
        n = 1
        while f"{kind[0]}{n}" in ids:
            n += 1
        self._build({"id": f"{kind[0]}{n}", "type": kind, **({"book": None} if kind == "reference" else {})}, True)
        self._save()
        self._sizes()
        self.add.setEnabled(len(self.windows) < LS.MAX_WINDOWS)

    def _close(self, wid):
        if len(self.windows) <= 1:
            return
        for w in list(self.windows):
            if w.win["id"] == wid:
                self.windows.remove(w)
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._save()
        self._sizes()
        self.add.setEnabled(True)
