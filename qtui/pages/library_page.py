"""The Library (native): the files by type, course, date added or title, as cards, tiles or a table; open, edit, add, update from a folder and remove files.
Opening a file is the window's job (`open_book`); Tidy Up and Prompt for AI are still on the classic page (`classic_requested`)."""
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QScrollArea, QTableWidget,
                               QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

from core import crud
from library import browse
from qtui.covers import CoverCache
from qtui.flow import FlowLayout
from qtui.library_dialogs import EditBookDialog, ImportDialog, RemoveDialog
from qtui.widgets import Segmented
from views import library_import as LI

PAGE = 120                                   # files drawn at once in a list; the rest come with Show More
VIEWS = [("Cards", "Cards"), ("Tiles", "Tiles"), ("Details", "Details")]


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


def _chip(text, color=None):
    lab = QLabel(text)
    css = "font-size: 11px; padding: 1px 7px; border-radius: 9px; background: transparent; "
    css += f"border: 1px solid {color}; color: {color};" if color else "border: 1px solid rgba(128,128,128,0.5);"
    lab.setStyleSheet(css)
    return lab


class BookCard(QFrame):
    """One file as a card (a cover, the title, its type and courses) or as a tile (the cover small, the text beside it). A click opens it."""
    open_requested = Signal(int)
    edit_requested = Signal(int)
    remove_requested = Signal(int)

    def __init__(self, book, courses, cache, tile=False):
        super().__init__()
        self.book, self.cache, self.tile = book, cache, tile
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        w, h = (70, 94) if tile else (150, 200)
        self.cover = QLabel()
        self.cover.setFixedSize(w, h)
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover_size = (w, h)
        self._paint_cover()
        linked = [courses[i] for i in book["course_ids"] if i in courses]
        kind = book["kind"] + (f" · {'HW' if book['kind'] in browse.HW_KINDS else 'Lec'} {book['lecture']}" if book.get("lecture") else "")
        title = QLabel(book["title"])
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 600; background: transparent;")
        title.setMaximumHeight(40 if not tile else 60)
        menu = QToolButton()
        menu.setText("···")
        menu.setCursor(Qt.PointingHandCursor)
        menu.setStyleSheet("QToolButton { border: none; background: transparent; font-size: 16px; } QToolButton::menu-indicator { image: none; }")
        menu.setPopupMode(QToolButton.InstantPopup)
        pop = QMenu(menu)
        pop.addAction("Open", lambda: self.open_requested.emit(book["id"]))
        pop.addAction("Edit Details…", lambda: self.edit_requested.emit(book["id"]))
        pop.addAction("Remove from Library…", lambda: self.remove_requested.emit(book["id"]))
        menu.setMenu(pop)
        kind_label = QLabel(kind)
        kind_label.setObjectName("muted")
        chips = QHBoxLayout()
        chips.setSpacing(4)
        for c in linked[:3]:
            chips.addWidget(_chip(crud.show_code(c["code"]) or c["name"], crud.course_color(c)))
        chips.addStretch(1)
        if not tile:
            self.setFixedWidth(176)
            lay = QVBoxLayout(self)
            lay.setContentsMargins(10, 10, 10, 8)
            lay.setSpacing(6)
            lay.addWidget(self.cover, 0, Qt.AlignHCenter)
            row = QHBoxLayout()
            row.addWidget(title, 1)
            row.addWidget(menu, 0, Qt.AlignTop)
            lay.addLayout(row)
            lay.addWidget(kind_label)
            lay.addLayout(chips)
            small = " · ".join(x for x in (book["edition"], book.get("year")) if x)
            if small or book["author"]:
                extra = QLabel(" · ".join(x for x in (book["author"], small) if x))
                extra.setObjectName("muted")
                extra.setWordWrap(True)
                lay.addWidget(extra)
            lay.addStretch(1)
        else:
            self.setFixedSize(400, 116)
            lay = QHBoxLayout(self)
            lay.setContentsMargins(10, 10, 10, 10)
            lay.addWidget(self.cover)
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(title)
            col.addWidget(kind_label)
            col.addLayout(chips)
            added = QLabel("Added " + (book.get("added_at") or "")[:10])
            added.setObjectName("muted")
            col.addWidget(added)
            col.addStretch(1)
            lay.addLayout(col, 1)
            lay.addWidget(menu, 0, Qt.AlignTop)
        cache.ready.connect(self._cover_ready)

    def _paint_cover(self):
        self.cover.setPixmap(self.cache.get(self.book, *self.cover_size))

    def _cover_ready(self, book_id):
        if book_id == self.book["id"]:
            try:
                self._paint_cover()
            except RuntimeError:                       # the card was removed in the meantime
                pass

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.open_requested.emit(self.book["id"])
        super().mouseReleaseEvent(e)


