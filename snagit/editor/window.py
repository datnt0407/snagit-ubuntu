"""Cửa sổ chỉnh sửa ảnh sau khi chụp."""

import os

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor, QFont, QImage, QKeySequence, QPainter
from PyQt6.QtWidgets import (QColorDialog, QFileDialog, QFontComboBox, QGraphicsView, QLabel, QMainWindow,
                             QMessageBox, QSizePolicy, QSpinBox, QToolBar, QToolButton, QWidget)

from snagit import icons
from snagit.editor import tools as T
from snagit.editor.tools import AnnotationScene

PALETTE = ["#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#8e24aa", "#000000", "#ffffff"]

TOOLS = [
    (T.TOOL_SELECT, "Chọn / Di chuyển", "V"),
    (T.TOOL_PEN, "Bút vẽ tự do", "P"),
    (T.TOOL_TEXT, "Văn bản", "T"),
    (T.TOOL_CALLOUT, "Callout (hộp chú thích có đuôi)", "C"),
    (T.TOOL_LINE, "Đoạn thẳng", "L"),
    (T.TOOL_ARROW, "Mũi tên", "A"),
    (T.TOOL_ELLIPSE, "Hình tròn / Elip", "E"),
    (T.TOOL_RECT, "Hình chữ nhật", "R"),
]

TOOL_CURSORS = {
    T.TOOL_SELECT: Qt.CursorShape.ArrowCursor,
    T.TOOL_TEXT: Qt.CursorShape.IBeamCursor,
}


