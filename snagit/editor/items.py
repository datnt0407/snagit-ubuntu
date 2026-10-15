"""Các đối tượng vẽ chú thích trên ảnh."""

import math

from PyQt6.QtCore import QLineF, QPointF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PyQt6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem, QGraphicsPathItem,
                             QGraphicsRectItem, QGraphicsTextItem, QStyle)

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


class PenItem(ShapeStyleMixin, QGraphicsPathItem):
    """Nét vẽ tự do, làm mượt bằng đường cong bậc hai đi qua trung điểm các điểm liên tiếp."""

    MIN_STEP = 2.0  # bỏ qua điểm quá sát điểm trước để nét không bị rung

    def __init__(self, start: QPointF, color: QColor, width: float):
        super().__init__()
        self._points = [QPointF(start)]
        self.setPen(make_pen(color, width))
        self.setFlags(ITEM_FLAGS)
        self._rebuild()

    def set_points(self, _start: QPointF, end: QPointF):
        last = self._points[-1]
        if math.hypot(end.x() - last.x(), end.y() - last.y()) < self.MIN_STEP:
            return
        self._points.append(QPointF(end))
        self._rebuild()

    def is_degenerate(self) -> bool:
        return False  # click một lần vẫn để lại một chấm

    def _rebuild(self):
        pts = self._points
        path = QPainterPath(pts[0])
        if len(pts) == 1:
            path.lineTo(pts[0] + QPointF(0.01, 0))  # đoạn siêu ngắn + đầu nét tròn = chấm tròn
        else:
            for prev, cur in zip(pts, pts[1:]):
                path.quadTo(prev, (prev + cur) / 2)
            path.lineTo(pts[-1])
        self.setPath(path)

    def shape(self) -> QPainterPath:
        # Chỉ tính phần nét vẽ, không tính vùng bên trong vòng nét
        stroker = QPainterPathStroker()
        stroker.setWidth(self.pen().widthF() + 6)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        return stroker.createStroke(self.path())


def contrast_text_color(fill: QColor) -> QColor:
    luminance = 0.299 * fill.red() + 0.587 * fill.green() + 0.114 * fill.blue()
    return QColor("#000000") if luminance > 160 else QColor("#ffffff")


class CalloutTextItem(TextItem):
    """Ô chữ nằm trong callout: không tự chọn/di chuyển, chỉ nhận chuột khi đang gõ."""

    def __init__(self, callout, font: QFont, on_edit_finished):
        super().__init__(QPointF(), QColor("#ffffff"), font, on_edit_finished)
        self.setParentItem(callout)
        self.setFlags(QGraphicsItem.GraphicsItemFlag(0))
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.is_new = False
        self.document().setDocumentMargin(2)
        option = self.document().defaultTextOption()
        option.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.document().setDefaultTextOption(option)

    def start_editing(self):
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        super().start_editing()

    def focusOutEvent(self, event):
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        super().focusOutEvent(event)

    def setFont(self, font: QFont):
        super().setFont(font)
        if self.parentItem() is not None:
            self.parentItem().relayout()

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.StateFlag.State_Selected
        QGraphicsTextItem.paint(self, painter, option, widget)