class Tile(QFrame):
    """A tile of the overview: a type with its number of titles, or a course with its color."""
    clicked = Signal()

    def __init__(self, title, count, color=None, subtitle=""):
        super().__init__()
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(230, 104)
        if color:
            self.setStyleSheet(f"QFrame#card {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {color}, stop:1 #1b2540); border: none; border-radius: 12px; }} QLabel {{ color: #ffffff; background: transparent; }}")
        else:
            self.setStyleSheet("QFrame#card { border-left: 4px solid #4c8dff; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        head = QLabel(title)
        head.setStyleSheet("font-size: 16px; font-weight: 700; background: transparent;")
        head.setWordWrap(True)
        head.setMaximumHeight(44)
        lay.addWidget(head)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet("font-size: 12px; background: transparent;")
            lay.addWidget(sub)
        lay.addStretch(1)
        lay.addWidget(QLabel(f"{count} {'title' if count == 1 else 'titles'}"))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class Fold(QWidget):
    """A heading that folds its files away with a click (the days, months or years of the timeline)."""

    def __init__(self, title, count, body, open_=True):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.head = QPushButton()
        self.head.setStyleSheet("QPushButton { text-align: left; border: none; background: transparent; font-weight: 700; font-size: 15px; padding: 6px 0; }")
        self.head.setCursor(Qt.PointingHandCursor)
        self.title, self.count, self.body = title, count, body
        self.head.clicked.connect(lambda: self.set_open(not self.body.isVisible()))
        lay.addWidget(self.head)
        lay.addWidget(body)
        self.set_open(open_)

    def set_open(self, on):
        self.body.setVisible(on)
        self.head.setText(f"{'▾' if on else '▸'}  {self.title}   ({self.count})")


class LibraryPage(QWidget):
    open_book = Signal(int)
    classic_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.cache = CoverCache()
        self.s = {"sort": "Type", "tile": None, "inner": {}, "view": "Cards", "desc": True, "unit": "Day", "search": ""}
        self.shown = {}
        self.budget = PAGE
        self.books, self.courses = [], {}
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 28, 40, 20)
        root.setSpacing(10)
        top = QHBoxLayout()
        title = QLabel("Library")
        title.setObjectName("h1")
        top.addWidget(title)
        top.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search the Library")
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self._search)
        top.addWidget(self.search)
        imp = QToolButton()
        imp.setText("Import")
        imp.setObjectName("importbtn")
        imp.setPopupMode(QToolButton.InstantPopup)
        imp.setCursor(Qt.PointingHandCursor)
        imp.setStyleSheet("QToolButton { border: 1px solid rgba(128,128,128,0.5); border-radius: 8px; padding: 7px 16px; } QToolButton::menu-indicator { image: none; }")
        menu = QMenu(imp)
        menu.addAction("Add Files…", self.add_files)
        menu.addAction("Update From Folder…", self.update_from_folder)
        menu.addAction("Remove Files…", self.remove_files)
        menu.addSeparator()
        menu.addAction("Tidy Up (Classic Page)", lambda: self.classic_requested.emit("tidy"))
        menu.addAction("Prompt for AI (Classic Page)", lambda: self.classic_requested.emit("prompt"))
        imp.setMenu(menu)
        top.addWidget(imp)
        root.addLayout(top)
        bar = QHBoxLayout()
        self.back = QPushButton("‹ All Types")
        self.back.clicked.connect(self._back)
        self.view = Segmented(VIEWS, self.s["view"])
        self.view.changed.connect(self._set_view)
        self.order = QPushButton("Newest First")
        self.order.clicked.connect(self._reverse)
        self.unit = Segmented([(u, u) for u in browse.TIMELINE_UNITS], self.s["unit"])
        self.unit.changed.connect(self._set_unit)
        self.collapse = QPushButton("Collapse All")
        self.collapse.clicked.connect(self._collapse_all)
        self.sort = QComboBox()
        self.sort.setFixedWidth(190)
        self.sort.currentTextChanged.connect(self._set_sort)
        for w in (self.back, self.view, self.unit, self.order, self.collapse):
            bar.addWidget(w)
        bar.addStretch(1)
        bar.addWidget(self.sort)
        root.addLayout(bar)
        self.count = QLabel()
        self.count.setObjectName("muted")
        root.addWidget(self.count)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.body = QWidget()
        self.body.setObjectName("page")
        self.blay = QVBoxLayout(self.body)
        self.blay.setContentsMargins(0, 0, 0, 0)
        self.blay.setSpacing(10)
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)
        self.folds = []
        self.refresh()

    # ---------------------------------------------------------------- state
    def _search(self, text):
        self.s["search"] = text.strip()
        self.draw()

    def _set_view(self, key):
        self.s["view"] = key
        self.draw()

    def _set_unit(self, key):
        self.s["unit"] = key
        self.draw()

    def _reverse(self):
        self.s["desc"] = not self.s["desc"]
        self.draw()

    def _collapse_all(self):
        any_open = any(f.body.isVisible() for f in self.folds)
        for f in self.folds:
            f.set_open(not any_open)
        self.collapse.setText("Expand All" if any_open else "Collapse All")

    def _set_sort(self, text):
        key = text.replace("Sort: ", "")
        if not key:
            return
        s = self.s
        if s["tile"] is None and s["sort"] in browse.INNER:
            if key != s["sort"]:
                s["sort"], s["tile"] = key, None
        elif s["tile"] is not None:
            s["inner"][s["sort"]] = key
        else:
            s["sort"] = key
        self.draw()

    def _back(self):
        self.s["tile"] = None
        self.draw()

    def _open_tile(self, key):
        self.s["tile"] = key
        self.draw()

    def refresh(self):
        """Reads the files again (after an import, an edit or a removal)."""
        self.books = crud.list_books()
        self.courses = {c["id"]: c for c in crud.list_courses(section=None)}
        self.draw()

    # ---------------------------------------------------------------- drawing
    def _matches(self):
        text = self.s["search"].lower()
        if not text:
            return None
        out = []
        for b in self.books:
            labels = " ".join(crud.label(self.courses[i]) for i in b["course_ids"] if i in self.courses)
            if text in " ".join(str(x or "") for x in (b["title"], b["kind"], b["author"], labels)).lower():
                out.append(b)
        return out

    def draw(self):
        s = self.s
        _clear(self.blay)
        self.folds = []
        self.budget = PAGE + 40
        found = self._matches()
        in_tile = s["sort"] in browse.INNER and s["tile"] is not None and found is None
        overview = s["sort"] in browse.INNER and s["tile"] is None and found is None
        inner = None
        # the sort box: the usual sorts at the overview, the sorts inside a tile within a tile
        self.sort.blockSignals(True)
        self.sort.clear()
        if in_tile:
            options = browse.INNER[s["sort"]]
            inner = s["inner"].get(s["sort"], options[0])
            if inner not in options:
                inner = options[0]
            self.sort.addItems([f"Sort: {o}" for o in options])
            self.sort.setCurrentText(f"Sort: {inner}")
        else:
            self.sort.addItems([f"Sort: {o}" for o in browse.SORTS])
            self.sort.setCurrentText(f"Sort: {s['sort']}")
        self.sort.setEnabled(found is None)
        self.sort.blockSignals(False)
        timeline = found is None and (s["sort"] == "Date Added" or inner == "Date Added")
        self.back.setVisible(in_tile)
        self.back.setText("‹ All Types" if s["sort"] == "Type" else "‹ All Courses")
        files_shown = not overview
        self.view.setVisible(files_shown)
        for b in self.view.group.buttons():
            b.setChecked(b.text() == s["view"])
        self.unit.setVisible(timeline)
        self.order.setVisible(timeline)
        self.order.setText("Newest First" if s["desc"] else "Oldest First")
        self.collapse.setVisible(timeline)
        self.collapse.setText("Collapse All")
        if overview:
            self._overview()
            return
        if found is not None:
            books, heading, groups = found, "", [("", sorted(found, key=lambda b: b["title"].lower()), None)]
        else:
            if s["sort"] == "Type" and s["tile"] is not None:
                books, heading = browse.books_of_type(self.books, s["tile"]), browse.PLURAL.get(s["tile"], s["tile"])
            elif s["sort"] == "Course" and s["tile"] is not None:
                books = browse.books_of_course(self.books, s["tile"])
                c = self.courses.get(s["tile"])
                heading = (c["code"] or crud.label(c)) if c else "No Course"
            else:
                books, heading, inner = self.books, "", s["sort"]
            if inner == "Date Added":
                groups = browse.timeline_groups(books, s["desc"], s["unit"])
            else:
                groups = browse._sorted_groups(books, inner)
        self.count.setText(f"{len(books)} {'Title' if len(books) == 1 else 'Titles'}" + (f"   ·   {heading}" if heading else ""))
        if not books:
            self.blay.addWidget(QLabel("No files here yet. Use Import > Add Files to add some."))
        for gi, (title, items, course_id) in enumerate(groups):
            body = self._files(items, f"{s['sort']}|{s['tile']}|{title}")
            if timeline:
                fold = Fold(title, len(items), body, open_=gi < 2)
                self.folds.append(fold)
                self.blay.addWidget(fold)
            else:
                if title:
                    h = QLabel(f"{title} ({len(items)})")
                    h.setObjectName("h2")
                    self.blay.addWidget(h)
                self.blay.addWidget(body)
        self.blay.addStretch(1)

    def _overview(self):
        s = self.s
        n = len(self.books)
        self.count.setText(f"{n} {'Title' if n == 1 else 'Titles'}")
        host = QWidget()
        flow = FlowLayout(host, 14, 14)
        if s["sort"] == "Type":
            for name, count in browse.type_tiles(self.books):
                t = Tile(browse.PLURAL.get(name, name), count)
                t.clicked.connect(lambda n=name: self._open_tile(n))
                flow.addWidget(t)
        else:
            for cid, label, color, count in browse.course_tiles(self.books, self.courses):
                c = self.courses.get(cid)
                t = Tile(c["code"] if c and c["code"] else label, count, color, c["name"] if c and c["code"] and c["name"] and c["name"] != c["code"] else "")
                t.clicked.connect(lambda cid=cid: self._open_tile(cid))
                flow.addWidget(t)
        self.blay.addWidget(host)
        self.blay.addStretch(1)

    def _files(self, items, key):
        """The files of one group in the chosen view, the first PAGE of them (the rest come with Show More)."""
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        limit = self.shown.get(key) or max(12, min(PAGE, self.budget))
        self.budget -= min(len(items), limit)
        part = items[:limit]
        view = self.s["view"]
        if view == "Details":
            lay.addWidget(self._table(part))
        else:
            grid = QWidget()
            flow = FlowLayout(grid, 14, 14)
            for b in part:
                card = BookCard(b, self.courses, self.cache, tile=view == "Tiles")
                card.open_requested.connect(self.open_book)
                card.edit_requested.connect(self.edit_book)
                card.remove_requested.connect(self.remove_one)
                flow.addWidget(card)
            lay.addWidget(grid)
        if len(items) > limit:
            more = QPushButton(f"Show {min(PAGE, len(items) - limit)} More ({len(items) - limit} Left)")
            more.setFixedWidth(240)
            more.clicked.connect(lambda: (self.shown.__setitem__(key, limit + PAGE), self.draw()))
            lay.addWidget(more)
        return host

    def _table(self, items):
        heads = ["Name", "Type", "Course", "Lecture", "Date Added", "Edition", "Author"]
        t = QTableWidget(len(items), len(heads))
        t.setHorizontalHeaderLabels(heads)
        t.verticalHeader().hide()
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        t.horizontalHeader().setStretchLastSection(True)
        t.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for i, w in enumerate((330, 150, 170, 80, 110, 120)):
            t.setColumnWidth(i, w)
        t.setStyleSheet("QTableWidget { gridline-color: transparent; background: transparent; border: none; } QHeaderView::section { background: transparent; border: none; padding: 6px; font-weight: 600; }")
        for r, b in enumerate(items):
            linked = ", ".join(crud.show_code(self.courses[i]["code"]) or self.courses[i]["name"] for i in b["course_ids"] if i in self.courses)
            lec = (f"{'HW' if b['kind'] in browse.HW_KINDS else 'Lec'} {b['lecture']}") if b.get("lecture") else ""
            cells = [b["title"], b["kind"], linked, lec, (b.get("added_at") or "")[:10], " · ".join(x for x in (b["edition"], b.get("year")) if x), b["author"] or ""]
            for c, text in enumerate(cells):
                it = QTableWidgetItem(text)
                it.setData(Qt.UserRole, b["id"])
                t.setItem(r, c, it)
            t.setRowHeight(r, 34)
        t.setFixedHeight(40 + 34 * len(items))
        t.cellClicked.connect(lambda r, c, t=t: self.open_book.emit(t.item(r, 0).data(Qt.UserRole)))
        t.setContextMenuPolicy(Qt.CustomContextMenu)
        t.customContextMenuRequested.connect(lambda pos, t=t: self._row_menu(t, pos))
        return t

    def _row_menu(self, t, pos):
        it = t.itemAt(pos)
        if it is None:
            return
        bid = it.data(Qt.UserRole)
        m = QMenu(t)
        m.addAction("Open", lambda: self.open_book.emit(bid))
        m.addAction("Edit Details…", lambda: self.edit_book(bid))
        m.addAction("Remove from Library…", lambda: self.remove_one(bid))
        m.exec(t.viewport().mapToGlobal(pos))

    # ---------------------------------------------------------------- actions
    def edit_book(self, book_id):
        book = crud.get_book(book_id)
        if book and EditBookDialog(book, self.window()).exec():
            self.refresh()

    def remove_one(self, book_id):
        book = crud.get_book(book_id)
        if not book:
            return
        ask = QMessageBox.question(self.window(), "Remove from Library", f"Remove “{book['title']}” from the Library? This also deletes the stored copy in the data folder. Your original file is not touched.")
        if ask == QMessageBox.Yes:
            from qtui.library_dialogs import remove_book
            remove_book(book)
            self.refresh()

    def _default_course(self):
        t = self.s["tile"]
        return t if self.s["sort"] == "Course" and isinstance(t, int) and t else None

    def _confirm(self, candidates, remember, heading):
        if not candidates:
            QMessageBox.information(self.window(), heading, "No files were found.")
            return
        dlg = ImportDialog(candidates, self.window(), heading)
        if not dlg.exec():
            return
        chosen = dlg.chosen()
        if not chosen:
            return
        kept = []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            added, replaced, problems = LI.import_all(chosen, remember, self._default_course(), kept)
        finally:
            QApplication.restoreOverrideCursor()
        text = f"Imported {added} file{'s' if added != 1 else ''}" + (f" and replaced {replaced}" if replaced else "") + (f", kept {len(kept)} as they were" if kept else "") + "."
        if problems:
            text += "\n\nNot imported:\n" + "\n".join(problems[:6])
        QMessageBox.information(self.window(), heading, text)
        self.refresh()

    def add_files(self):
        names, _ = QFileDialog.getOpenFileNames(self.window(), "Add Files", str(Path.home()), "PDF, HTML and ZIP files (*.pdf *.html *.htm *.zip)")
        if not names:
            return
        entries, candidates = [], []
        for n in names:
            p = Path(n)
            if p.suffix.lower() == ".zip":
                candidates += LI.zip_candidates(p.read_bytes(), self._default_course())
            else:
                st = p.stat()
                entries.append((p.name, p.name, st.st_size, st.st_mtime, (lambda p=p: p.read_bytes())))
        if entries:
            candidates += LI.classify(entries, {}, self._default_course())
        self._confirm(sorted(candidates, key=LI.priority), False, "Add Files")

    def update_from_folder(self):
        folder = QFileDialog.getExistingDirectory(self.window(), "Update From Folder", str(Path.home()))
        if folder:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                candidates = LI.folder_candidates(folder, self._default_course())
            finally:
                QApplication.restoreOverrideCursor()
            self._confirm(candidates, True, "Update From Folder")

    def remove_files(self):
        dlg = RemoveDialog(self.window())
        if dlg.exec() and dlg.removed:
            self.refresh()
