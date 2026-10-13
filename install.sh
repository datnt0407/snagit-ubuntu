#!/bin/sh
# Cài đặt Snagit cho người dùng hiện tại (không cần sudo).
set -e

PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/snagit"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

if [ "$1" = "--uninstall" ]; then
    echo "Gỡ cài đặt Snagit..."
    "$LAUNCHER" --quit 2>/dev/null || true
    PYTHONPATH="$PROJECT_DIR" python3 -c "
from PyQt6.QtCore import QCoreApplication
from snagit import hotkey
from snagit.settings import Settings
app = QCoreApplication([])
s = Settings()
hotkey.unregister()
hotkey.restore_print_key(s)
hotkey.set_autostart(False)
s.first_run_done = False
" || true
    rm -f "$LAUNCHER" "$APPS_DIR/snagit.desktop" "$ICON_DIR/snagit.svg"
    echo "Đã gỡ. (Cài đặt cá nhân vẫn còn trong ~/.config/snagit/)"
    exit 0
fi

echo "Kiểm tra phụ thuộc..."
if ! python3 -c "import PyQt6.QtWidgets, PyQt6.QtDBus, PyQt6.QtNetwork" 2>/dev/null; then
    echo "Thiếu PyQt6. Hãy chạy: sudo apt install python3-pyqt6"
    exit 1
fi

echo "Tạo lệnh $LAUNCHER"
mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"
cat > "$LAUNCHER" <<EOF
#!/bin/sh
export PYTHONPATH="$PROJECT_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec /usr/bin/python3 -m snagit "\$@"
EOF
chmod +x "$LAUNCHER"

echo "Cài biểu tượng và lối tắt ứng dụng"
cp "$PROJECT_DIR/snagit/resources/snagit.svg" "$ICON_DIR/snagit.svg"
sed "s|@LAUNCHER@|$LAUNCHER|g" "$PROJECT_DIR/snagit.desktop" > "$APPS_DIR/snagit.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Khởi động lại Snagit"
"$LAUNCHER" --quit 2>/dev/null || true
sleep 1
setsid "$LAUNCHER" >/dev/null 2>&1 < /dev/null &

echo ""
echo "Hoàn tất! Snagit đang chạy ở khay hệ thống."
echo "  - Phím tắt mặc định: Ctrl+Shift+A (đổi trong menu khay › Cài đặt)"
echo "  - Gỡ cài đặt: $0 --uninstall"
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    echo ""
    echo "Lưu ý (Wayland): nếu chưa cấp quyền chụp màn hình cho Snagit, chạy lệnh sau một lần:"
    echo "  gdbus call --session --dest org.freedesktop.impl.portal.PermissionStore \\"
    echo "    --object-path /org/freedesktop/impl/portal/PermissionStore \\"
    echo "    --method org.freedesktop.impl.portal.PermissionStore.SetPermission \\"
    echo "    screenshot true screenshot snagit \"['yes']\""
fi
