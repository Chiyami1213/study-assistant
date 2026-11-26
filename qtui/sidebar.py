"""The menu on the left: a rail of icons that opens to the full menu when the mouse is over it. Courses has its list below it (Active, Self-Study, Completed) beside thin grey lines."""
from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget

from core import crud, settings
from qtui import icons
from qtui.theme import MENU_W, RAIL_W, SIDEBAR

TOP = ["Home", "Calendar", "Library", "Note Reader", "Quiz", "Courses"]
SECTIONS = ["Active", "Self-Study", "Completed"]


def _repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)


class CourseList(QWidget):
    """The courses under Courses: a line down from the icon of the group, and a shorter line beside the courses of each section."""

    def __init__(self, on_section, on_course):
        super().__init__()
        self._on_section, self._on_course = on_section, on_course
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)
        self.spans = []                                   # (first row, last row) of each section, for its line
        self.course_buttons = {}

    def fill(self, current_course, page):
        while self.lay.count():
            item = self.lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.spans, self.course_buttons = [], {}
        collapsed = set(settings.get_collapsed())
        for status in SECTIONS:
            items = crud.courses_by_status(status)
            if not items:
                continue
            head = QPushButton(status)
            head.setObjectName("navsec")
            head.setCursor(Qt.PointingHandCursor)
            head.setToolTip("click to fold or unfold this list")
            head.clicked.connect(lambda _=False, s=status: self._on_section(s))
            row = QWidget()
            row.setFixedHeight(32)
            h = QHBoxLayout(row); h.setContentsMargins(47, 0, 8, 0); h.addWidget(head)
            self.lay.addWidget(row)
            if status in collapsed:
                continue
            rows = []
            for c in items:
                b = QPushButton("  " + (crud.show_code(c["code"]) or c["name"]))
                b.setObjectName("navsub")
                b.setIcon(icons.icon("course", SIDEBAR["text"], 22))
                b.setCursor(Qt.PointingHandCursor)
                b.setProperty("current", page == "Courses" and current_course == c["id"])
                b.setStyleSheet("padding-left: 14px;")
                b.clicked.connect(lambda _=False, cid=c["id"]: self._on_course(cid))
                r = QWidget()
                r.setFixedHeight(40)
                b.setMinimumHeight(36)
                hh = QHBoxLayout(r); hh.setContentsMargins(60, 0, 8, 0); hh.addWidget(b)
                self.lay.addWidget(r)
                rows.append(r)
                self.course_buttons[c["id"]] = b
            if rows:
                self.spans.append((rows[0], rows[-1]))
        self.updateGeometry()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setPen(QColor(SIDEBAR["line"]))
        p.drawLine(26, 2, 26, self.height() - 2)           # from the middle of the icon of Courses
        for first, last in self.spans:
            p.drawLine(51, first.geometry().top(), 51, last.geometry().bottom())
        p.end()


class Sidebar(QFrame):
    navigate = Signal(str)
    course_chosen = Signal(int)
    rest_now = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(RAIL_W)
        self._width = RAIL_W
        self._anim = QPropertyAnimation(self, b"railWidth", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.page, self.course = "Home", None
        self.inner = QWidget(self)
        outer = QVBoxLayout(self.inner)
        outer.setContentsMargins(10, 18, 10, 14)
        outer.setSpacing(4)
        self.buttons = {}
        scroll = QScrollArea()                       # the top of the menu scrolls when there are many courses; Rest Now and Settings stay at the bottom
        scroll.setObjectName("navscroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)       # the mouse wheel still scrolls
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        for name in TOP:
            lay.addWidget(self._nav(name, lambda _=False, n=name: self._go(n)))
            if name == "Courses":
                self.courses = CourseList(self._fold, self._choose)
                self.courses.hide()
                lay.addWidget(self.courses)
        lay.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        lay = outer
        lay.addWidget(self._nav("Rest Now", lambda _=False: self.rest_now.emit(), tip="start an eye rest now: it counts as your eye rest and the 20-minute reminder starts again"))
        lay.addWidget(self._nav("Settings", lambda _=False: self._go("Settings")))
        self.set_current("Home", None)

    # ---- the width of the rail (grows while the mouse is over the menu) ----
    def _get_w(self):
        return self._width

    def _set_w(self, w):
        self._width = int(w)
        self.setFixedWidth(self._width)

    railWidth = Property(int, _get_w, _set_w)

    def _slide(self, w):
        self._anim.stop()
        self._anim.setStartValue(self._width)
        self._anim.setEndValue(w)
        self._anim.start()

    def enterEvent(self, e):
        self._slide(MENU_W)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._slide(RAIL_W)
        super().leaveEvent(e)

    def resizeEvent(self, e):
        self.inner.setGeometry(0, 0, MENU_W, self.height())
        super().resizeEvent(e)

    # ---- items ----
    def _nav(self, name, slot, tip=None):
        b = QPushButton("   " + name)
        b.setObjectName("nav")
        b.setIcon(icons.icon(name, SIDEBAR["text"], 24))
        b.setIconSize(QSize(24, 24))
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet("padding-left: 16px;")
        if tip:
            b.setToolTip(tip)
        b.clicked.connect(slot)
        self.buttons[name] = b
        return b

    def _go(self, name):
        self.navigate.emit(name)

    def _fold(self, status):
        collapsed = set(settings.get_collapsed())
        collapsed.symmetric_difference_update({status})
        settings.set_collapsed(collapsed)
        self.courses.fill(self.course, self.page)

    def _choose(self, cid):
        self.course_chosen.emit(cid)

    def refresh_courses(self):
        self.courses.fill(self.course, self.page)

    def set_current(self, page, course_id):
        self.page, self.course = page, course_id
        for name, b in self.buttons.items():
            b.setProperty("current", name == page)
            _repolish(b)
        self.courses.setVisible(page == "Courses")
        if page == "Courses":
            self.courses.fill(course_id, page)
