"""Lớp phủ chọn vùng chụp.

Mỗi màn hình có một cửa sổ toàn màn hình hiển thị ảnh đã "đóng băng" và phủ mờ.
- Kéo thả chuột: chọn vùng tùy chỉnh (hiển thị kích thước W × H).
- Click (không kéo): chụp toàn bộ màn hình đó.
- Esc / chuột phải: hủy.
"""

from PyQt6.QtCore import QObject, QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

DRAG_THRESHOLD = 4
DIM_COLOR = QColor(0, 0, 0, 120)
ACCENT = QColor(0, 145, 255)
HINT = "Kéo để chọn vùng  •  Click để chụp toàn màn hình  •  Esc để hủy"


class ScreenOverlay(QWidget):
    selected = pyqtSignal(QImage)
    cancelled = pyqtSignal()

    def __init__(self, screen, image: QImage):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Snagit - Chọn vùng chụp")
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self._screen = screen
        self._image = image
        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self._mouse = QPoint(-1, -1)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def show_on_screen(self):
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    # ---------- Tọa độ ----------
    def _scale(self) -> float:
        return self._image.width() / max(1, self.width())

    def _selection(self) -> QRect | None:
        if self._origin is None or self._current is None:
            return None
        a, b = self._origin, self._current
        return QRect(min(a.x(), b.x()), min(a.y(), b.y()), abs(b.x() - a.x()), abs(b.y() - a.y()))

    def _is_drag(self) -> bool:
        if self._origin is None or self._current is None:
            return False
        d = self._current - self._origin
        return abs(d.x()) >= DRAG_THRESHOLD or abs(d.y()) >= DRAG_THRESHOLD

    def _to_image_rect(self, rect: QRect) -> QRect:
        s = self._scale()
        r = QRect(round(rect.x() * s), round(rect.y() * s), round(rect.width() * s), round(rect.height() * s))
        return r.intersected(self._image.rect())

    # ---------- Sự kiện chuột/phím ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            if self._origin is not None:
                self._origin = self._current = None
                self.update()
            else:
                self.cancelled.emit()
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self._origin = self._current = e.position().toPoint()
            self.update()

    def mouseMoveEvent(self, e):
        self._mouse = e.position().toPoint()
        if self._origin is not None:
            self._current = self._clamp(self._mouse)
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        self._current = self._clamp(e.position().toPoint())
        if self._is_drag():
            rect = self._to_image_rect(self._selection())
            if rect.width() > 0 and rect.height() > 0:
                self.selected.emit(self._image.copy(rect))
                return
        self.selected.emit(self._image.copy())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            sel = self._selection()
            if sel is not None and self._is_drag():
                self.selected.emit(self._image.copy(self._to_image_rect(sel)))
            else:
                self.selected.emit(self._image.copy())

    def _clamp(self, p: QPoint) -> QPoint:
        return QPoint(min(max(p.x(), 0), self.width()), min(max(p.y(), 0), self.height()))

    # ---------- Vẽ ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.drawImage(QRectF(self.rect()), self._image)

        sel = self._selection() if self._is_drag() else None
        dim = QPainterPath()
        dim.addRect(QRectF(self.rect()))
        if sel is not None:
            hole = QPainterPath()
            hole.addRect(QRectF(sel))
            dim = dim.subtracted(hole)
        p.fillPath(dim, DIM_COLOR)

        if sel is not None:
            p.setPen(QPen(ACCENT, 1))
            p.drawRect(sel.adjusted(0, 0, -1, -1))
            img_rect = self._to_image_rect(sel)
            self._draw_label(p, f"{img_rect.width()} × {img_rect.height()}", sel)
        else:
            self._draw_crosshair(p)
            self._draw_hint(p)
        p.end()

    def _draw_label(self, p: QPainter, text: str, sel: QRect):
        font = QFont(self.font())
        font.setPointSize(10)
        font.setBold(True)
        p.setFont(font)
        fm = p.fontMetrics()
        w, h = fm.horizontalAdvance(text) + 14, fm.height() + 8
        x = sel.left()
        y = sel.top() - h - 4
        if y < 0:  # không đủ chỗ phía trên -> đặt vào trong vùng chọn
            y = sel.top() + 4
            x = sel.left() + 4
        x = min(x, self.width() - w)
        box = QRect(x, y, w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 20, 20, 220))
        p.drawRoundedRect(box, 4, 4)
        p.setPen(Qt.GlobalColor.white)
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_crosshair(self, p: QPainter):
        if not self.rect().contains(self._mouse):
            return
        p.setPen(QPen(QColor(255, 255, 255, 110), 1, Qt.PenStyle.DashLine))
        p.drawLine(0, self._mouse.y(), self.width(), self._mouse.y())
        p.drawLine(self._mouse.x(), 0, self._mouse.x(), self.height())

    def _draw_hint(self, p: QPainter):
        font = QFont(self.font())
        font.setPointSize(12)
        p.setFont(font)
        fm = p.fontMetrics()
        w, h = fm.horizontalAdvance(HINT) + 32, fm.height() + 16
        box = QRect((self.width() - w) // 2, 40, w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 20, 20, 200))
        p.drawRoundedRect(box, 8, 8)
        p.setPen(Qt.GlobalColor.white)
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, HINT)


class SelectionSession(QObject):
    """Quản lý các lớp phủ trên mọi màn hình cho một lần chụp."""

    selected = pyqtSignal(QImage)
    cancelled = pyqtSignal()

    def __init__(self, shots, parent=None):
        super().__init__(parent)
        self._overlays = []
        for screen, image in shots:
            ov = ScreenOverlay(screen, image)
            ov.selected.connect(self._on_selected)
            ov.cancelled.connect(self._on_cancelled)
            self._overlays.append(ov)

    def start(self):
        for ov in self._overlays:
            ov.show_on_screen()

    def _close_all(self):
        for ov in self._overlays:
            ov.close()
        self._overlays = []

    def _on_selected(self, image: QImage):
        # Mở trình chỉnh sửa trước khi đóng lớp phủ: trên Wayland cửa sổ mới chỉ được
        # cấp focus khi có cửa sổ đang focus của ứng dụng "chuyển giao" quyền kích hoạt.
        self.selected.emit(image)
        self._close_all()

    def _on_cancelled(self):
        self._close_all()
        self.cancelled.emit()
