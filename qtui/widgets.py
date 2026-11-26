"""Small widgets the pages share: a switch, a segmented choice, a theme card."""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class Switch(QCheckBox):
    """An on / off switch with its label at the right."""

    def __init__(self, text="", checked=False, colors=None):
        super().__init__(text)
        self.setChecked(checked)
        self.colors = colors or {}
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        h = super().sizeHint()
        h.setWidth(h.width() + 36)
        h.setHeight(max(h.height(), 28))
        return h

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        track = QColor(self.colors.get("primary", "#ff4b4b")) if on else QColor(self.colors.get("border", "#888888"))
        if not self.isEnabled():
            track.setAlpha(90)
        y = (self.height() - 18) / 2
        p.setPen(Qt.NoPen); p.setBrush(track)
        p.drawRoundedRect(QRectF(0, y, 34, 18), 9, 9)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(17 if on else 2, y + 2, 14, 14))
        p.setPen(QColor(self.colors.get("text", "#dddddd")))
        p.drawText(QRectF(44, 0, self.width() - 44, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()


class Segmented(QWidget):
    """A row of buttons of which one is chosen: `changed(key)`."""
    changed = Signal(str)

    def __init__(self, options, current):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for key, label in options:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(key == current)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
            self.group.addButton(b)
            lay.addWidget(b)
        lay.addStretch(1)


class ThemeCard(QFrame):
    """A color theme: its four surface colors and its name; a click chooses it."""
    clicked = Signal(str)

    def __init__(self, key, name, swatches, chosen):
        super().__init__()
        self.key = key
        self.setObjectName("card")
        self.setProperty("chosen", chosen)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(150, 92)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        row = QHBoxLayout()
        row.setSpacing(4)
        for color in swatches:
            tile = QFrame()
            tile.setFixedHeight(34)
            tile.setStyleSheet(f"background: {color}; border-radius: 6px; border: 1px solid rgba(128,128,128,0.35);")
            row.addWidget(tile)
        lay.addLayout(row)
        label = QLabel(name)
        label.setStyleSheet("font-weight: 600; background: transparent;")
        lay.addWidget(label)

    def mousePressEvent(self, e):
        self.clicked.emit(self.key)
