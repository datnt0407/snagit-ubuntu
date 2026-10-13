"""Tiến trình nền: icon khay hệ thống, nhận lệnh qua socket, điều phối chụp -> chọn vùng -> chỉnh sửa."""

import os
import signal
import sys

from PyQt6.QtCore import QObject, QTimer, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QGuiApplication, QImage, QKeySequence
from PyQt6.QtNetwork import QLocalServer
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from snagit import APP_ID, APP_NAME, __version__, hotkey, icons
from snagit.__main__ import socket_path
from snagit.capture import PERMISSION_COMMAND, ScreenGrabber
from snagit.editor import EditorWindow
from snagit.export import export_image
from snagit.overlay import SelectionSession
from snagit.settings import Settings
from snagit.settings_dialog import SettingsDialog


class SnagitApp(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.settings = Settings()
        self._busy = False
        self._session = None
        self._editors = []
        self._settings_dialog = None

        self.grabber = ScreenGrabber(self)
        self.grabber.finished.connect(self._on_grabbed)
        self.grabber.failed.connect(self._on_capture_failed)
        self.grabber.permission_denied.connect(self._on_permission_denied)

        self._start_server()
        self._build_tray()
        self._first_run()

    # ---------- IPC ----------
    def _start_server(self):
        path = socket_path()
        QLocalServer.removeServer(path)  # dọn socket cũ nếu lần trước bị tắt đột ngột
        self.server = QLocalServer(self)
        if not self.server.listen(path):
            print(f"Không mở được socket {path}: {self.server.errorString()}", file=sys.stderr)
        self.server.newConnection.connect(self._on_connection)

    def _on_connection(self):
        while self.server.hasPendingConnections():
            conn = self.server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: self._read_command(c))
            conn.disconnected.connect(conn.deleteLater)

    def _read_command(self, conn):
        while conn.canReadLine():
            line = bytes(conn.readLine()).decode(errors="replace").strip()
            command, _, token = line.partition("\t")
            self.handle_command(command, token)

    def handle_command(self, command: str, token: str = ""):
        if command == "capture":
            self.capture(token)
        elif command == "settings":
            self.open_settings()
        elif command == "quit":
            self.app.quit()
        elif command == "show":
            self.tray.showMessage(APP_NAME, "Snagit đang chạy. Bấm "
                                  f"{self.settings.hotkey} để chụp màn hình.", icons.app_icon(), 4000)

    # ---------- Khay hệ thống ----------
    def _build_tray(self):
        self.tray = QSystemTrayIcon(icons.app_icon(), self)
        self.tray.setToolTip(f"{APP_NAME} - Chụp màn hình")
        menu = QMenu()
        self.act_capture = QAction(icons.tool_icon("rect"), "Chụp màn hình", menu)
        self.act_capture.triggered.connect(lambda: QTimer.singleShot(300, self.capture))
        menu.addAction(self.act_capture)
        act_folder = QAction(icons.themed("folder-pictures"), "Mở thư mục ảnh", menu)
        act_folder.triggered.connect(self.open_folder)
        menu.addAction(act_folder)
        menu.addSeparator()
        act_settings = QAction(icons.themed("preferences-system"), "Cài đặt...", menu)
        act_settings.triggered.connect(self.open_settings)
        menu.addAction(act_settings)
        act_about = QAction("Giới thiệu", menu)
        act_about.triggered.connect(self.about)
        menu.addAction(act_about)
        menu.addSeparator()
        act_quit = QAction(icons.themed("application-exit"), "Thoát", menu)
        act_quit.triggered.connect(self.app.quit)
        menu.addAction(act_quit)
        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self._update_tray_text()
        self.tray.show()

    def _update_tray_text(self):
        key = QKeySequence(self.settings.hotkey).toString(QKeySequence.SequenceFormat.NativeText)
        self.act_capture.setText(f"Chụp màn hình\t{key}" if key else "Chụp màn hình")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            QTimer.singleShot(200, self.capture)

    def _notify(self, title, message, error=False):
        icon = QSystemTrayIcon.MessageIcon.Warning if error else QSystemTrayIcon.MessageIcon.Information
        if self.tray.isSystemTrayAvailable() and self.tray.supportsMessages():
            self.tray.showMessage(title, message, icon, 5000)
        elif error:
            QMessageBox.warning(None, title, message)

    # ---------- Lần chạy đầu ----------
    def _first_run(self):
        if self.settings.first_run_done:
            try:
                hotkey.refresh_command()
                if self.settings.autostart:
                    hotkey.set_autostart(True)
            except (RuntimeError, OSError):
                pass
            return
        errors = []
        if hotkey.gsettings_available():
            try:
                hotkey.apply_hotkey(self.settings, self.settings.hotkey)
            except (RuntimeError, OSError) as exc:
                errors.append(f"Không đăng ký được phím tắt: {exc}")
        try:
            hotkey.set_autostart(self.settings.autostart)
        except OSError as exc:
            errors.append(f"Không bật được tự khởi động: {exc}")
        self.settings.first_run_done = True
        if errors:
            self._notify(APP_NAME, "\n".join(errors), error=True)
        else:
            self._notify(APP_NAME, f"Đã sẵn sàng! Bấm {self.settings.hotkey} để chụp màn hình.")

    # ---------- Luồng chụp ----------
    def capture(self, token: str = ""):
        if self._busy:
            return
        self._busy = True
        self._token = token
        self.grabber.grab()

    def _on_grabbed(self, shots):
        if self._token:
            # Token kích hoạt từ phím tắt: cho phép lớp phủ nhận focus bàn phím trên Wayland
            os.environ["XDG_ACTIVATION_TOKEN"] = self._token
        self._session = SelectionSession(shots, self)
        self._session.selected.connect(self._on_selected)
        self._session.cancelled.connect(self._end_session)
        self._session.start()

    def _on_selected(self, image: QImage):
        editor = EditorWindow(image, self.settings, self.export)
        self._editors.append(editor)
        editor.destroyed.connect(lambda _=None, e=editor: self._editors.remove(e) if e in self._editors else None)
        editor.show()
        editor.raise_()
        editor.activateWindow()
        self._end_session()

    def _end_session(self):
        os.environ.pop("XDG_ACTIVATION_TOKEN", None)
        if self._session is not None:
            self._session.deleteLater()
            self._session = None
        self._busy = False

    def _on_capture_failed(self, message: str):
        self._busy = False
        self._notify(f"{APP_NAME} - Lỗi chụp màn hình", message, error=True)

    def _on_permission_denied(self):
        self._busy = False
        box = QMessageBox(QMessageBox.Icon.Warning, f"{APP_NAME} - Chưa có quyền chụp màn hình",
                          "GNOME đã chặn Snagit chụp màn hình vì ứng dụng chưa được cấp quyền.\n\n"
                          "Để cấp quyền (chỉ cần làm một lần), mở Terminal và chạy lệnh bên dưới, "
                          "sau đó thử chụp lại. Có thể thu hồi quyền trong Cài đặt › Ứng dụng › Snagit.")
        box.setDetailedText(PERMISSION_COMMAND)
        btn_copy = box.addButton("Sao chép lệnh", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is btn_copy:
            QGuiApplication.clipboard().setText(PERMISSION_COMMAND)
            self._notify(APP_NAME, "Đã sao chép lệnh cấp quyền vào clipboard.")

    def export(self, image: QImage) -> str:
        path, errors = export_image(image, self.settings)
        if errors:
            self._notify(f"{APP_NAME} - Lỗi", "\n".join(errors), error=True)
            return "; ".join(errors)
        parts = []
        if self.settings.copy_clipboard:
            parts.append("Đã chép vào clipboard")
        if path:
            parts.append(f"Đã lưu: {path}")
        message = "\n".join(parts)
        if message:
            self._notify(APP_NAME, message)
        return message

    # ---------- Khác ----------
    def open_folder(self):
        directory = os.path.expanduser(self.settings.save_dir)
        os.makedirs(directory, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(directory))

    def open_settings(self):
        if self._settings_dialog is not None:
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        self._settings_dialog = SettingsDialog(self.settings)
        self._settings_dialog.finished.connect(self._settings_closed)
        self._settings_dialog.show()

    def _settings_closed(self):
        self._settings_dialog.deleteLater()
        self._settings_dialog = None
        self._update_tray_text()

    def about(self):
        QMessageBox.about(None, f"Giới thiệu {APP_NAME}",
                          f"<b>{APP_NAME} {__version__}</b><br>Ứng dụng chụp màn hình cho Ubuntu "
                          "(Wayland &amp; X11).<br><br>Phím tắt hiện tại: "
                          f"<b>{self.settings.hotkey}</b>")


def run(initial_command: str | None = None) -> int:
    QGuiApplication.setDesktopFileName(APP_ID)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(icons.app_icon())
    app.setQuitOnLastWindowClosed(False)
    # Cho phép Ctrl+C trong terminal
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    snagit = SnagitApp(app)
    if initial_command:
        token = os.environ.pop("XDG_ACTIVATION_TOKEN", "")
        QTimer.singleShot(0, lambda: snagit.handle_command(initial_command, token))
    return app.exec()
