"""Chụp ảnh toàn bộ màn hình.

- Wayland: dùng xdg-desktop-portal (org.freedesktop.portal.Screenshot) ở chế độ không tương tác.
- X11: dùng trực tiếp QScreen.grabWindow(0).

Kết quả là danh sách (QScreen, QImage) - mỗi màn hình một ảnh ở độ phân giải thật (pixel vật lý).
"""

import os
import uuid
from urllib.parse import unquote, urlparse

from PyQt6.QtCore import QObject, QRect, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
from PyQt6.QtGui import QGuiApplication, QImage

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"

# Lệnh người dùng tự chạy (một lần) để cấp quyền chụp màn hình cho Snagit trên GNOME
PERMISSION_COMMAND = (
    "gdbus call --session --dest org.freedesktop.impl.portal.PermissionStore "
    "--object-path /org/freedesktop/impl/portal/PermissionStore "
    "--method org.freedesktop.impl.portal.PermissionStore.SetPermission "
    "screenshot true screenshot snagit \"['yes']\""
)


def is_wayland() -> bool:
    return QGuiApplication.platformName().startswith("wayland")


def virtual_geometry() -> QRect:
    rect = QRect()
    for screen in QGuiApplication.screens():
        rect = rect.united(screen.geometry())
    return rect


def split_by_screen(image: QImage):
    """Cắt ảnh toàn desktop thành ảnh của từng màn hình."""
    virt = virtual_geometry()
    scale = image.width() / max(1, virt.width())
    result = []
    for screen in QGuiApplication.screens():
        g = screen.geometry().translated(-virt.topLeft())
        crop = QRect(round(g.x() * scale), round(g.y() * scale),
                     round(g.width() * scale), round(g.height() * scale))
        result.append((screen, image.copy(crop)))
    return result


class ScreenGrabber(QObject):
    finished = pyqtSignal(list)  # list[(QScreen, QImage)]
    failed = pyqtSignal(str)
    permission_denied = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bus = QDBusConnection.sessionBus()
        self._request_path = None
        self._timeout = QTimer(self, singleShot=True, interval=15000)
        self._timeout.timeout.connect(lambda: self._fail("Hết thời gian chờ phản hồi từ xdg-desktop-portal."))

    def grab(self):
        if is_wayland():
            self._grab_portal()
        else:
            # Chờ một nhịp để các cửa sổ của ứng dụng (nếu có) kịp ẩn đi
            QTimer.singleShot(50, self._grab_x11)

    # ---------------- X11 ----------------
    def _grab_x11(self):
        shots = []
        for screen in QGuiApplication.screens():
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                self.failed.emit(f"Không chụp được màn hình {screen.name()}.")
                return
            shots.append((screen, pixmap.toImage()))
        self.finished.emit(shots)

    # ---------------- Wayland / Portal ----------------
    def _grab_portal(self):
        if not self._bus.isConnected():
            self.failed.emit("Không kết nối được D-Bus phiên làm việc.")
            return
        token = "snagit_" + uuid.uuid4().hex
        sender = self._bus.baseService().lstrip(":").replace(".", "_")
        self._request_path = f"{PORTAL_PATH}/request/{sender}/{token}"
        # Đăng ký nhận tín hiệu trước khi gọi để tránh mất phản hồi
        self._bus.connect(PORTAL_SERVICE, self._request_path, "org.freedesktop.portal.Request",
                          "Response", self._on_response)
        iface = QDBusInterface(PORTAL_SERVICE, PORTAL_PATH, "org.freedesktop.portal.Screenshot", self._bus)
        reply = iface.call("Screenshot", "", {"handle_token": token, "interactive": False})
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            self._disconnect()
            self.failed.emit(f"Portal báo lỗi: {reply.errorMessage()}")
            return
        handle = reply.arguments()[0] if reply.arguments() else None
        if handle and str(handle) != self._request_path:
            # Portal cũ có thể trả về đường dẫn khác - chuyển đăng ký sang đường dẫn đó
            self._disconnect()
            self._request_path = str(handle)
            self._bus.connect(PORTAL_SERVICE, self._request_path, "org.freedesktop.portal.Request",
                              "Response", self._on_response)
        self._timeout.start()

    def _disconnect(self):
        if self._request_path:
            self._bus.disconnect(PORTAL_SERVICE, self._request_path, "org.freedesktop.portal.Request",
                                 "Response", self._on_response)
            self._request_path = None

    def _fail(self, message):
        self._disconnect()
        self.failed.emit(message)

    @pyqtSlot(QDBusMessage)
    def _on_response(self, msg: QDBusMessage):
        self._timeout.stop()
        self._disconnect()
        args = msg.arguments()
        code = args[0] if args else 2
        results = args[1] if len(args) > 1 else {}
        if code == 2:
            # GNOME từ chối chụp không tương tác khi ứng dụng chưa được cấp quyền
            self.permission_denied.emit()
            return
        if code != 0:
            self.failed.emit("Yêu cầu chụp màn hình bị từ chối hoặc bị hủy.")
            return
        uri = results.get("uri", "")
        path = unquote(urlparse(uri).path)
        image = QImage(path)
        # Portal tự ghi file vào ~/Pictures - xóa đi vì ta tự quản lý việc lưu
        try:
            os.remove(path)
        except OSError:
            pass
        if image.isNull():
            self.failed.emit(f"Không đọc được ảnh chụp: {uri}")
            return
        self.finished.emit(split_by_screen(image))