class CalloutItem(QGraphicsItem):
    """Hộp chú thích nền màu đặc kèm đuôi chỉ hướng.

    - Chiều rộng giãn theo chữ (tối thiểu bằng lúc vẽ, tối đa tới gần mép phải ảnh), sau đó
      chữ tự xuống dòng và hộp giãn chiều cao.
    - Khi được chọn, mũi đuôi có tay nắm để kéo chỉ vào nội dung.
    """

    PAD = 10
    RADIUS = 10
    HANDLE_R = 7
    EDGE_MARGIN = 8
    DEFAULT_SIZE = QSizeF(200, 60)
    MIN_SIZE = QSizeF(60, 36)

    def __init__(self, start: QPointF, color: QColor, font: QFont, on_text_finished):
        super().__init__()
        self._ready = False
        self.setFlags(ITEM_FLAGS | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self._color = QColor(color)
        self._min = QSizeF(self.MIN_SIZE)
        self._rect = QRectF(QPointF(0, 0), self._min)
        self._tip = QPointF()
        self._tip_custom = False  # True khi người dùng đã tự kéo đuôi
        self._tail_drag_from = None
        self._in_layout = False
        self.is_new = True
        self.text = CalloutTextItem(self, font, lambda _t: on_text_finished(self))
        self.text.setDefaultTextColor(contrast_text_color(self._color))
        self.text.document().contentsChanged.connect(self.relayout)
        self._ready = True
        self.set_box(start, start)

    # ---------- Hình học ----------
    def set_box(self, p1: QPointF, p2: QPointF):
        """Đặt hộp theo vùng kéo chuột (tọa độ scene). Kích thước này là mức tối thiểu."""
        r = QRectF(p1, p2).normalized()
        self.setPos(r.topLeft())
        self._min = QSizeF(max(r.width(), self.MIN_SIZE.width()), max(r.height(), self.MIN_SIZE.height()))
        self._reset_tip()
        self.relayout()

    def use_default_size(self):
        self._min = QSizeF(self.DEFAULT_SIZE)
        self._reset_tip()
        self.relayout()

    def _reset_tip(self):
        self._tip_custom = False

    def _default_tip(self) -> QPointF:
        # Đuôi mặc định hướng xuống dưới-trái và đi theo cạnh dưới khi hộp giãn
        return QPointF(min(40.0, self._rect.width() * 0.3), self._rect.height() + 50)

    def is_degenerate(self) -> bool:
        return self._min.width() <= self.MIN_SIZE.width() and self._min.height() <= self.MIN_SIZE.height()

    def _max_width(self) -> float:
        scene = self.scene()
        if scene is None or not hasattr(scene, "image_rect"):
            return float("inf")
        return scene.image_rect().right() - self.EDGE_MARGIN - self.pos().x()

    def relayout(self):
        if not self._ready or self._in_layout:
            return
        self._in_layout = True
        try:
            self.prepareGeometryChange()
            t = self.text
            t.setTextWidth(-1)
            natural = t.boundingRect().width() + 2 * self.PAD
            max_w = max(self._min.width(), self._max_width())
            width = min(max(natural, self._min.width()), max_w)
            t.setTextWidth(width - 2 * self.PAD)
            text_h = t.boundingRect().height()
            height = max(self._min.height(), text_h + 2 * self.PAD)
            self._rect = QRectF(0, 0, width, height)
            if not self._tip_custom:
                self._tip = self._default_tip()
            t.setPos(self.PAD, (height - text_h) / 2)
            self.update()
        finally:
            self._in_layout = False

    def itemChange(self, change, value):
        if change in (QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
                      QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged):
            self.relayout()
        return super().itemChange(change, value)

    def tip(self) -> QPointF:
        return QPointF(self._tip)

    def set_tip(self, tip: QPointF):
        self.prepareGeometryChange()
        self._tip_custom = True
        self._tip = QPointF(tip)
        self.update()

    def _tail_polygon(self):
        rect, tip = self._rect, self._tip
        if rect.contains(tip):
            return None
        c = rect.center()
        dx, dy = tip.x() - c.x(), tip.y() - c.y()
        half_w, half_h = rect.width() / 2, rect.height() / 2
        inset = 2.0  # gốc đuôi lấn vào trong hộp để không lộ khe hở khi ghép hình
        if abs(dx) / half_w > abs(dy) / half_h:  # đuôi ra từ cạnh trái/phải
            half = max(4.0, min(14.0, (rect.height() - 2 * self.RADIUS) * 0.4))
            x = rect.right() - inset if dx > 0 else rect.left() + inset
            y = c.y() + dy * (half_w / abs(dx))
            lo, hi = rect.top() + self.RADIUS + half, rect.bottom() - self.RADIUS - half
            y = min(max(y, lo), hi) if lo <= hi else c.y()
            return QPolygonF([QPointF(x, y - half), tip, QPointF(x, y + half)])
        half = max(4.0, min(14.0, (rect.width() - 2 * self.RADIUS) * 0.4))
        y = rect.bottom() - inset if dy > 0 else rect.top() + inset
        x = c.x() + dx * (half_h / abs(dy)) if dy else c.x()
        lo, hi = rect.left() + self.RADIUS + half, rect.right() - self.RADIUS - half
        x = min(max(x, lo), hi) if lo <= hi else c.x()
        return QPolygonF([QPointF(x - half, y), tip, QPointF(x + half, y)])

    def body_path(self) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(self._rect, self.RADIUS, self.RADIUS)
        tail = self._tail_polygon()
        if tail is not None:
            tail_path = QPainterPath()
            tail_path.addPolygon(tail)
            tail_path.closeSubpath()
            path = path.united(tail_path)
        return path

    def _handle_rect(self) -> QRectF:
        r = self.HANDLE_R
        return QRectF(self._tip.x() - r, self._tip.y() - r, 2 * r, 2 * r)

    def _show_handle(self) -> bool:
        return self.isSelected() or self.text.is_editing()

    def handle_hit(self, scene_pos: QPointF) -> bool:
        local = self.mapFromScene(scene_pos)
        return QLineF(local, self._tip).length() <= self.HANDLE_R + 4

    def shape(self) -> QPainterPath:
        path = self.body_path()
        if self._show_handle():
            path.addEllipse(self._handle_rect().adjusted(-4, -4, 4, 4))
        return path

    def boundingRect(self) -> QRectF:
        m = self.HANDLE_R + 6
        return self.body_path().boundingRect().united(self._handle_rect()).adjusted(-m, -m, m, m)

    def paint(self, painter, option, widget=None):
        painter.setPen(QPen(self._color.darker(130), 1))
        painter.setBrush(QBrush(self._color))
        painter.drawPath(self.body_path())
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(QPen(QColor(0, 145, 255), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._rect.adjusted(-3, -3, 3, 3))
        if self._show_handle():
            painter.setPen(QPen(QColor(0, 145, 255), 2))
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(self._handle_rect())

    # ---------- Kiểu ----------
    def get_style(self) -> dict:
        return {"color": QColor(self._color), "font": QFont(self.text.font())}

    def set_style(self, style: dict):
        if "color" in style:
            self._color = QColor(style["color"])
            self.text.setDefaultTextColor(contrast_text_color(self._color))
        if "font" in style:
            self.text.setFont(style["font"])
        self.update()

    def start_editing(self):
        self.text.start_editing()
        self.update()

    # ---------- Kéo tay nắm đuôi ----------
    def hoverMoveEvent(self, e):
        if self._show_handle() and self.handle_hit(e.scenePos()):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.unsetCursor()
        super().hoverMoveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._show_handle() and self.handle_hit(e.scenePos()):
            self._tail_drag_from = QPointF(self._tip)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._tail_drag_from is not None:
            self.set_tip(e.pos())
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._tail_drag_from is not None:
            old, self._tail_drag_from = self._tail_drag_from, None
            scene = self.scene()
            if old != self._tip and scene is not None and hasattr(scene, "on_tail_moved"):
                scene.on_tail_moved(self, old, QPointF(self._tip))
            return
        super().mouseReleaseEvent(e)


def constrain(tool: str, p1: QPointF, p2: QPointF) -> QPointF:
    """Giữ Shift: đoạn thẳng/mũi tên bám góc 45°, hình chữ nhật/elip thành hình vuông/tròn."""
    dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
    if tool in ("line", "arrow"):
        length = math.hypot(dx, dy)
        angle = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
        return QPointF(p1.x() + length * math.cos(angle), p1.y() + length * math.sin(angle))
    side = max(abs(dx), abs(dy))
    return QPointF(p1.x() + math.copysign(side, dx or 1), p1.y() + math.copysign(side, dy or 1))
