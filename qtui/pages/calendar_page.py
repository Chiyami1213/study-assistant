"""The Calendar (native): the week or the day as a time grid (classes, activities, events, exams, study sessions, free time, the time now), the month, the terms and Auto-Plan, and the Task List beside it.
Not native yet: dragging and resizing the blocks, the schedule editor and the planner's other windows (they open on the classic page)."""
import calendar
from datetime import date, datetime, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from core import crud, settings
from planner import gridview, service, session_store, store as planner_store, timeutil
from planner.models import AwakeTimes, PlannerError
from qtui.pages.tasklist_page import TaskListPage
from qtui.task_dialogs import TaskDialog
from qtui.widgets import Segmented
from views import plan_grid

WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MONTHS = list(calendar.month_name)
GUTTER, HEAD_H, PILL_H = 58, 50, 20


def _span_title(view, days):
    a, b = days[0], days[-1]
    if view == "Day":
        return f"{WEEKDAYS[(a.weekday() + 1) % 7]}, {MONTHS[a.month][:3]} {a.day}, {a.year}"
    return (f"{MONTHS[a.month][:3]} {a.day} – {b.day}" if a.month == b.month else f"{MONTHS[a.month][:3]} {a.day} – {MONTHS[b.month][:3]} {b.day}") + f", {b.year}"


