"""Điểm vào khi đóng gói bằng PyInstaller thành một tệp .exe duy nhất.

``start.bat`` gọi ``python -m uvicorn app.main:app --host 127.0.0.1 --port 8000``.
Tệp .exe đóng gói không có cờ ``-m``, nên ở đây gọi thẳng ``uvicorn.run()`` bằng
Python với đúng tham số đó — hành vi hai cách chạy giống hệt nhau, kể cả banner
in ra cửa sổ dòng lệnh và việc tự mở trình duyệt (xem ``vong_doi()`` trong
``app/main.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    # Cho phép gọi trực tiếp `python packaging/khoi_dong.py` khi chạy từ mã
    # nguồn (ví dụ để thử trước khi đóng gói) mà không cần cài package `app`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn

from app.main import app, cong_dang_chay


def main() -> None:
    # dùng chung cong_dang_chay() với app/main.py để banner khởi động (in ra
    # địa chỉ kèm token) và cổng thật sự lắng nghe luôn khớp nhau — kể cả khi
    # đặt biến môi trường UVICORN_PORT để tránh cổng 8000 bị chiếm.
    uvicorn.run(app, host="127.0.0.1", port=cong_dang_chay(), log_level="warning")


if __name__ == "__main__":
    main()
