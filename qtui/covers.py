"""Covers of the Library: the first page of a PDF (the app's own `library.covers`, made in the background), or a colored card with the title for a file that has no page to show."""
import hashlib

from PySide6.QtCore import QObject, QRect, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap

from core.database import data_path
from library import covers


def placeholder(title, w, h):
    """A colored card with the title, the color taken from the title (the same one each time)."""
    hue = int(hashlib.md5(title.encode()).hexdigest()[:6], 16) % 360
    pm = QPixmap(w, h)
    p = QPainter(pm)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor.fromHsl(hue, 120, 95))
    g.setColorAt(1, QColor.fromHsl((hue + 40) % 360, 130, 60))
    p.fillRect(0, 0, w, h, g)
    p.setPen(QColor("#ffffff"))
    font = QFont()
    font.setPixelSize(max(11, w // 11))
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRect(8, 8, w - 16, h - 16), Qt.AlignCenter | Qt.TextWordWrap, title)
    p.end()
    return pm


class _Job(QRunnable):
    def __init__(self, cache, book_id, path):
        super().__init__()
        self.cache, self.book_id, self.path = cache, book_id, path

    def run(self):
        try:
            img = covers.ensure_cover(self.book_id, self.path)
        except Exception:
            img = None
        self.cache.done.emit(self.book_id, str(img) if img else "")


class CoverCache(QObject):
    """`get(book, w, h)` gives a pixmap at once (the cover when it exists, else the colored card) and `ready(book id)` is emitted when a cover was made in the background."""
    done = Signal(int, str)
    ready = Signal(int)

    def __init__(self):
        super().__init__()
        self.pixmaps, self.asked = {}, set()
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(2)
        self.done.connect(self._done)

    def _done(self, book_id, path):
        if path:
            pm = QPixmap(path)
            if not pm.isNull():
                self.pixmaps[book_id] = pm
                self.ready.emit(book_id)

    def get(self, book, w, h):
        bid = book["id"]
        pm = self.pixmaps.get(bid)
        if pm is None and book["pdf_path"].lower().endswith(".pdf"):
            img = covers.cover_path(bid)
            if img.exists():
                pm = QPixmap(str(img))
                if not pm.isNull():
                    self.pixmaps[bid] = pm
            elif bid not in self.asked:
                self.asked.add(bid)
                self.pool.start(_Job(self, bid, data_path(book["pdf_path"])))
        if pm is None or pm.isNull():
            return placeholder(book["title"], w, h)
        return pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
