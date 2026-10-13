# Snagit — Ứng dụng chụp màn hình cho Ubuntu 26.04

Chụp màn hình bằng phím tắt, chọn vùng, chú thích (chữ, đoạn thẳng, mũi tên, elip, chữ nhật),
rồi tự động chép vào clipboard và lưu file. Hỗ trợ cả **Wayland** và **X11**.

## Cài đặt

```sh
sudo apt install python3-pyqt6     # phụ thuộc duy nhất
./install.sh                       # cài cho người dùng hiện tại, không cần sudo
```

`install.sh` sẽ:
- tạo lệnh `~/.local/bin/snagit`, lối tắt trong danh sách ứng dụng và biểu tượng;
- khởi động Snagit ở khay hệ thống; lần chạy đầu tự đăng ký phím tắt **Ctrl+Shift+A**
  vào GNOME và bật tự khởi động cùng hệ thống.

### Cấp quyền chụp màn hình (Wayland, làm một lần)

GNOME chỉ cho ứng dụng chụp màn hình không tương tác khi đã được cấp quyền. Chạy lệnh sau một lần:

```sh
gdbus call --session --dest org.freedesktop.impl.portal.PermissionStore \
  --object-path /org/freedesktop/impl/portal/PermissionStore \
  --method org.freedesktop.impl.portal.PermissionStore.SetPermission \
  screenshot true screenshot snagit "['yes']"
```

Nếu chưa cấp quyền, Snagit sẽ hiện hộp thoại hướng dẫn kèm nút sao chép lệnh này.
Thu hồi quyền: *Cài đặt › Ứng dụng › Snagit*, hoặc chạy lại lệnh trên với `"['no']"`.

Gỡ cài đặt: `./install.sh --uninstall` (gỡ phím tắt, tự khởi động, khôi phục phím Print của GNOME).

Chạy trực tiếp không cần cài: `python3 -m snagit` (trong thư mục dự án).

## Sử dụng

| Thao tác | Cách làm |
|---|---|
| Chụp | `Ctrl+Shift+A`, hoặc click icon khay, hoặc `snagit --capture` |
| Chọn vùng | Kéo thả chuột (hiện kích thước W × H) |
| Chụp toàn màn hình | Click một lần (chụp màn hình đang trỏ chuột) |
| Hủy | `Esc` hoặc chuột phải |

### Trình chỉnh sửa

| Công cụ | Phím |
|---|---|
| Chọn / di chuyển (double-click để sửa chữ) | `V` |
| Văn bản | `T` |
| Đoạn thẳng | `L` |
| Mũi tên | `A` |
| Hình tròn / elip | `E` |
| Hình chữ nhật | `R` |

- Giữ `Shift` khi vẽ: đường thẳng bám góc 45°, hình vuông, hình tròn.
- Đổi màu / độ dày / phông khi đang chọn đối tượng sẽ áp dụng cho đối tượng đó.
- `Ctrl+Z` hoàn tác, `Ctrl+Y` làm lại, `Delete` xóa đối tượng đang chọn.
- `Ctrl+lăn chuột` thu phóng, `Ctrl+0` vừa cửa sổ, `Ctrl+1` 100%.
- **Xong** (`Enter` / `Ctrl+S` / đóng cửa sổ): chép ảnh vào clipboard và lưu vào
  `~/Pictures/Screenshots/Screenshot_YYYYMMDD_HHMMSS.png`.
- `Ctrl+Shift+S`: lưu thành file khác. `Esc`: hủy ảnh.

### Cài đặt

Menu khay › **Cài đặt...**: thư mục lưu, định dạng PNG/JPG (chất lượng JPG), bật/tắt lưu file
và chép clipboard, đổi phím tắt (có nút **Dùng PrintScreen**), tự khởi động.

## Kiến trúc

```
Phím tắt GNOME ──> snagit --capture ──(Unix socket)──> tiến trình nền (icon khay)
   ──> chụp (Portal Screenshot trên Wayland / QScreen.grabWindow trên X11)
   ──> lớp phủ chọn vùng ──> trình chỉnh sửa (QGraphicsScene + QUndoStack)
   ──> Xong: clipboard + lưu file
```

| File | Vai trò |
|---|---|
| `snagit/__main__.py` | Điểm vào; gửi lệnh tới tiến trình nền (không import Qt để phản hồi nhanh) |
| `snagit/app.py` | Icon khay, máy chủ IPC, điều phối luồng chụp |
| `snagit/capture.py` | Chụp ảnh qua xdg-desktop-portal / X11 |
| `snagit/overlay.py` | Lớp phủ chọn vùng trên từng màn hình |
| `snagit/editor/` | Trình chỉnh sửa: cửa sổ, công cụ, đối tượng vẽ, lệnh Undo/Redo |
| `snagit/export.py` | Clipboard và lưu file |
| `snagit/hotkey.py` | Phím tắt GNOME (gsettings) và tự khởi động |
| `snagit/settings.py`, `settings_dialog.py` | Lưu trữ và giao diện cài đặt |

## Ghi chú kỹ thuật

- Wayland không cho ứng dụng tự bắt phím tắt toàn cục, nên Snagit đăng ký một *Custom Shortcut*
  của GNOME (xem trong Cài đặt › Bàn phím › Phím tắt tùy chỉnh).
- Ảnh trong clipboard trên Wayland chỉ tồn tại khi ứng dụng còn chạy — vì thế Snagit chạy nền.
- Icon khay cần extension AppIndicator (Ubuntu bật sẵn).
- Cài đặt lưu tại `~/.config/snagit/snagit.conf`.
