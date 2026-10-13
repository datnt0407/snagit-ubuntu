"""Tích hợp hệ thống GNOME: phím tắt toàn cục (Custom Shortcuts) và tự khởi động.

Trên Wayland ứng dụng không thể tự bắt phím tắt toàn hệ thống, nên ta đăng ký một
"Custom Shortcut" của GNOME chạy lệnh `snagit --capture`. Cách này dùng được cả trên X11.
"""

import ast
import os
import shlex
import shutil
import subprocess
import sys

MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA = MEDIA_KEYS + ".custom-keybinding"
BINDING_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/snagit/"
SHELL_KEYS = "org.gnome.shell.keybindings"
SCREENSHOT_UI_KEY = "show-screenshot-ui"

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.expanduser("~/.local/bin/snagit")
AUTOSTART_FILE = os.path.expanduser("~/.config/autostart/snagit.desktop")

# Tên phím Qt (PortableText) -> tên phím GTK/GNOME
_KEY_NAMES = {
    "Print": "Print", "Esc": "Escape", "Space": "space", "Tab": "Tab", "Backspace": "BackSpace",
    "Return": "Return", "Enter": "KP_Enter", "Ins": "Insert", "Del": "Delete", "Home": "Home",
    "End": "End", "PgUp": "Page_Up", "PgDown": "Page_Down", "Left": "Left", "Right": "Right",
    "Up": "Up", "Down": "Down", "Pause": "Pause", "ScrollLock": "Scroll_Lock",
}
_MODIFIERS = {"Ctrl": "<Control>", "Shift": "<Shift>", "Alt": "<Alt>", "Meta": "<Super>"}


def gsettings_available() -> bool:
    return shutil.which("gsettings") is not None


def _gsettings(*args) -> str:
    result = subprocess.run(["gsettings", *args], capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gsettings lỗi")
    return result.stdout.strip()


def _parse_strv(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("@as"):
        value = value[3:].strip()
    try:
        return list(ast.literal_eval(value))
    except (ValueError, SyntaxError):
        return []


def qt_to_gnome(sequence: str) -> str:
    """'Ctrl+Shift+A' -> '<Control><Shift>a', 'Print' -> 'Print'."""
    if not sequence:
        return ""
    sequence = sequence.split(",")[0].strip()  # chỉ dùng tổ hợp đầu tiên
    parts = sequence.split("+")
    # Trường hợp phím chính là dấu '+' (vd: 'Ctrl++')
    if sequence.endswith("++"):
        parts = parts[:-2] + ["+"]
    *mods, key = parts
    accel = "".join(_MODIFIERS.get(m, "") for m in mods)
    if key in _KEY_NAMES:
        name = _KEY_NAMES[key]
    elif len(key) == 1:
        name = key.lower() if key.isalpha() else key
    else:
        name = key  # F1..F12 và các tên giống nhau
    return accel + name


def launch_command(*args: str) -> list[str]:
    """Lệnh để chạy Snagit (ưu tiên launcher do install.sh tạo)."""
    if os.path.isfile(LAUNCHER) and os.access(LAUNCHER, os.X_OK):
        return [LAUNCHER, *args]
    return ["env", f"PYTHONPATH={PROJECT_DIR}", sys.executable, "-m", "snagit", *args]


def register(sequence: str):
    """Đăng ký/cập nhật phím tắt GNOME. Ném RuntimeError nếu thất bại."""
    accel = qt_to_gnome(sequence)
    if not accel:
        unregister()
        return
    paths = _parse_strv(_gsettings("get", MEDIA_KEYS, "custom-keybindings"))
    if BINDING_PATH not in paths:
        paths.append(BINDING_PATH)
        _gsettings("set", MEDIA_KEYS, "custom-keybindings", str(paths))
    schema = f"{CUSTOM_SCHEMA}:{BINDING_PATH}"
    _gsettings("set", schema, "name", "Snagit - Chụp màn hình")
    _gsettings("set", schema, "command", shlex.join(launch_command("--capture")))
    _gsettings("set", schema, "binding", accel)


def refresh_command():
    """Nếu phím tắt đã được đăng ký, cập nhật lại lệnh chạy (vd: sau khi cài launcher)."""
    paths = _parse_strv(_gsettings("get", MEDIA_KEYS, "custom-keybindings"))
    if BINDING_PATH in paths:
        _gsettings("set", f"{CUSTOM_SCHEMA}:{BINDING_PATH}", "command", shlex.join(launch_command("--capture")))


def unregister():
    paths = _parse_strv(_gsettings("get", MEDIA_KEYS, "custom-keybindings"))
    if BINDING_PATH in paths:
        paths.remove(BINDING_PATH)
        _gsettings("set", MEDIA_KEYS, "custom-keybindings", str(paths))
    schema = f"{CUSTOM_SCHEMA}:{BINDING_PATH}"
    for key in ("name", "command", "binding"):
        try:
            _gsettings("reset", schema, key)
        except RuntimeError:
            pass


def gnome_screenshot_keys() -> list[str]:
    try:
        return _parse_strv(_gsettings("get", SHELL_KEYS, SCREENSHOT_UI_KEY))
    except RuntimeError:
        return []


def take_over_print_key(settings):
    """Gỡ phím Print khỏi công cụ chụp của GNOME (lưu lại giá trị gốc để khôi phục)."""
    keys = gnome_screenshot_keys()
    if "Print" not in keys:
        return
    if not settings.gnome_print_backup:
        settings.gnome_print_backup = str(keys)
    keys = [k for k in keys if k != "Print"]
    _gsettings("set", SHELL_KEYS, SCREENSHOT_UI_KEY, str(keys) if keys else "@as []")


def restore_print_key(settings):
    backup = settings.gnome_print_backup
    if not backup:
        return
    _gsettings("set", SHELL_KEYS, SCREENSHOT_UI_KEY, backup)
    settings.gnome_print_backup = ""


def apply_hotkey(settings, sequence: str):
    if qt_to_gnome(sequence) == "Print":
        take_over_print_key(settings)
    else:
        restore_print_key(settings)
    register(sequence)


# ---------------- Tự khởi động ----------------
def _desktop_exec(args: list[str]) -> str:
    def quote(a):
        if any(c in a for c in ' \t"\'\\$`'):
            return '"' + a.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"'
        return a
    return " ".join(quote(a) for a in args)


def set_autostart(enabled: bool):
    if not enabled:
        if os.path.exists(AUTOSTART_FILE):
            os.remove(AUTOSTART_FILE)
        return
    os.makedirs(os.path.dirname(AUTOSTART_FILE), exist_ok=True)
    with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
        f.write("[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Snagit\n"
                "Comment=Ứng dụng chụp màn hình\n"
                f"Exec={_desktop_exec(launch_command())}\n"
                "Icon=snagit\n"
                "Terminal=false\n"
                "X-GNOME-Autostart-enabled=true\n"
                "X-GNOME-Autostart-Delay=3\n")
