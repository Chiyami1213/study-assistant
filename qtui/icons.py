"""The menu icons, drawn with QPainter (no icon font or image files, so they look the same on Windows and on a Mac and take the color they are given)."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def _pen(color, w=1.8):
    pen = QPen(QColor(color), w)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _home(p):
    p.drawPolyline(QPolygonF([QPointF(3, 12), QPointF(12, 4), QPointF(21, 12)]))
    p.drawPolyline(QPolygonF([QPointF(5.5, 10.5), QPointF(5.5, 20), QPointF(18.5, 20), QPointF(18.5, 10.5)]))
    p.drawRect(QRectF(10, 13.5, 4, 6.5))


def _calendar(p):
    p.drawRoundedRect(QRectF(3.5, 5, 17, 15.5), 2.5, 2.5)
    p.drawLine(QPointF(3.5, 10), QPointF(20.5, 10))
    p.drawLine(QPointF(8, 3), QPointF(8, 6.5))
    p.drawLine(QPointF(16, 3), QPointF(16, 6.5))
    for x in (8, 12, 16):
        p.drawPoint(QPointF(x, 14))
        p.drawPoint(QPointF(x, 17.2))


def _library(p):
    p.drawRoundedRect(QRectF(3.5, 4, 5, 16), 1, 1)
    p.drawRoundedRect(QRectF(9.5, 4, 5, 16), 1, 1)
    p.drawLine(QPointF(16, 6), QPointF(20.2, 5)); p.drawLine(QPointF(20.2, 5), QPointF(21.5, 17.5)); p.drawLine(QPointF(21.5, 17.5), QPointF(17.3, 19))
    p.drawLine(QPointF(16, 6), QPointF(17.3, 19))


def _reader(p):
    path = QPainterPath()
    path.moveTo(12, 6.5); path.cubicTo(9, 4.5, 5.5, 4.5, 3, 5.5); path.lineTo(3, 18.5); path.cubicTo(5.5, 17.5, 9, 17.5, 12, 19.5)
    path.cubicTo(15, 17.5, 18.5, 17.5, 21, 18.5); path.lineTo(21, 5.5); path.cubicTo(18.5, 4.5, 15, 4.5, 12, 6.5)
    p.drawPath(path)
    p.drawLine(QPointF(12, 6.5), QPointF(12, 19.5))


def _courses(p):                       # a graduation cap
    p.drawPolygon(QPolygonF([QPointF(12, 5), QPointF(22, 10), QPointF(12, 15), QPointF(2, 10)]))
    p.drawPolyline(QPolygonF([QPointF(6, 12.5), QPointF(6, 17), QPointF(12, 19.5), QPointF(18, 17), QPointF(18, 12.5)]))
    p.drawLine(QPointF(22, 10), QPointF(22, 16))


def _settings(p):                      # a gear
    p.drawEllipse(QPointF(12, 12), 3.2, 3.2)
    p.drawEllipse(QPointF(12, 12), 7, 7)
    import math
    for k in range(8):
        a = k * math.pi / 4
        p.drawLine(QPointF(12 + 7 * math.cos(a), 12 + 7 * math.sin(a)), QPointF(12 + 9.6 * math.cos(a), 12 + 9.6 * math.sin(a)))


def _rest(p):                          # a person sitting in rest
    p.drawEllipse(QPointF(12, 6), 2.2, 2.2)
    p.drawPolyline(QPolygonF([QPointF(12, 9), QPointF(12, 14)]))
    p.drawPolyline(QPolygonF([QPointF(6, 11), QPointF(12, 10), QPointF(18, 11)]))
    path = QPainterPath()
    path.moveTo(4, 19); path.cubicTo(8, 14, 16, 14, 20, 19); path.lineTo(4, 19)
    p.drawPath(path)


def _quiz(p):                          # a question mark in a circle
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    path = QPainterPath()
    path.moveTo(9.3, 9.6); path.cubicTo(9.5, 6.8, 14.8, 6.8, 14.8, 9.8); path.cubicTo(14.8, 11.8, 12, 11.6, 12, 14)
    p.drawPath(path)
    p.drawPoint(QPointF(12, 16.8))


def _course(p):                        # a book
    p.drawRoundedRect(QRectF(5, 3.5, 14, 17), 2, 2)
    p.drawLine(QPointF(8.5, 3.5), QPointF(8.5, 20.5))
    p.drawLine(QPointF(11.5, 8), QPointF(16, 8))


DRAWERS = {"Home": _home, "Calendar": _calendar, "Library": _library, "Note Reader": _reader, "Courses": _courses, "Settings": _settings, "Rest Now": _rest, "Quiz": _quiz, "course": _course}


def icon(name, color="#d5d7dd", size=24):
    """The icon `name` as a QIcon of `size` pixels (drawn at twice that for sharp edges on a high-density screen)."""
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size * scale / 24, size * scale / 24)
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)
    DRAWERS.get(name, _course)(p)
    p.end()
    pm.setDevicePixelRatio(scale)
    return QIcon(pm)
