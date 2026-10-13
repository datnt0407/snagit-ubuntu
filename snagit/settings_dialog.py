"""Hộp thoại cài đặt."""

from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                             QHBoxLayout, QKeySequenceEdit, QLabel, QLineEdit, QMessageBox, QPushButton,
                             QSpinBox, QVBoxLayout, QWidget)

from snagit import hotkey, icons
from snagit.settings import DEFAULT_HOTKEY


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Snagit - Cài đặt")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumWidth(520)
        self._settings = settings

        form = QFormLayout()

        # Thư mục lưu
        self.dir_edit = QLineEdit(settings.save_dir)
        browse = QPushButton("Chọn...")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.dir_edit)
        row.addWidget(browse)
        form.addRow("Thư mục lưu ảnh:", _wrap(row))

        # Định dạng
        self.format_combo = QComboBox()
        self.format_combo.addItem("PNG (không mất chất lượng)", "png")
        self.format_combo.addItem("JPG (dung lượng nhỏ)", "jpg")
        self.format_combo.setCurrentIndex(1 if settings.image_format == "jpg" else 0)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(10, 100)
        self.quality_spin.setSuffix(" %")
        self.quality_spin.setValue(settings.jpg_quality)
        self.format_combo.currentIndexChanged.connect(self._update_quality)
        row = QHBoxLayout()
        row.addWidget(self.format_combo, 1)
        row.addWidget(QLabel("Chất lượng JPG:"))
        row.addWidget(self.quality_spin)
        form.addRow("Định dạng:", _wrap(row))

        self.save_check = QCheckBox("Tự động lưu file khi bấm Xong")
        self.save_check.setChecked(settings.save_file)
        self.clip_check = QCheckBox("Tự động chép ảnh vào clipboard khi bấm Xong")
        self.clip_check.setChecked(settings.copy_clipboard)
        form.addRow("", self.save_check)
        form.addRow("", self.clip_check)

        # Phím tắt
        self.key_edit = QKeySequenceEdit(QKeySequence(settings.hotkey))
        self.key_edit.setMaximumSequenceLength(1)
        btn_print = QPushButton("Dùng PrintScreen")
        btn_print.setToolTip("Phím Print bị GNOME giữ nên không bấm trực tiếp vào ô được - dùng nút này")
        btn_print.clicked.connect(lambda: self.key_edit.setKeySequence(QKeySequence("Print")))
        btn_default = QPushButton("Mặc định")
        btn_default.clicked.connect(lambda: self.key_edit.setKeySequence(QKeySequence(DEFAULT_HOTKEY)))
        row = QHBoxLayout()
        row.addWidget(self.key_edit, 1)
        row.addWidget(btn_print)
        row.addWidget(btn_default)
        form.addRow("Phím tắt chụp:", _wrap(row))
        note = QLabel("Phím tắt được đăng ký vào GNOME (Cài đặt › Bàn phím › Phím tắt tùy chỉnh).\n"
                      "Khi chọn PrintScreen, công cụ chụp mặc định của GNOME sẽ được gỡ khỏi phím này.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        form.addRow("", note)

        self.autostart_check = QCheckBox("Tự khởi động cùng hệ thống")
        self.autostart_check.setChecked(settings.autostart)
        form.addRow("", self.autostart_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Lưu")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._update_quality()

    def _update_quality(self):
        self.quality_spin.setEnabled(self.format_combo.currentData() == "jpg")

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu ảnh", self.dir_edit.text())
        if path:
            self.dir_edit.setText(path)

    def _save(self):
        s = self._settings
        s.save_dir = self.dir_edit.text().strip() or s.save_dir
        s.image_format = self.format_combo.currentData()
        s.jpg_quality = self.quality_spin.value()
        s.save_file = self.save_check.isChecked()
        s.copy_clipboard = self.clip_check.isChecked()

        errors = []
        sequence = self.key_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        try:
            hotkey.apply_hotkey(s, sequence)
            s.hotkey = sequence
        except (RuntimeError, OSError) as exc:
            errors.append(f"Không đăng ký được phím tắt: {exc}")
        try:
            hotkey.set_autostart(self.autostart_check.isChecked())
            s.autostart = self.autostart_check.isChecked()
        except OSError as exc:
            errors.append(f"Không cập nhật được tự khởi động: {exc}")
        if errors:
            QMessageBox.warning(self, "Snagit", "\n".join(errors))
        self.accept()


def _wrap(layout) -> QWidget:
    w = QWidget()
    layout.setContentsMargins(0, 0, 0, 0)
    w.setLayout(layout)
    return w
