"""Điểm vào chương trình.

    python3 -m snagit              # khởi động tiến trình nền (icon khay)
    python3 -m snagit --capture    # yêu cầu chụp màn hình (dùng cho phím tắt)
    python3 -m snagit --settings   # mở cửa sổ cài đặt
    python3 -m snagit --quit       # thoát tiến trình nền

Phần gửi lệnh không import Qt để phím tắt phản hồi nhanh nhất có thể.
"""

import argparse
import os
import socket
import sys


def socket_path() -> str:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/snagit-{os.getuid()}"
    os.makedirs(runtime, exist_ok=True)
    return os.path.join(runtime, "snagit.sock")


def send_command(command: str) -> bool:
    """Gửi lệnh tới tiến trình nền đang chạy. Trả về False nếu chưa có tiến trình."""
    token = os.environ.get("XDG_ACTIVATION_TOKEN") or os.environ.get("DESKTOP_STARTUP_ID") or ""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect(socket_path())
            sock.sendall(f"{command}\t{token}\n".encode())
        return True
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(prog="snagit", description="Ứng dụng chụp màn hình")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--capture", action="store_true", help="chụp màn hình ngay")
    group.add_argument("--settings", action="store_true", help="mở cửa sổ cài đặt")
    group.add_argument("--quit", action="store_true", help="thoát tiến trình nền")
    args = parser.parse_args()

    command = "capture" if args.capture else "settings" if args.settings else "quit" if args.quit else "show"
    if send_command(command):
        return 0
    if command == "quit":
        return 0

    from snagit.app import run
    return run(initial_command=None if command == "show" else command)


if __name__ == "__main__":
    sys.exit(main())
