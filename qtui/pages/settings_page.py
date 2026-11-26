"""Settings (native): Appearance, Eye Rest and Quizzes. The other sections (Study Planner, Backup, Keyboard Shortcuts ...) are still on the classic page, reached with the button at the bottom."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget

from core import settings
from qtui.widgets import Segmented, Switch, ThemeCard

APPEARANCE = [("light", "Light"), ("dark", "Dark"), ("device", "Device")]


class SettingsPage(QScrollArea):
    appearance_changed = Signal()
    classic_requested = Signal()

    def __init__(self, colors):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.colors = colors
        self.body = QWidget()
        self.body.setObjectName("page")
        self.setWidget(self.body)
        self.build()

    def refresh(self, colors):
        """Drawn again (the colors changed)."""
        self.colors = colors
        self.build()

    # ---- building ----
    def _label(self, text, name="caption"):
        lab = QLabel(text)
        lab.setObjectName(name)
        lab.setWordWrap(True)
        return lab

    def _spin(self, low, high, value, on_change, enabled=True, suffix=""):
        s = QSpinBox()
        s.setRange(low, high)
        s.setValue(value)
        s.setSuffix(suffix)
        s.setEnabled(enabled)
        s.setFixedWidth(130)
        s.valueChanged.connect(on_change)
        return s

    def _field(self, caption, widget, tip=""):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 18, 0)
        lay.setSpacing(4)
        lab = QLabel(caption)
        lab.setToolTip(tip)
        widget.setToolTip(tip)
        lay.addWidget(lab)
        lay.addWidget(widget)
        return box

    def build(self):
        old = self.body.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    self._remove(item.widget())
                elif item.layout():
                    self._drop(item.layout())
            QWidget().setLayout(old)
        root = QVBoxLayout(self.body)
        root.setContentsMargins(40, 28, 40, 40)
        root.setSpacing(8)
        title = QLabel("Settings"); title.setObjectName("h1")
        root.addWidget(title)

        # Appearance
        root.addWidget(self._label("Appearance", "h2"))
        seg = Segmented(APPEARANCE, settings.get_appearance())
        seg.changed.connect(self._set_appearance)
        root.addWidget(seg)
        root.addWidget(self._label("Color Theme", "muted"))
        cards = QHBoxLayout()
        cards.setSpacing(12)
        mode = self.colors.get("mode", "dark")
        current = settings.get_color_theme()
        for key, (name, *_rest) in settings.COLOR_THEMES.items():
            c = settings.theme_colors(key, mode)
            card = ThemeCard(key, name, [c["bg"], c["card"], c["accent"], c["primary"]], key == current)
            card.clicked.connect(self._set_theme)
            cards.addWidget(card)
        cards.addStretch(1)
        root.addLayout(cards)
        root.addWidget(self._label("Graphite is the original look. The theme changes the colors of the surfaces and of the buttons you press; Light, Dark or the device's setting stay as chosen above."))

        # Eye Rest
        root.addWidget(self._label("Eye Rest", "h2"))
        root.addWidget(self._label("A reminder to look away from the screen after every 20 minutes of studying."))
        eye = settings.get_eye_rest()
        row = QHBoxLayout()
        row.addWidget(self._field("Rest Length (Seconds)", self._spin(5, 300, eye["rest_seconds"], lambda v: settings.set_eye_rest(rest_seconds=v)), "how long each eye rest lasts"))
        row.addWidget(self._field("Skips Allowed in a Row", self._spin(0, 10, eye["max_skips"], lambda v: settings.set_eye_rest(max_skips=v)),
                                  "after this many skipped rests in a row, the next reminder becomes a required rest"))
        row.addWidget(self._field("Required Rest (Minutes)", self._spin(1, 60, eye["required_minutes"], lambda v: settings.set_eye_rest(required_minutes=v)),
                                  "how long the required rest lasts; it cannot be skipped"))
        sound = Switch("Sound", eye["sound"], self.colors)
        sound.setToolTip("a short beep when a rest starts and ends")
        sound.toggled.connect(lambda v: settings.set_eye_rest(sound=bool(v)))
        row.addWidget(sound, 0, Qt.AlignBottom)
        row.addStretch(1)
        root.addLayout(row)

        # Quizzes
        root.addWidget(self._label("Quizzes", "h2"))
        root.addWidget(self._label("A speed round gives you a number of seconds for each question, so a round of 8 questions at 5 seconds has 40 seconds. This replaces the time limit written in the study guide."))
        quiz = settings.get_quiz()
        row = QHBoxLayout()
        spin = self._spin(1, 120, quiz["speed_seconds"], lambda v: settings.set_quiz(speed_seconds=v), enabled=not quiz["use_guide_time"])
        row.addWidget(self._field("Seconds per Question", spin, "the time of a speed round is this many seconds for each of its questions"))
        guide = Switch("Use the Guide's Own Time Limit", quiz["use_guide_time"], self.colors)
        guide.setToolTip("uses the total time written in each study guide instead of the seconds per question")
        guide.toggled.connect(lambda v: (settings.set_quiz(use_guide_time=bool(v)), spin.setEnabled(not v)))
        row.addWidget(guide, 0, Qt.AlignBottom)
        row.addStretch(1)
        root.addLayout(row)

        # the rest
        root.addWidget(self._label("More Settings", "h2"))
        root.addWidget(self._label("Study Planner, Backup, Keyboard Shortcuts, Help, Report an Issue, Danger Zone and About are still on the classic page."))
        more = QPushButton("Open Classic Settings")
        more.setCursor(Qt.PointingHandCursor)
        more.clicked.connect(self.classic_requested.emit)
        more.setFixedWidth(210)
        root.addWidget(more)
        root.addStretch(1)

    @staticmethod
    def _remove(widget):
        widget.hide()                      # gone from the screen at once, deleted when the event loop is free
        widget.setParent(None)
        widget.deleteLater()

    def _drop(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                self._remove(item.widget())
            elif item.layout():
                self._drop(item.layout())

    # ---- changes ----
    def _set_appearance(self, key):
        settings.set_appearance(key)
        self.appearance_changed.emit()

    def _set_theme(self, key):
        settings.set_color_theme(key)
        self.appearance_changed.emit()
