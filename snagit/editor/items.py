"""Các đối tượng vẽ chú thích trên ảnh."""

import math

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PyQt6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem, QGraphicsRectItem,
                             QGraphicsTextItem, QStyle)

ITEM_FLAGS = QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsMovable


def make_pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


class ShapeStyleMixin:
    """Màu & độ dày nét cho các hình dùng QPen (đoạn thẳng, chữ nhật, elip)."""

    def get_style(self) -> dict:
        pen = self.pen()
        return {"color": QColor(pen.color()), "width": pen.widthF()}

    def set_style(self, style: dict):
        pen = self.pen()
        if "color" in style:
            pen.setColor(style["color"])
        if "width" in style:
            pen.setWidthF(style["width"])
        self.setPen(pen)


class LineItem(ShapeStyleMixin, QGraphicsLineItem):
    def __init__(self, start: QPointF, color: QColor, width: float):
        super().__init__(QLineF(start, start))
        self.setPen(make_pen(color, width))
        self.setFlags(ITEM_FLAGS)

    def set_points(self, p1: QPointF, p2: QPointF):
        self.setLine(QLineF(p1, p2))

    def is_degenerate(self) -> bool:
        return self.line().length() < 3


class RectItem(ShapeStyleMixin, QGraphicsRectItem):
    def __init__(self, start: QPointF, color: QColor, width: float):
        super().__init__(QRectF(start, start))
        self.setPen(make_pen(color, width))
        self.setFlags(ITEM_FLAGS)

    def set_points(self, p1: QPointF, p2: QPointF):
        self.setRect(QRectF(p1, p2).normalized())

    def is_degenerate(self) -> bool:
        r = self.rect()
        return r.width() < 3 and r.height() < 3


class EllipseItem(ShapeStyleMixin, QGraphicsEllipseItem):
    def __init__(self, start: QPointF, color: QColor, width: float):
        super().__init__(QRectF(start, start))
        self.setPen(make_pen(color, width))
        self.setFlags(ITEM_FLAGS)

    def set_points(self, p1: QPointF, p2: QPointF):
        self.setRect(QRectF(p1, p2).normalized())

    def is_degenerate(self) -> bool:
        r = self.rect()
        return r.width() < 3 and r.height() < 3


class ArrowItem(QGraphicsItem):
    """Mũi tên: thân là đoạn thẳng, đầu là tam giác đặc tỉ lệ theo độ dày nét."""

    def __init__(self, start: QPointF, color: QColor, width: float):
        super().__init__()
        self._p1 = QPointF(start)
        self._p2 = QPointF(start)
        self._color = QColor(color)
        self._width = width
        self.setFlags(ITEM_FLAGS)

    def set_points(self, p1: QPointF, p2: QPointF):
        self.prepareGeometryChange()
        self._p1, self._p2 = QPointF(p1), QPointF(p2)
        self.update()

    def is_degenerate(self) -> bool:
        return QLineF(self._p1, self._p2).length() < 3

    def get_style(self) -> dict:
        return {"color": QColor(self._color), "width": self._width}

    def set_style(self, style: dict):
        self.prepareGeometryChange()
        self._color = QColor(style.get("color", self._color))
        self._width = style.get("width", self._width)
        self.update()

    def _head(self):
        line = QLineF(self._p1, self._p2)
        length = line.length()
        head_len = min(max(12.0, self._width * 4.0), length * 0.6 if length else 0)
        head_half = head_len * 0.5
        if length == 0:
            return QPolygonF(), self._p2
        ux, uy = (self._p2.x() - self._p1.x()) / length, (self._p2.y() - self._p1.y()) / length
        base = QPointF(self._p2.x() - ux * head_len, self._p2.y() - uy * head_len)
        left = QPointF(base.x() - uy * head_half, base.y() + ux * head_half)
        right = QPointF(base.x() + uy * head_half, base.y() - ux * head_half)
        return QPolygonF([self._p2, left, right]), base

    def _path(self) -> QPainterPath:
        head, _ = self._head()
        path = QPainterPath(self._p1)
        path.lineTo(self._p2)
        path.addPolygon(head)
        return path

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self._width, 1) + 8)
        return stroker.createStroke(self._path()).united(self._path())

    def boundingRect(self) -> QRectF:
        m = self._width + 12
        return self._path().boundingRect().adjusted(-m, -m, m, m)

    def paint(self, painter, option, widget=None):
        head, base = self._head()
        painter.setPen(make_pen(self._color, self._width))
        painter.drawLine(QLineF(self._p1, base))
        painter.setPen(make_pen(self._color, 1))
        painter.setBrush(QBrush(self._color))
        painter.drawPolygon(head)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(QPen(QColor(0, 145, 255), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.shape())


class TextItem(QGraphicsTextItem):
    """Ghi chú văn bản. Kết thúc chỉnh sửa khi mất focus -> báo cho scene để ghi Undo."""

    def __init__(self, pos: QPointF, color: QColor, font: QFont, on_edit_finished=None):
        super().__init__()
        self.setPos(pos)
        self.setDefaultTextColor(color)
        self.setFont(font)
        self.setFlags(ITEM_FLAGS)
        self.is_new = True
        self.text_before = ""
        self._on_edit_finished = on_edit_finished

    def get_style(self) -> dict:
        return {"color": QColor(self.defaultTextColor()), "font": QFont(self.font())}

    def set_style(self, style: dict):
        if "color" in style:
            self.setDefaultTextColor(style["color"])
        if "font" in style:
            self.setFont(style["font"])

    def is_editing(self) -> bool:
        return bool(self.textInteractionFlags() & Qt.TextInteractionFlag.TextEditorInteraction)

    def start_editing(self):
        self.text_before = self.toPlainText()
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if self.is_editing():
            self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            cursor = self.textCursor()
            cursor.clearSelection()
            self.setTextCursor(cursor)
            if self._on_edit_finished:
                self._on_edit_finished(self)

    def paint(self, painter, option, widget=None):
        # Bỏ khung chọn mặc định khi đang gõ chữ cho gọn mắt
        if self.is_editing():
            option.state &= ~QStyle.StateFlag.State_Selected
            painter.setPen(QPen(QColor(0, 145, 255, 160), 1, Qt.PenStyle.DashLine))
            painter.drawRect(self.boundingRect())
        super().paint(painter, option, widget)


def constrain(tool: str, p1: QPointF, p2: QPointF) -> QPointF:
    """Giữ Shift: đoạn thẳng/mũi tên bám góc 45°, hình chữ nhật/elip thành hình vuông/tròn."""
    dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
    if tool in ("line", "arrow"):
        length = math.hypot(dx, dy)
        angle = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
        return QPointF(p1.x() + length * math.cos(angle), p1.y() + length * math.sin(angle))
    side = max(abs(dx), abs(dy))
    return QPointF(p1.x() + math.copysign(side, dx or 1), p1.y() + math.copysign(side, dy or 1))
