"""Các lệnh Undo/Redo cho trình chỉnh sửa (QUndoStack)."""

from PyQt6.QtGui import QUndoCommand


class AddItemCommand(QUndoCommand):
    """Thêm đối tượng. Đối tượng thường đã có sẵn trong scene khi lệnh được push."""

    def __init__(self, scene, item, text="Thêm đối tượng"):
        super().__init__(text)
        self._scene, self._item = scene, item

    def redo(self):
        if self._item.scene() is None:
            self._scene.addItem(self._item)

    def undo(self):
        if self._item.scene() is not None:
            self._scene.removeItem(self._item)


class RemoveItemsCommand(QUndoCommand):
    def __init__(self, scene, items, text="Xóa đối tượng"):
        super().__init__(text)
        self._scene, self._items = scene, list(items)

    def redo(self):
        for item in self._items:
            if item.scene() is not None:
                self._scene.removeItem(item)

    def undo(self):
        for item in self._items:
            if item.scene() is None:
                self._scene.addItem(item)


class MoveItemsCommand(QUndoCommand):
    def __init__(self, moves, text="Di chuyển"):
        """moves: list[(item, old_pos, new_pos)]"""
        super().__init__(text)
        self._moves = moves

    def redo(self):
        for item, _, new in self._moves:
            item.setPos(new)

    def undo(self):
        for item, old, _ in self._moves:
            item.setPos(old)


class StyleCommand(QUndoCommand):
    def __init__(self, changes, text="Đổi kiểu"):
        """changes: list[(item, old_style, new_style)]"""
        super().__init__(text)
        self._changes = changes

    def redo(self):
        for item, _, new in self._changes:
            item.set_style(new)

    def undo(self):
        for item, old, _ in self._changes:
            item.set_style(old)


class MoveTailCommand(QUndoCommand):
    def __init__(self, callout, old_tip, new_tip):
        super().__init__("Di chuyển đuôi callout")
        self._callout, self._old, self._new = callout, old_tip, new_tip

    def redo(self):
        self._callout.set_tip(self._new)

    def undo(self):
        self._callout.set_tip(self._old)


class EditTextCommand(QUndoCommand):
    def __init__(self, item, old_text, new_text):
        super().__init__("Sửa văn bản")
        self._item, self._old, self._new = item, old_text, new_text

    def redo(self):
        if self._item.toPlainText() != self._new:
            self._item.setPlainText(self._new)

    def undo(self):
        self._item.setPlainText(self._old)
