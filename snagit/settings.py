"""Lưu trữ cài đặt (QSettings -> ~/.config/snagit/snagit.conf)."""

import os

from PyQt6.QtCore import QSettings, QStandardPaths

DEFAULT_HOTKEY = "Ctrl+Shift+A"


def default_save_dir() -> str:
    pictures = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
    return os.path.join(pictures or os.path.expanduser("~/Pictures"), "Screenshots")


class Settings:
    def __init__(self):
        self._s = QSettings("snagit", "snagit")

    def _get(self, key, default, type_):
        return self._s.value(key, default, type=type_)

    def _set(self, key, value):
        self._s.setValue(key, value)
        self._s.sync()

    @property
    def save_dir(self) -> str:
        return self._get("export/save_dir", default_save_dir(), str)

    @save_dir.setter
    def save_dir(self, v: str):
        self._set("export/save_dir", v)

    @property
    def image_format(self) -> str:
        return self._get("export/format", "png", str)

    @image_format.setter
    def image_format(self, v: str):
        self._set("export/format", v)

    @property
    def jpg_quality(self) -> int:
        return self._get("export/jpg_quality", 90, int)

    @jpg_quality.setter
    def jpg_quality(self, v: int):
        self._set("export/jpg_quality", v)

    @property
    def save_file(self) -> bool:
        return self._get("export/save_file", True, bool)

    @save_file.setter
    def save_file(self, v: bool):
        self._set("export/save_file", v)

    @property
    def copy_clipboard(self) -> bool:
        return self._get("export/copy_clipboard", True, bool)

    @copy_clipboard.setter
    def copy_clipboard(self, v: bool):
        self._set("export/copy_clipboard", v)

    @property
    def hotkey(self) -> str:
        """Phím tắt theo định dạng QKeySequence PortableText, ví dụ 'Ctrl+Shift+A'."""
        return self._get("general/hotkey", DEFAULT_HOTKEY, str)

    @hotkey.setter
    def hotkey(self, v: str):
        self._set("general/hotkey", v)

    @property
    def autostart(self) -> bool:
        return self._get("general/autostart", True, bool)

    @autostart.setter
    def autostart(self, v: bool):
        self._set("general/autostart", v)

    @property
    def first_run_done(self) -> bool:
        return self._get("general/first_run_done", False, bool)

    @first_run_done.setter
    def first_run_done(self, v: bool):
        self._set("general/first_run_done", v)

    @property
    def gnome_print_backup(self) -> str:
        """Giá trị gốc của phím chụp màn hình GNOME, lưu lại khi ta chiếm phím Print."""
        return self._get("gnome/print_backup", "", str)

    @gnome_print_backup.setter
    def gnome_print_backup(self, v: str):
        self._set("gnome/print_backup", v)

    # Trạng thái trình chỉnh sửa (màu, nét, phông) được ghi nhớ giữa các lần chụp
    def editor_value(self, key, default, type_):
        return self._get(f"editor/{key}", default, type_)

    def set_editor_value(self, key, value):
        self._set(f"editor/{key}", value)