class AnnotationView(QGraphicsView):
    zoom_changed = pyqtSignal(float)

    def __init__(self, scene, window):
        super().__init__(scene)
        self._window = window
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform |
                            QPainter.RenderHint.TextAntialiasing)
        self.setBackgroundBrush(QColor("#2b2b2b"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

    def zoom(self) -> float:
        return self.transform().m11()

    def set_zoom(self, z: float):
        z = min(max(z, 0.05), 16.0)
        self.resetTransform()
        self.scale(z, z)
        self.zoom_changed.emit(z)

    def fit(self):
        rect = self.scene().image_rect()
        vp = self.viewport().size()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        z = min(1.0, (vp.width() - 16) / rect.width(), (vp.height() - 16) / rect.height())
        self.set_zoom(z)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self.zoom() * factor)
            return
        super().wheelEvent(e)

    def keyPressEvent(self, e):
        scene = self.scene()
        if scene.editing_text_item() is not None:
            if e.key() == Qt.Key.Key_Escape:
                scene.finish_text_editing()
                return
            super().keyPressEvent(e)
            return
        if e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._window.delete_selected()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._window.finish()
        elif e.key() == Qt.Key.Key_Escape:
            self._window.cancel()
        else:
            super().keyPressEvent(e)


class EditorWindow(QMainWindow):
    """exporter(image: QImage) -> str: hàm xuất ảnh (clipboard + lưu file), trả về thông báo kết quả."""

    def __init__(self, image: QImage, settings, exporter, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(f"Snagit - Chỉnh sửa ({image.width()} × {image.height()})")
        self.setWindowIcon(icons.app_icon())
        self._settings = settings
        self._exporter = exporter
        self._handled = False

        self.scene = AnnotationScene(image, self)
        self._load_style()
        self.view = AnnotationView(self.scene, self)
        self.setCentralWidget(self.view)

        self._build_actions()
        self._build_toolbars()
        self._build_statusbar()
        self.set_tool(self._settings.editor_value("tool", T.TOOL_ARROW, str))
        self._resize_to_image(image)

    # ---------- Khởi tạo giao diện ----------
    def _load_style(self):
        s = self._settings
        self.scene.color = QColor(s.editor_value("color", "#e53935", str))
        self.scene.stroke_width = s.editor_value("width", 4, int)
        self.scene.text_font = QFont(s.editor_value("font_family", "Sans Serif", str),
                                     s.editor_value("font_size", 18, int))

    def _build_actions(self):
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_actions = {}
        for key, label, shortcut in TOOLS:
            act = QAction(icons.tool_icon(key), label, self, checkable=True)
            act.setShortcut(QKeySequence(shortcut))
            act.setToolTip(f"{label} ({shortcut})")
            act.triggered.connect(lambda _=False, k=key: self.set_tool(k))
            self.tool_group.addAction(act)
            self.tool_actions[key] = act

        stack = self.scene.undo_stack
        self.act_undo = QAction(icons.themed("edit-undo", "↶"), "Hoàn tác", self)
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.act_undo.setToolTip("Hoàn tác (Ctrl+Z)")
        self.act_undo.triggered.connect(self.undo)
        self.act_undo.setEnabled(False)
        stack.canUndoChanged.connect(self.act_undo.setEnabled)

        self.act_redo = QAction(icons.themed("edit-redo", "↷"), "Làm lại", self)
        self.act_redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.act_redo.setToolTip("Làm lại (Ctrl+Y)")
        self.act_redo.triggered.connect(self.redo)
        self.act_redo.setEnabled(False)
        stack.canRedoChanged.connect(self.act_redo.setEnabled)

        self.act_delete = QAction(icons.themed("edit-delete", "✕"), "Xóa", self)
        self.act_delete.setToolTip("Xóa đối tượng đang chọn (Delete)")
        self.act_delete.triggered.connect(self.delete_selected)
        self.act_delete.setEnabled(False)
        self.scene.selectionChanged.connect(
            lambda: self.act_delete.setEnabled(bool(self.scene.selectedItems())))

        self.act_save_as = QAction(icons.themed("document-save-as", "💾"), "Lưu thành...", self)
        self.act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.setToolTip("Lưu thành file khác (Ctrl+Shift+S)")
        self.act_save_as.triggered.connect(self.save_as)

        self.act_done = QAction(icons.themed("object-select", "✓"), "Xong", self)
        self.act_done.setShortcut(QKeySequence("Ctrl+S"))
        self.act_done.setToolTip("Xong: chép vào clipboard và lưu ảnh (Ctrl+S / Enter)")
        self.act_done.triggered.connect(self.finish)

        act_fit = QAction("Vừa cửa sổ", self, shortcut=QKeySequence("Ctrl+0"))
        act_fit.triggered.connect(self.view.fit)
        act_100 = QAction("100%", self, shortcut=QKeySequence("Ctrl+1"))
        act_100.triggered.connect(lambda: self.view.set_zoom(1.0))
        act_zoom_in = QAction("Phóng to", self, shortcut=QKeySequence("Ctrl+="))
        act_zoom_in.triggered.connect(lambda: self.view.set_zoom(self.view.zoom() * 1.25))
        act_zoom_out = QAction("Thu nhỏ", self, shortcut=QKeySequence("Ctrl+-"))
        act_zoom_out.triggered.connect(lambda: self.view.set_zoom(self.view.zoom() / 1.25))
        self.addActions([act_fit, act_100, act_zoom_in, act_zoom_out])

    def _build_toolbars(self):
        main = QToolBar("Công cụ", self)
        main.setMovable(False)
        main.setIconSize(QSize(22, 22))
        main.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        for key, *_ in TOOLS:
            main.addAction(self.tool_actions[key])
        main.addSeparator()
        main.addActions([self.act_undo, self.act_redo, self.act_delete])
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        main.addWidget(spacer)
        main.addAction(self.act_save_as)
        done_btn = QToolButton()
        done_btn.setDefaultAction(self.act_done)
        done_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        done_btn.setStyleSheet("QToolButton { background: #1e88e5; color: white; border-radius: 4px;"
                               " padding: 4px 14px; font-weight: bold; }"
                               "QToolButton:hover { background: #1976d2; }")
        main.addWidget(done_btn)
        self.addToolBar(main)
        self.addToolBarBreak()

        style = QToolBar("Kiểu nét", self)
        style.setMovable(False)
        style.setIconSize(QSize(20, 20))
        style.addWidget(QLabel(" Màu: "))
        self.color_group = QActionGroup(self)
        self.color_actions = []
        for hex_ in PALETTE:
            c = QColor(hex_)
            act = QAction(icons.color_icon(c), hex_, self, checkable=True)
            act.setData(c)
            act.triggered.connect(lambda _=False, col=c: self.set_color(col))
            self.color_group.addAction(act)
            style.addAction(act)
            self.color_actions.append(act)
        self.act_custom_color = QAction(icons.rainbow_icon(), "Màu khác...", self, checkable=True)
        self.act_custom_color.triggered.connect(self.pick_custom_color)
        self.color_group.addAction(self.act_custom_color)
        style.addAction(self.act_custom_color)

        style.addSeparator()
        style.addWidget(QLabel(" Độ dày nét: "))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 40)
        self.width_spin.setSuffix(" px")
        self.width_spin.setValue(self.scene.stroke_width)
        self.width_spin.setToolTip("Độ dày nét vẽ")
        self.width_spin.valueChanged.connect(self.set_stroke_width)
        style.addWidget(self.width_spin)

        style.addSeparator()
        style.addWidget(QLabel(" Phông chữ: "))
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(self.scene.text_font)
        self.font_combo.setMaximumWidth(200)
        self.font_combo.currentFontChanged.connect(lambda _: self.set_font())
        style.addWidget(self.font_combo)
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 200)
        self.font_size.setSuffix(" pt")
        self.font_size.setValue(self.scene.text_font.pointSize())
        self.font_size.setToolTip("Cỡ chữ")
        self.font_size.valueChanged.connect(lambda _: self.set_font())
        style.addWidget(self.font_size)
        self.addToolBar(style)
        self._sync_color_buttons()

    def _build_statusbar(self):
        self.zoom_label = QLabel()
        self.statusBar().addPermanentWidget(self.zoom_label)
        self.view.zoom_changed.connect(lambda z: self.zoom_label.setText(f"Thu phóng: {round(z * 100)}%  "))
        self.statusBar().showMessage(
            "Giữ Shift để vẽ thẳng 45° / hình vuông / hình tròn  •  Kéo tay nắm tròn để chỉnh đuôi callout  •  "
            "Ctrl+lăn chuột để thu phóng  •  "
            "Enter để hoàn tất, Esc để hủy")

    def _resize_to_image(self, image: QImage):
        screen = self.screen() or self.window().screen()
        avail = screen.availableGeometry()
        dpr = screen.devicePixelRatio()
        w = min(max(image.width() / dpr + 60, 960), avail.width() * 0.9)
        h = min(max(image.height() / dpr + 150, 520), avail.height() * 0.9)
        self.resize(int(w), int(h))

    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_fitted", False):
            self._fitted = True
            self.view.fit()

    # ---------- Kiểu nét ----------
    def _sync_color_buttons(self):
        for act in self.color_actions:
            if act.data() == self.scene.color:
                act.setChecked(True)
                return
        self.act_custom_color.setChecked(True)
        self.act_custom_color.setIcon(icons.color_icon(self.scene.color))

    def set_tool(self, key: str):
        if key not in self.tool_actions:
            key = T.TOOL_ARROW
        self.scene.finish_text_editing()
        self.scene.tool = key
        self.tool_actions[key].setChecked(True)
        if key != T.TOOL_SELECT:
            self.scene.clearSelection()
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag if key == T.TOOL_SELECT
                              else QGraphicsView.DragMode.NoDrag)
        self.view.viewport().setCursor(TOOL_CURSORS.get(key, Qt.CursorShape.CrossCursor))
        self._settings.set_editor_value("tool", key)

    def set_color(self, color: QColor):
        self.scene.color = QColor(color)
        self._settings.set_editor_value("color", color.name())
        self._sync_color_buttons()
        self.scene.apply_style_to_selection({"color": QColor(color)})

    def pick_custom_color(self):
        color = QColorDialog.getColor(self.scene.color, self, "Chọn màu")
        if color.isValid():
            self.set_color(color)
        else:
            self._sync_color_buttons()

    def set_stroke_width(self, width: int):
        self.scene.stroke_width = width
        self._settings.set_editor_value("width", width)
        self.scene.apply_style_to_selection({"width": width})

    def set_font(self):
        font = QFont(self.font_combo.currentFont().family(), self.font_size.value())
        self.scene.text_font = font
        self._settings.set_editor_value("font_family", font.family())
        self._settings.set_editor_value("font_size", font.pointSize())
        editing = self.scene.editing_text_item()
        if editing is not None:
            editing.setFont(font)
        else:
            self.scene.apply_style_to_selection({"font": font})

    # ---------- Thao tác ----------
    def undo(self):
        self.scene.finish_text_editing()
        self.scene.undo_stack.undo()

    def redo(self):
        self.scene.finish_text_editing()
        self.scene.undo_stack.redo()

    def delete_selected(self):
        if self.scene.editing_text_item() is None:
            self.scene.delete_selected()

    def save_as(self):
        image = self.scene.render_image()
        fmt = self._settings.image_format
        start = os.path.join(self._settings.save_dir, f"Screenshot.{fmt}")
        path, _ = QFileDialog.getSaveFileName(self, "Lưu ảnh", start, "Ảnh PNG (*.png);;Ảnh JPEG (*.jpg *.jpeg)")
        if not path:
            return
        from snagit.export import save_image
        if save_image(image, path, self._settings.jpg_quality):
            self.statusBar().showMessage(f"Đã lưu: {path}", 5000)
        else:
            QMessageBox.warning(self, "Snagit", f"Không lưu được ảnh vào:\n{path}")

    def finish(self):
        if self._handled:
            return
        image = self.scene.render_image()
        message = self._exporter(image)
        self._handled = True
        if message:
            self.statusBar().showMessage(message)
        self.close()

    def cancel(self):
        if self.scene.undo_stack.count() > 0:
            answer = QMessageBox.question(self, "Snagit", "Bỏ ảnh chụp này? Các chỉnh sửa sẽ không được lưu.",
                                          QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                          QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Discard:
                return
        self._handled = True
        self.close()

    def closeEvent(self, e):
        # Đóng cửa sổ bằng nút X cũng được coi là "Xong"
        if not self._handled:
            self._handled = True
            self._exporter(self.scene.render_image())
        # Scene phát selectionChanged khi bị hủy -> ngắt trước để không gọi vào đối tượng đã xóa
        self.scene.selectionChanged.disconnect()
        super().closeEvent(e)

