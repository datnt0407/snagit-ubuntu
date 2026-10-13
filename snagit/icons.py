"""Biểu tượng vẽ bằng code (không phụ thuộc theme hệ thống)."""

import os

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resources")
FG = QColor("#3a3a3a")


def app_icon() -> QIcon:
    icon = QIcon(os.path.join(RESOURCE_DIR, "snagit.svg"))
    return icon if not icon.isNull() else QIcon.fromTheme("applets-screenshooter")


def _canvas(size=48):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24, size / 24)
    pen = QPen(FG, 2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    return pm, p


def tool_icon(name: str) -> QIcon:
    pm, p = _canvas()
    if name == "select":
        path = QPainterPath(QPointF(6, 3))
        for x, y in ((6, 19), (10.5, 15), (13.5, 21), (16, 20), (13, 14), (19, 14)):
            path.lineTo(x, y)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "text":
        font = QFont("Sans Serif")
        font.setPixelSize(18)
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(0, 0, 24, 24), Qt.AlignmentFlag.AlignCenter, "T")
    elif name == "line":
        p.drawLine(QPointF(4, 20), QPointF(20, 4))
    elif name == "arrow":
        p.drawLine(QPointF(4, 20), QPointF(17, 7))
        p.setBrush(FG)
        p.drawPolygon(QPolygonF([QPointF(20, 4), QPointF(11, 7), QPointF(17, 13)]))
    elif name == "ellipse":
        p.drawEllipse(QRectF(3, 5, 18, 14))
    elif name == "rect":
        p.drawRect(QRectF(3, 5, 18, 14))
    p.end()
    return QIcon(pm)


def color_icon(color: QColor, size=22) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(0, 0, 0, 90), 2))
    p.setBrush(color)
    p.drawEllipse(QRectF(4, 4, size * 2 - 8, size * 2 - 8))
    p.end()
    return QIcon(pm)


def rainbow_icon(size=22) -> QIcon:
    from PyQt6.QtGui import QConicalGradient
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QConicalGradient(size, size, 0)
    for i, c in enumerate(("#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff", "#ff0000")):
        grad.setColorAt(i / 6, QColor(c))
    p.setPen(QPen(QColor(0, 0, 0, 90), 2))
    p.setBrush(grad)
    p.drawEllipse(QRectF(4, 4, size * 2 - 8, size * 2 - 8))
    p.end()
    return QIcon(pm)


def themed(name: str, fallback_text: str = "") -> QIcon:
    icon = QIcon.fromTheme(name)
    if not icon.isNull() or not fallback_text:
        return icon
    pm, p = _canvas()
    font = QFont("Sans Serif")
    font.setPixelSize(14)
    p.setFont(font)
    p.drawText(QRectF(0, 0, 24, 24), Qt.AlignmentFlag.AlignCenter, fallback_text)
    p.end()
    return QIcon(pm)
