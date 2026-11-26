"""The 20-20-20 eye rest of the native interface: after every 20 minutes of studying a short look away from the screen is offered; skipping is allowed a few times in a row, then a required rest starts.
`EyeRest` is PURE (no Qt, the clock is a parameter) so it can be tested; `RestOverlay` and `EyeRestController` are the Qt part."""
import time

INTERVAL = 20 * 60          # seconds of studying between two reminders


class EyeRest:
    """The state of the reminder. `tick()` says what to do now: None, 'ask' (offer a rest), 'force' (a required rest starts)."""

    def __init__(self, cfg, clock=time.time, interval=INTERVAL):
        self.cfg, self.clock, self.interval = cfg, clock, interval
        self.next = clock() + interval
        self.refused = 0
        self.force_end = 0.0
        self.busy = False                 # a card (ask, rest, warn) or the required rest is on screen

    def tick(self):
        now = self.clock()
        if self.busy:
            return None
        if self.force_end > now:
            self.busy = True
            return "force"
        if now >= self.next:
            self.next = now + self.interval
            self.busy = True
            if self.refused >= self.cfg["max_skips"]:
                self.force_end = now + self.cfg["required_minutes"] * 60
                return "force"
            return "ask"
        return None

    def start_rest(self):
        """The student took the rest the reminder offered."""
        self.refused = 0

    def refuse(self):
        """Not Now (or Skip in the middle of a rest). True when this is the skip after which a warning is shown."""
        self.refused += 1
        self.busy = False
        return self.cfg["max_skips"] > 0 and self.refused == self.cfg["max_skips"]

    def finished(self):
        """A rest ended (or its card was closed): the 20 minutes start again."""
        self.next = self.clock() + self.interval
        self.refused = 0
        self.busy = False

    def rest_now(self):
        """The student chose to rest now: it counts as the eye rest, so the 20 minutes start again. False when a required rest is running (that cannot be replaced)."""
        if self.force_end > self.clock():
            return False
        self.next = self.clock() + self.interval
        self.refused = 0
        self.force_end = 0.0
        self.busy = True
        return True

    def forced_left(self):
        return max(0, int(self.force_end - self.clock() + 0.999))

    def end_force(self):
        self.force_end = 0.0
        self.finished()

    def close_card(self):
        self.busy = False


# ---------------------------------------------------------------- the Qt part
from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget


