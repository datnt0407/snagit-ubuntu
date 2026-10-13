# CLAUDE.md - Hướng dẫn Phát triển Ứng dụng Chụp màn hình cho Ubuntu 26.04 LTS

## 1. Tổng quan Dự án
Phát triển một ứng dụng chụp màn hình native dành cho hệ điều hành **Ubuntu 26.04 LTS** (hỗ trợ môi trường Wayland và X11). Ứng dụng cung cấp trải nghiệm chụp màn hình nhanh chóng, linh hoạt và tích hợp trình chỉnh sửa ảnh mạnh mẽ ngay sau khi chụp.

---

## 2. Các Tính năng Chính

1. **Chụp màn hình bằng Phím tắt tùy chỉnh (Custom Hotkeys):**
   - Hỗ trợ thiết lập và lắng nghe phím tắt toàn hệ thống (Global Shortcuts).
   - Mặc định sử dụng phím tắt (ví dụ: `Ctrl + Shift + A` hoặc `PrintScreen`).

2. **Chọn vùng chụp linh hoạt (Screen Selection):**
   - Ngay khi bấm phím tắt, hiển thị lớp phủ (overlay) mờ trên toàn màn hình.
   - Cho phép người dùng kéo thả để **chọn vùng tùy chỉnh** hoặc click để **chụp toàn màn hình**.
   - Hiển thị kích thước vùng chọn (chiều rộng x chiều cao).

3. **Giao diện Chỉnh sửa sau khi chụp (Post-capture Editor):**
   - Tự động chuyển hình ảnh vừa chụp vào cửa sổ chỉnh sửa trực quan.
   - Giao diện tối giản, phản hồi nhanh.

4. **Bộ công cụ Chỉnh sửa tối thiểu (Editing Tools):**
   - **Văn bản (Text/Notes):** Thêm ghi chú chữ trên ảnh với các tùy chọn phông chữ và màu sắc.
   - **Đoạn thẳng (Line):** Vẽ các đường thẳng mượt mà.
   - **Mũi tên (Arrow):** Vẽ mũi tên chỉ dẫn đến vùng nội dung cần chú ý.
   - **Hình tròn/Hình elip (Circle/Ellipse):** Khoanh vùng nội dung dạng đường cong.
   - **Hình chữ nhật (Rectangle):** Khoanh nội dung dạng ô vuông/chữ nhật.
   - **Quản lý chỉnh sửa (Undo/Redo/Delete):** Hoàn tác (`Ctrl + Z`), làm lại (`Ctrl + Y`) hoặc xóa các nét vẽ/đối tượng vừa chỉnh sửa.
   - **Chọn màu sắc & Độ dày nét vẽ:** Cho phép chọn bảng màu cơ bản và điều chỉnh nét vẽ (stroke size).

5. **Xuất kết quả & Lưu tự động (Auto Export & Save):**
   - **Clipboard:** Tự động chép ảnh hoàn
   - **Lưu thư mục:** Tự động lưu tệp tin ảnh (định dạng PNG/JPG) vào thư mục chỉ định (ví dụ: `~/Pictures/Screenshots/`).
   - Định dạng tên file tự động theo thời gian: `Screenshot_YYYYMMDD_HHMMSS.png`.

---

## 3. Kiến trúc & Công nghệ Đề xuất

- **Ngôn ngữ:** Python 3.12+ / C++ / Rust
- **GUI Framework:** PyQt6 / PySide6 hoặc GTK4 (khuyến nghị PyQt6/PySide6 nhờ khả năng thao tác trên QGraphicsScene/Canvas mượt mà).
- **Giao thức hiển thị:** Hỗ trợ cả **Wayland** (thông qua gdbus / xdg-desktop-portal) và **X11** trên Ubuntu 26.04.
- **Thư viện xử lý ảnh:** Pillow (PIL) hoặc OpenCV / QImage.