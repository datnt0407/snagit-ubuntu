"""Xuất ảnh: chép vào clipboard và lưu file tự động."""

import os
from datetime import datetime

from PyQt6.QtGui import QGuiApplication, QImage


def unique_path(directory: str, ext: str, now: datetime | None = None) -> str:
    """Screenshot_YYYYMMDD_HHMMSS.ext, thêm hậu tố _1, _2... nếu đã tồn tại."""
    base = (now or datetime.now()).strftime("Screenshot_%Y%m%d_%H%M%S")
    path = os.path.join(directory, f"{base}.{ext}")
    n = 1
    while os.path.exists(path):
        path = os.path.join(directory, f"{base}_{n}.{ext}")
        n += 1
    return path


def save_image(image: QImage, path: str, jpg_quality: int = 90) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        # JPG không có kênh trong suốt
        return image.convertToFormat(QImage.Format.Format_RGB32).save(path, "JPG", jpg_quality)
    return image.save(path, "PNG")


def copy_to_clipboard(image: QImage):
    QGuiApplication.clipboard().setImage(image)


def export_image(image: QImage, settings) -> tuple[str | None, list[str]]:
    """Trả về (đường dẫn file đã lưu hoặc None, danh sách lỗi)."""
    errors = []
    saved = None
    if settings.copy_clipboard:
        copy_to_clipboard(image)
    if settings.save_file:
        directory = os.path.expanduser(settings.save_dir)
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            errors.append(f"Không tạo được thư mục {directory}: {exc.strerror}")
        else:
            ext = "jpg" if settings.image_format == "jpg" else "png"
            path = unique_path(directory, ext)
            if save_image(image, path, settings.jpg_quality):
                saved = path
            else:
                errors.append(f"Không lưu được ảnh vào {path}")
    return saved, errors