class PlannerGrid(QWidget):
    """The time grid of the days shown, painted in one piece: a click on a block says which one (`clicked(item, day)`)."""
    clicked = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.palette_colors = {"bg": "#0e1117", "text": "#e6e6e6", "border": "#2a2c33", "accent": "#4c8dff", "card": "#1b1c20"}
        self.data = None
        self.days = []
        self.hits = []

    def set_data(self, days, today, data, colors):
        self.days, self.today, self.data, self.palette_colors = days, today, data, colors
        items, allday, off, lo, hi, now_min, free, hour_px = data
        rows = max([len(allday.get(d, [])) for d in days] + [0])
        self.allday_h = (rows * (PILL_H + 3) + 8) if rows else 6
        self.setMinimumHeight(HEAD_H + self.allday_h + (hi - lo) * hour_px + 10)
        self.update()

    def _col(self, i):
        w = (self.width() - GUTTER) / max(1, len(self.days))
        return GUTTER + i * w, w

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self.palette_colors
        p.fillRect(self.rect(), QColor(c["bg"]))
        self.hits = []
        if not self.data:
            p.end()
            return
        items, allday, off, lo, hi, now_min, free, hour_px = self.data
        text, border, accent = QColor(c["text"]), QColor(c["border"]), QColor(c["accent"])
        body_top = HEAD_H + self.allday_h
        font = QFont(self.font())
        small = QFont(font)
        small.setPixelSize(11)
        bold = QFont(font)
        bold.setBold(True)
        # headers and the all-day strip
        for i, d in enumerate(self.days):
            x, w = self._col(i)
            today = d == self.today
            p.setPen(accent if today else text)
            p.setFont(small)
            p.drawText(QRectF(x, 4, w, 16), Qt.AlignCenter, WEEKDAYS[(d.weekday() + 1) % 7])
            p.setFont(bold)
            if today:
                p.setBrush(accent)
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x + w / 2, 33), 14, 14)
                p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(x, 20, w, 26), Qt.AlignCenter, f"{d.day:02d}")
            y = HEAD_H + 4
            for row in allday.get(d, []):
                label, color = row[0], row[1]
                r = QRectF(x + 3, y, w - 6, PILL_H)
                p.setBrush(QColor(color))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(r, 5, 5)
                p.setPen(QColor("#ffffff"))
                p.setFont(small)
                p.drawText(r.adjusted(6, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, p.fontMetrics().elidedText(label, Qt.ElideRight, int(r.width() - 10)))
                y += PILL_H + 3
        p.setPen(QPen(border, 1))
        p.drawLine(0, body_top, self.width(), body_top)
        p.setFont(small)
        # the hours
        for h in range(lo, hi):
            y = body_top + (h - lo) * hour_px
            p.setPen(QPen(border, 1))
            p.drawLine(GUTTER, y, self.width(), y)
            p.setPen(text)
            p.drawText(QRectF(0, y - 2, GUTTER - 8, 16), Qt.AlignRight | Qt.AlignTop, f"{h:02d}:00")
        for i, d in enumerate(self.days):
            x, w = self._col(i)
            p.setPen(QPen(border, 1))
            p.drawLine(int(x), body_top, int(x), self.height())
            if d in off:
                p.fillRect(QRectF(x, body_top, w, self.height() - body_top), QColor(128, 128, 128, 26))
            for it in free.get(d, []):
                r = QRectF(x + 2, body_top + (it.start - lo * 60) * hour_px / 60, w - 4, (it.end - it.start) * hour_px / 60)
                p.fillRect(r, QColor(124, 106, 255, 28))
                p.setPen(QColor(124, 106, 255, 170))
                p.drawText(r.adjusted(6, 2, -4, 0), Qt.AlignTop | Qt.AlignLeft, it.title)
            for it, lane, count in plan_grid.lanes(items.get(d, [])):
                top = body_top + (it.start - lo * 60) * hour_px / 60
                height = max((it.end - it.start) * hour_px / 60 - 2, 18)
                bw = (w - 4) / count
                r = QRectF(x + 2 + lane * bw, top, bw - 2, height)
                self._block(p, it, r, small, bold)
                self.hits.append((r, it, d))
            if d == self.today and now_min is not None and lo * 60 <= now_min <= hi * 60:
                y = body_top + (now_min - lo * 60) * hour_px / 60
                p.setPen(QPen(QColor("#e0392b"), 2))
                p.drawLine(int(x), int(y), int(x + w), int(y))
        p.end()

    def _block(self, p, it, r, small, bold):
        color = QColor(it.color)
        if it.kind == "commute":
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(color, Qt.BDiagPattern))
            p.drawRoundedRect(r, 4, 4)
            return
        if it.kind == "session":
            fill = QColor(color)
            fill.setAlpha(46)
            p.setBrush(fill)
            pen = QPen(color, 1.5, Qt.DashLine)
            p.setPen(pen)
            p.drawRoundedRect(r, 6, 6)
            if it.progress > 0:
                used = QColor(color)
                used.setAlpha(120)
                p.fillRect(QRectF(r.x() + 1, r.bottom() - 4, (r.width() - 2) * min(1.0, it.progress), 3), used)
            if it.level:
                p.setBrush(QColor(plan_grid.LEVEL_COLORS.get(it.level, "#6b7280")))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(r.right() - 9, r.top() + 9), 4, 4)
            p.setPen(QColor(self.palette_colors["text"]))
        else:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, color)
            g.setColorAt(1, QColor(crud.darken(it.color)))
            p.setBrush(QBrush(g))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(r, 6, 6)
            p.setPen(QColor("#ffffff"))
        p.setFont(small)
        inner = r.adjusted(6, 3, -6, -2)
        p.drawText(inner, Qt.AlignTop | Qt.AlignLeft, f"{plan_grid.hhmm(it.start)} - {plan_grid.hhmm(it.end)}")
        if inner.height() > 28:
            p.setFont(bold)
            p.drawText(inner.adjusted(0, 14, 0, 0), Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap, it.title)
            if it.sub and inner.height() > 52 and it.kind != "commute":
                p.setFont(small)
                p.drawText(inner.adjusted(0, 32, 0, 0), Qt.AlignTop | Qt.AlignLeft, it.sub)

    def _hit(self, pos):
        for r, it, d in reversed(self.hits):
            if r.contains(pos):
                return it, d
        return None

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            hit = self._hit(e.position())
            if hit:
                self.clicked.emit(*hit)

    def mouseMoveEvent(self, e):
        hit = self._hit(e.position())
        self.setCursor(Qt.PointingHandCursor if hit and hit[0].kind != "commute" else Qt.ArrowCursor)
        if hit:
            it = hit[0]
            self.setToolTip(f"{it.title}\n{plan_grid.hhmm(it.start)} - {plan_grid.hhmm(it.end)}" + (f"\n{it.sub}" if it.sub else ""))
        else:
            self.setToolTip("")