class RestOverlay(QFrame):
    """The card on top of the window: an offer (Start Rest / Not Now), a countdown, a warning, or the required rest (the rest of the window dimmed)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("restdim")
        self.card = QFrame(self)
        self.card.setObjectName("restcard")
        self.card.setFixedWidth(440)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(22, 18, 22, 18)
        self.title = QLabel(); self.title.setAlignment(Qt.AlignCenter); self.title.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.text = QLabel(); self.text.setWordWrap(True); self.text.setAlignment(Qt.AlignCenter)
        self.count = QLabel(); self.count.setAlignment(Qt.AlignCenter); self.count.setStyleSheet("font-size: 40px; font-weight: 700;")
        self.bar = QProgressBar(); self.bar.setTextVisible(False); self.bar.setFixedHeight(6); self.bar.setRange(0, 100)
        row = QHBoxLayout()
        self.go = QPushButton(); self.no = QPushButton()
        row.addStretch(1); row.addWidget(self.go); row.addWidget(self.no); row.addStretch(1)
        for w in (self.title, self.text, self.count, self.bar):
            lay.addWidget(w)
        lay.addLayout(row)
        self.hide()

    def show_card(self, dim):
        self.setStyleSheet("QFrame#restdim { background: rgba(0, 0, 0, 175); }" if dim else "QFrame#restdim { background: transparent; }")
        self.card.setStyleSheet("QFrame#restcard { background: palette(base); border: 1px solid #4c8dff; border-radius: 12px; }")
        self.reposition(dim)
        self.show(); self.raise_()

    def reposition(self, dim=None):
        p = self.parentWidget()
        if p is None:
            return
        dim = self.property("dim") if dim is None else dim
        self.setProperty("dim", dim)
        if dim:
            self.setGeometry(0, 0, p.width(), p.height())
            self.card.adjustSize(); self.card.move((self.width() - self.card.width()) // 2, (self.height() - self.card.height()) // 2)
        else:
            self.card.adjustSize()
            self.setGeometry((p.width() - self.card.width()) // 2, 22, self.card.width(), self.card.height())
            self.card.move(0, 0)


class EyeRestController(QObject):
    """Drives `EyeRest` with a one-second timer and shows its cards. `settings_fn()` returns the eye rest settings (they may change while the app runs)."""

    def __init__(self, window, settings_fn):
        super().__init__(window)
        self.window, self.settings_fn = window, settings_fn
        self.logic = EyeRest(settings_fn())
        self.overlay = RestOverlay(window)
        self.end = 0.0
        self.mode = None
        self.overlay.go.clicked.connect(self._go_clicked)
        self.overlay.no.clicked.connect(self._no_clicked)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)

    def _beep(self):
        if self.logic.cfg.get("sound"):
            QApplication.beep()

    # -- the cards --
    def _card(self, title, text, go=None, no=None, dim=False, count=False, bar=False):
        o = self.overlay
        o.title.setText(title); o.text.setText(text)
        o.count.setVisible(count); o.bar.setVisible(bar)
        for btn, label in ((o.go, go), (o.no, no)):
            btn.setVisible(bool(label)); btn.setText(label or "")
        o.go.setEnabled(True)
        o.show_card(dim)

    def _go_clicked(self):
        {"ask": self.start_rest, "warn": self._close_warn, "force": self._resume}.get(self.mode, lambda: None)()

    def _no_clicked(self):
        if self.mode in ("ask", "rest", "done"):
            self.refuse()

    def ask(self):
        cfg = self.logic.cfg
        self.mode = "ask"
        self._card("Eye Rest", f"You have been studying for 20 minutes. Look at something 20 feet (6 meters) away for {cfg['rest_seconds']} seconds?", "Start Rest", "Not Now")
        self._beep()

    def start_rest(self):
        self.logic.start_rest()
        self.mode = "rest"
        total = self.logic.cfg["rest_seconds"]
        self.end = self.logic.clock() + total
        self._card("Eye Rest", "Look at something 20 feet (6 meters) away.", None, "Skip", count=True, bar=True)
        self._update_rest()

    def refuse(self):
        self.overlay.hide()
        if self.mode == "done":
            self.logic.finished()
        elif self.logic.refuse():
            cfg = self.logic.cfg
            self.mode = "warn"
            self.logic.busy = True
            self._card("Rest Warning", f"You have skipped {cfg['max_skips']} eye rest{'' if cfg['max_skips'] == 1 else 's'} in a row. If you keep studying without a break, "
                                       f"a required {cfg['required_minutes']}-minute rest starts at the next reminder.", "Understood")
            QTimer.singleShot(15000, lambda: self._close_warn() if self.mode == "warn" else None)
        self.mode = None if self.mode != "warn" else "warn"

    def _close_warn(self):
        if self.mode == "warn":
            self.mode = None
            self.overlay.hide()
            self.logic.close_card()

    def rest_now(self):
        """The Rest Now button: a rest the student takes on their own (the reminder starts again)."""
        self.logic.cfg = self.settings_fn()
        if not self.logic.rest_now():
            return
        self._beep()
        self.start_rest()

    def force(self):
        self.mode = "force"
        left = self.logic.forced_left()
        cfg = self.logic.cfg
        self._card("Required Rest", f"You have used the app for {int((cfg['max_skips'] + 1) * self.logic.interval / 60)} minutes without taking an eye rest. "
                                    f"Step away from the screen and rest your eyes for {cfg['required_minutes']} minutes.", "Resume Studying", None, dim=True, count=True, bar=True)
        self.overlay.go.setEnabled(False)
        self._beep()
        self._update_force()

    def _resume(self):
        self.overlay.hide(); self.mode = None
        self.logic.end_force()

    # -- the clock --
    def _update_rest(self):
        total = self.logic.cfg["rest_seconds"]
        left = max(0, int(self.end - self.logic.clock() + 0.999))
        self.overlay.count.setText(str(left))
        self.overlay.bar.setValue(int((total - left) / total * 100))
        if left == 0 and self.mode == "rest":
            self.mode = "done"
            self.logic.finished()
            self._beep()
            self.overlay.text.setText("Nice work. Your eyes are rested.")
            self.overlay.count.setText("Done"); self.overlay.bar.setValue(100)
            self.overlay.no.setText("Back to Studying")
            QTimer.singleShot(15000, lambda: (self.overlay.hide(), setattr(self, "mode", None)) if self.mode == "done" else None)

    def _update_force(self):
        total = self.logic.cfg["required_minutes"] * 60
        left = self.logic.forced_left()
        self.overlay.count.setText(f"{left // 60}:{left % 60:02d}" if left else "Done")
        self.overlay.bar.setValue(int((total - left) / total * 100))
        if not left and not self.overlay.go.isEnabled():
            self.overlay.go.setEnabled(True)
            self.overlay.text.setText("Nice work. Your eyes are rested.")
            self._beep()

    def tick(self):
        self.logic.cfg = self.settings_fn()
        if self.mode == "rest":
            self._update_rest()
        elif self.mode == "force":
            self._update_force()
        elif self.mode is None:
            event = self.logic.tick()
            if event == "ask":
                self.ask()
            elif event == "force":
                self.force()
        if self.overlay.isVisible():
            self.overlay.reposition()
