"""Dựng biểu tượng .ico màu đỏ cho bản đóng gói, từ ``app/static/img/meo-may.svg``.

Chạy: ``..\\.venv\\Scripts\\python.exe tao_icon.py`` (từ trong thư mục ``packaging``)

SVG gốc dùng ``fill="currentColor"`` để đổi màu qua CSS trên giao diện web. Tệp
.ico không có CSS, nên ở đây thay thẳng ``currentColor`` bằng một mã màu đỏ cụ
thể, rồi nhờ Chrome/Edge chạy ``--headless`` chụp lại thành PNG nền trong suốt
độ phân giải cao — cùng kỹ thuật ``scripts/chup_anh.py`` đã dùng để chụp ảnh tài
liệu, nên không cần cài thêm thư viện vẽ SVG (những thư viện đó thường đòi thư
viện hệ thống Cairo, không có sẵn trên Windows).

Cuối cùng Pillow đóng gói PNG độ phân giải cao đó thành .ico nhiều cỡ — Windows
tự chọn cỡ phù hợp cho từng chỗ hiển thị (taskbar, Explorer, tiêu đề cửa sổ).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image

GOC = Path(__file__).resolve().parents[1]
SVG_GOC = GOC / "app" / "static" / "img" / "meo-may.svg"
THU_MUC_NAY = Path(__file__).resolve().parent
ICO_DICH = THU_MUC_NAY / "icon.ico"

MAU_DO = "#DC2626"
DO_PHAN_GIAI = 512
CAC_CO = (16, 24, 32, 48, 64, 128, 256)

TRINH_DUYET = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def _tim_trinh_duyet() -> str:
    for duong_dan in TRINH_DUYET:
        if Path(duong_dan).is_file():
            return duong_dan
    raise SystemExit(
        "Không tìm thấy Chrome hoặc Edge trên máy này — cần một trong hai để "
        "chụp SVG thành PNG."
    )


def main() -> None:
    svg_do = SVG_GOC.read_text(encoding="utf-8").replace("currentColor", MAU_DO)
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>html,body{{margin:0;padding:0;background:transparent}}"
        f"svg{{display:block;width:{DO_PHAN_GIAI}px;height:{DO_PHAN_GIAI}px}}</style>"
        f"</head><body>{svg_do}</body></html>"
    )
    tep_html = THU_MUC_NAY / "_icon_tam.html"
    tep_png = THU_MUC_NAY / "_icon_tam.png"
    tep_html.write_text(html, encoding="utf-8")
    try:
        lenh = [
            _tim_trinh_duyet(),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--default-background-color=00000000",
            f"--window-size={DO_PHAN_GIAI},{DO_PHAN_GIAI}",
            "--virtual-time-budget=5000",
            f"--screenshot={tep_png}",
            tep_html.as_uri(),
        ]
        ket_qua = subprocess.run(lenh, capture_output=True, timeout=60)
        if not tep_png.is_file():
            raise SystemExit(
                "Chụp ảnh không ra tệp. stderr trình duyệt:\n"
                + ket_qua.stderr.decode(errors="replace")
            )
        anh = Image.open(tep_png).convert("RGBA")
        anh.save(ICO_DICH, format="ICO", sizes=[(c, c) for c in CAC_CO])
    finally:
        tep_html.unlink(missing_ok=True)
        tep_png.unlink(missing_ok=True)
    print(f"Đã ghi {ICO_DICH} ({ICO_DICH.stat().st_size} byte)")


if __name__ == "__main__":
    main()
