"""Scene chú thích: xử lý chuột cho từng công cụ và ghi lại lịch sử Undo/Redo."""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap, QTransform, QUndoStack
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene

from snagit.editor.commands import (AddItemCommand, EditTextCommand, MoveItemsCommand, RemoveItemsCommand,
                                    StyleCommand)
from snagit.editor.items import ArrowItem, EllipseItem, LineItem, RectItem, TextItem, constrain

TOOL_SELECT = "select"
TOOL_TEXT = "text"
TOOL_LINE = "line"
TOOL_ARROW = "arrow"
TOOL_ELLIPSE = "ellipse"
TOOL_RECT = "rect"

SHAPE_CLASSES = {
    TOOL_LINE: LineItem,
    TOOL_ARROW: ArrowItem,
    TOOL_ELLIPSE: EllipseItem,
    TOOL_RECT: RectItem,
}


class AnnotationScene(QGraphicsScene):
    def __init__(self, image: QImage, parent=None):
        super().__init__(parent)
        self.undo_stack = QUndoStack(self)
        self.tool = TOOL_ARROW
        self.color = QColor("#e53935")
        self.stroke_width = 4
        self.text_font = QFont("Sans Serif", 18)

        self._background = QGraphicsPixmapItem(QPixmap.fromImage(image))
        self._background.setZValue(-1000)
        self._background.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.addItem(self._background)
        self.setSceneRect(QRectF(image.rect()))

        self._drawing = None
        self._draw_start = QPointF()
        self._move_start = {}
        self._z = 0

    # ---------- Tiện ích ----------
    def image_rect(self) -> QRectF:
        return QRectF(self._background.pixmap().rect())

    def annotations(self):
        return [i for i in self.items() if i is not self._background and i.parentItem() is None]

    def _next_z(self) -> float:
        self._z += 1
        return self._z

    def editing_text_item(self):
        item = self.focusItem()
        return item if isinstance(item, TextItem) and item.is_editing() else None

    def finish_text_editing(self):
        if self.editing_text_item() is not None:
            self.setFocusItem(None)
            self.clearFocus()

    def _item_at(self, pos: QPointF, cls):
        for item in self.items(pos, Qt.ItemSelectionMode.IntersectsItemShape,
                               Qt.SortOrder.DescendingOrder, QTransform()):
            if isinstance(item, cls):
                return item
        return None

    # ---------- Chuột ----------
    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(e)
            return
        pos = e.scenePos()

        if self.tool == TOOL_SELECT:
            super().mousePressEvent(e)
            self._move_start = {item: item.pos() for item in self.selectedItems()}
            return

        # Đang gõ chữ mà click ra ngoài -> kết thúc ô chữ, không tạo đối tượng mới
        editing = self.editing_text_item()
        if editing is not None and not editing.sceneBoundingRect().contains(pos):
            self.finish_text_editing()
            return
        if editing is not None:
            super().mousePressEvent(e)
            return

        if self.tool == TOOL_TEXT:
            self.clearSelection()
            existing = self._item_at(pos, TextItem)
            if existing is not None:
                existing.start_editing()
                return
            item = TextItem(pos, self.color, self.text_font, self._on_text_finished)
            item.setZValue(self._next_z())
            self.addItem(item)
            item.start_editing()
            return

        cls = SHAPE_CLASSES.get(self.tool)
        if cls is not None:
            self.clearSelection()
            self._draw_start = pos
            self._drawing = cls(pos, self.color, self.stroke_width)
            self._drawing.setZValue(self._next_z())
            self.addItem(self._drawing)

    def mouseMoveEvent(self, e):
        if self._drawing is not None:
            end = e.scenePos()
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                end = constrain(self.tool, self._draw_start, end)
            self._drawing.set_points(self._draw_start, end)
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._drawing is not None and e.button() == Qt.MouseButton.LeftButton:
            item, self._drawing = self._drawing, None
            if item.is_degenerate():
                self.removeItem(item)
            else:
                self.undo_stack.push(AddItemCommand(self, item, "Vẽ hình"))
            return
        super().mouseReleaseEvent(e)
        if self.tool == TOOL_SELECT and self._move_start:
            moves = [(item, old, item.pos()) for item, old in self._move_start.items() if item.pos() != old]
            self._move_start = {}
            if moves:
                self.undo_stack.push(MoveItemsCommand(moves))

    def mouseDoubleClickEvent(self, e):
        if self.tool == TOOL_SELECT:
            text = self._item_at(e.scenePos(), TextItem)
            if text is not None:
                text.start_editing()
                return
        super().mouseDoubleClickEvent(e)

    # ---------- Văn bản ----------
    def _on_text_finished(self, item: TextItem):
        text = item.toPlainText()
        if item.is_new:
            if text.strip():
                item.is_new = False
                self.undo_stack.push(AddItemCommand(self, item, "Thêm văn bản"))
            else:
                self.removeItem(item)
            return
        if text == item.text_before:
            return
        if text.strip():
            self.undo_stack.push(EditTextCommand(item, item.text_before, text))
        else:
            # Xóa hết chữ -> coi như xóa đối tượng (khôi phục được bằng Undo)
            item.setPlainText(item.text_before)
            self.undo_stack.push(RemoveItemsCommand(self, [item], "Xóa văn bản"))

    # ---------- Thao tác ----------
    def delete_selected(self) -> bool:
        items = [i for i in self.selectedItems() if i is not self._background]
        if not items:
            return False
        self.undo_stack.push(RemoveItemsCommand(self, items))
        return True

    def apply_style_to_selection(self, style: dict):
        changes = []
        for item in self.selectedItems():
            if not hasattr(item, "set_style"):
                continue
            old = item.get_style()
            new = {k: v for k, v in style.items() if k in old}
            if new and any(old[k] != v for k, v in new.items()):
                changes.append((item, old, {**old, **new}))
        if changes:
            self.undo_stack.push(StyleCommand(changes))

    def render_image(self) -> QImage:
        self.finish_text_editing()
        self.clearSelection()
        rect = self.image_rect()
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing |
                               QPainter.RenderHint.SmoothPixmapTransform)
        self.render(painter, QRectF(image.rect()), rect)
        painter.end()
        return image