class CalendarPage(QWidget):
    classic_requested = Signal(str)
    changed = Signal()

    def __init__(self, colors):
        super().__init__()
        self.setObjectName("page")
        self.colors = colors
        self.page = "Calendar"
        self.view = "Week"
        self.anchor = date.today()
        self.month = (self.anchor.year, self.anchor.month)
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 28, 40, 12)
        root.setSpacing(8)
        top = QHBoxLayout()
        title = QLabel("Calendar")
        title.setObjectName("h1")
        top.addWidget(title)
        self.pages = Segmented([("Calendar", "Calendar"), ("Task List", "Task List")], self.page)
        self.pages.changed.connect(self._set_page)
        top.addWidget(self.pages)
        top.addStretch(1)
        self.term = QComboBox()
        self.term.setMinimumWidth(180)
        self.term.currentIndexChanged.connect(self._term_changed)
        top.addWidget(self.term)
        root.addLayout(top)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        # the calendar
        cal = QWidget()
        cl = QVBoxLayout(cal)
        cl.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.viewseg = Segmented([(v, v) for v in ("Day", "Week", "Month")], self.view)
        self.viewseg.changed.connect(self._set_view)
        prev, nxt, today = QPushButton("‹"), QPushButton("›"), QPushButton("Today")
        prev.setFixedWidth(44)
        nxt.setFixedWidth(44)
        prev.clicked.connect(lambda: self._step(-1))
        nxt.clicked.connect(lambda: self._step(1))
        today.clicked.connect(self._today)
        self.span = QLabel()
        self.span.setStyleSheet("font-size: 17px; font-weight: 700;")
        add = QPushButton("+ Task")
        add.clicked.connect(lambda: self.add_task())
        plan = QPushButton("Auto-Plan")
        plan.setToolTip("places study time for the tasks that are not planned yet, in the free time before their deadlines")
        plan.clicked.connect(self.auto_plan)
        sched = QPushButton("Edit Schedule (Classic Page)")
        sched.clicked.connect(lambda: self.classic_requested.emit("schedule"))
        for w in (self.viewseg, prev, today, nxt, self.span):
            bar.addWidget(w)
        bar.addStretch(1)
        for w in (add, plan, sched):
            bar.addWidget(w)
        cl.addLayout(bar)
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet("background: rgba(224,57,43,0.16); border: 1px solid #e0392b; border-radius: 8px; padding: 8px 12px;")
        self.banner.hide()
        cl.addWidget(self.banner)
        self.cstack = QStackedWidget()
        cl.addWidget(self.cstack, 1)
        self.grid = PlannerGrid()
        self.grid.clicked.connect(self._item_clicked)
        self.gscroll = QScrollArea()
        self.gscroll.setWidgetResizable(True)
        self.gscroll.setFrameShape(QFrame.NoFrame)
        self.gscroll.setWidget(self.grid)
        self.cstack.addWidget(self.gscroll)
        self.mscroll = QScrollArea()
        self.mscroll.setWidgetResizable(True)
        self.mscroll.setFrameShape(QFrame.NoFrame)
        self.cstack.addWidget(self.mscroll)
        self.stack.addWidget(cal)
        self.tasks = TaskListPage()
        self.tasks.changed.connect(self._tasks_changed)
        self.stack.addWidget(self.tasks)
        self.reload_terms()
        self.refresh()

    # ---------------------------------------------------------------- terms, state
    def set_colors(self, colors):
        self.colors = colors
        self.refresh()

    def reload_terms(self):
        terms = settings.list_terms()
        active = settings.get_active_term()
        self.term.blockSignals(True)
        self.term.clear()
        for t in terms:
            self.term.addItem(t["name"], t["id"])
        self.term.addItem("Manage Terms… (Classic Page)", 0)
        if active:
            self.term.setCurrentIndex(max(0, self.term.findData(active["id"])))
        self.term.blockSignals(False)

    def _term_changed(self, *_):
        tid = self.term.currentData()
        if tid == 0:
            self.reload_terms()
            self.classic_requested.emit("terms")
            return
        if tid is None:
            return
        settings.set_active_term(tid)
        term = settings.get_active_term()
        if term.get("awake"):
            try:
                planner_store.set_awake(AwakeTimes.uniform(timeutil.parse_hhmm(term["awake"]["wake"]), timeutil.parse_hhmm(term["awake"]["bed"])))
            except (PlannerError, ValueError):
                pass
        first, last = date.fromisoformat(term["start"]), date.fromisoformat(term["exam_end"])
        self.anchor = date.today() if first <= date.today() <= last else first
        self.month = (self.anchor.year, self.anchor.month)
        self.refresh()

    def _set_page(self, key):
        self.page = key
        self.refresh()

    def _set_view(self, key):
        self.view = key
        self.refresh()

    def _step(self, n):
        if self.view == "Month":
            y, m = self.month
            m += n
            y += (m - 1) // 12
            self.month = (y, (m - 1) % 12 + 1)
        else:
            self.anchor += timedelta(days=n * (7 if self.view == "Week" else 1))
        self.refresh()

    def _today(self):
        self.anchor = date.today()
        self.month = (self.anchor.year, self.anchor.month)
        self.refresh()

    # ---------------------------------------------------------------- drawing
    def refresh(self):
        if self.page == "Task List":
            self.stack.setCurrentWidget(self.tasks)
            self.tasks.refresh()
            return
        self.stack.setCurrentIndex(0)
        today = date.today()
        try:
            report = service.cushion_report()
        except Exception:
            report = None
        self._banner(report)
        if self.view == "Month":
            self._month(today)
            return
        first = gridview._week_start(self.anchor)
        days = [first + timedelta(days=i) for i in range(7)] if self.view == "Week" else [self.anchor]
        self.span.setText(_span_title(self.view, days))
        data = gridview.grid_data(days, today, report or service.cushion_report(), True)
        self.grid.set_data(days, today, data, self.colors)
        self.cstack.setCurrentWidget(self.gscroll)

    def _banner(self, report):
        if not report or not report.any_negative or not settings.get_fit_warning():
            self.banner.hide()
            return
        from planner import task_store
        tasks = {t.id: t for t in task_store.list_tasks()}
        tz = planner_store.get_term().zone
        lines = []
        for c in report.negative_items[:4]:
            t = tasks.get(c.task_id)
            if t:
                lines.append(f"<b>{t.title}</b> ({self.tasks._fmt_due(t.due, tz)}): short by {plan_grid.fmt_minutes(-c.cushion_minutes)}")
        more = len(report.negative_items) - len(lines)
        self.banner.setText("Some tasks do not fit before their deadlines:<br>" + "<br>".join(lines) + (f"<br>…and {more} more" if more > 0 else ""))
        self.banner.show()

    def _month(self, today):
        year, month = self.month
        self.span.setText(f"{MONTHS[month]} {year}")
        items = gridview._items_by_day(year, month)
        host = QWidget()
        host.setObjectName("page")
        g = QGridLayout(host)
        g.setSpacing(6)
        for i, name in enumerate(WEEKDAYS):
            lab = QLabel(name)
            lab.setAlignment(Qt.AlignCenter)
            lab.setObjectName("muted")
            g.addWidget(lab, 0, i)
        for r, week in enumerate(calendar.Calendar(firstweekday=6).monthdatescalendar(year, month), 1):
            for i, day in enumerate(week):
                cell = QFrame()
                cell.setObjectName("card")
                cell.setMinimumHeight(112)
                cell.setStyleSheet("QFrame#card { border: 2px solid #4c8dff; border-radius: 8px; }" if day == today and day.month == month else "")
                lay = QVBoxLayout(cell)
                lay.setContentsMargins(6, 4, 6, 4)
                lay.setSpacing(2)
                if day.month != month:
                    cell.setObjectName("")
                    cell.setStyleSheet("background: transparent;")
                    g.addWidget(cell, r, i)
                    continue
                num = QLabel(str(day.day))
                num.setStyleSheet("font-weight: 700; background: transparent;")
                lay.addWidget(num)
                rows = items.get(day.isoformat(), [])
                for label, color in rows[:3]:
                    chip = QLabel(label)
                    chip.setStyleSheet(f"background: {color}; color: #ffffff; border-radius: 4px; padding: 1px 6px; font-size: 11px;")
                    chip.setToolTip(label)
                    lay.addWidget(chip)
                if len(rows) > 3:
                    more = QLabel(f"+{len(rows) - 3} more")
                    more.setObjectName("muted")
                    lay.addWidget(more)
                lay.addStretch(1)
                g.addWidget(cell, r, i)
        self.mscroll.setWidget(host)
        self.cstack.setCurrentWidget(self.mscroll)

    # ---------------------------------------------------------------- actions
    def _item_clicked(self, item, day):
        if item.kind == "commute":
            return
        box = QMessageBox(self.window())
        box.setWindowTitle(item.title)
        box.setText(f"<b>{item.title}</b><br>{day:%A, %B} {day.day} · {plan_grid.hhmm(item.start)} - {plan_grid.hhmm(item.end)}" + (f"<br>{item.sub}" if item.sub else ""))
        delete = None
        if item.kind == "session" and item.ref.startswith("session:"):
            delete = box.addButton("Delete Session", QMessageBox.DestructiveRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec()
        if delete is not None and box.clickedButton() is delete:
            try:
                service.delete_session(int(item.ref.split(":")[1]))
            except PlannerError as e:
                QMessageBox.warning(self.window(), "Session", str(e))
            self.refresh()
            self.changed.emit()

    def add_task(self):
        if TaskDialog(None, None, False, self.window()).exec():
            self.refresh()
            self.changed.emit()

    def auto_plan(self):
        result, report = service.auto_plan()
        placed, left = len(result.add), len(result.unplaced)
        text = (f"Planned {placed} study session{'s' if placed != 1 else ''}." if placed else "Nothing to plan: every task is already covered, or has no due date.") + \
               (f" {left} task{'s' if left != 1 else ''} do not fully fit." if left else "")
        QMessageBox.information(self.window(), "Auto-Plan", text)
        self.refresh()
        self.changed.emit()

    def _tasks_changed(self):
        self.changed.emit()
