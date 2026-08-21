"""Chụp lại toàn bộ ảnh màn hình cho tài liệu hướng dẫn.

Chạy:  .venv\\Scripts\\python.exe scripts\\chup_anh.py

Vì sao phải có script này thay vì chụp tay
------------------------------------------
Giao diện đổi thì ảnh trong hướng dẫn thành ảnh của bản cũ, mà không ai nhận ra
cho tới khi người vận hành làm theo ảnh rồi không tìm thấy nút. Chụp bằng script
thì mỗi lần đổi giao diện chỉ việc chạy lại một lệnh.

Ba việc script phải tự lo
-------------------------
1. **Dữ liệu giả.** Tuyệt đối không chụp dữ liệu thật của cơ quan: ảnh sẽ được
   đẩy lên kho mã nguồn công khai. Script tự dựng 6 đảng viên hư cấu với số căn
   cước bịa, và một đảng bộ hư cấu.
2. **Giữ nguyên cấu hình đang có.** ``app/data/cau_hinh.json`` là cấu hình thật
   của người vận hành. Script sao lưu trước khi chạy và trả lại trong ``finally``.
3. **Chụp được cả phần do JavaScript vẽ.** Bảng lỗi và thanh tiến độ chỉ hiện ra
   sau khi bấm nút, mà Chrome không tự bấm. Script chèn tạm một dòng tự bấm vào
   template, chụp, rồi **trả lại nguyên trạng trong ``finally``** — có kiểm lại
   bằng cách so nội dung tệp trước và sau.
"""

from __future__ import annotations

import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
from openpyxl import Workbook

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))

THU_MUC_ANH = GOC / "docs" / "anh"
THU_MUC_MAU = GOC / "app" / "templates"
TEP_CAU_HINH = GOC / "app" / "data" / "cau_hinh.json"

BE_NGANG, BE_DOC = 1366, 1000

CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

# Đảng bộ hư cấu. Không dùng mã 053 của Viện Nông nghiệp để ảnh không bị hiểu
# nhầm là ảnh chụp hệ thống thật đang chạy.
DANG_BO = "Đảng bộ Trung tâm Thử nghiệm Mẫu"
MA_TINH, MA_CAP_TREN, MA_CO_SO = "38", "168", "900"
CO_SO = f"{MA_TINH}.{MA_CAP_TREN}.{MA_CO_SO}"

NGUOI_MAU = [
    ("NGUYỄN VĂN AN", "001199000111", "Chi bộ Văn phòng", "1990-01-15", "2015-05-19"),
    ("TRẦN THỊ BÌNH", "001199000222", "Chi bộ Văn phòng", "1988-03-02", "2012-09-02"),
    ("LÊ VĂN CƯỜNG", "001199000333", "Chi bộ Văn phòng", "1992-07-21", "2018-02-03"),
    ("PHẠM THỊ DUNG", "001199000444", "Chi bộ Kỹ thuật", "1985-11-30", "2010-11-20"),
    ("HOÀNG VĂN EM", "001199000555", "Chi bộ Kỹ thuật", "1995-04-08", "2020-06-15"),
    ("VŨ THỊ GIANG", "001199000666", "Chi bộ Kỹ thuật", "1991-12-25", "2016-08-19"),
]

# Tệp scan giả: cố ý trộn cả tên đúng, tên thiếu hậu tố, và tên sai hẳn — để ảnh
# chụp bước 4 cho thấy đúng thứ người vận hành sẽ gặp.
TEP_SCAN = [
    "A.ID01.1.1.pdf",
    "A.ID01.2.pdf",
    "A.ID02.1.pdf",
    "A.ID02.2.1.pdf",
    "B.ID04.1.pdf",
    "B.ID05.2.pdf",
    "Ho so dang vien Le Van Cuong.pdf",
    "A.ID99.1.1.pdf",
]

# Trang nào cần bấm nút gì trước khi chụp. Khóa là tên tệp template, giá trị là
# id của nút. Chèn tạm rồi trả lại — xem ghi chú đầu tệp.
TU_BAM = {
    "buoc1.html": "nut-doc",
    "buoc3.html": "nut-kiem",
    "buoc4.html": "nut-quet",
    "buoc5.html": "nut-xem",
    "buoc6.html": "nut-quet",
}

# Hai dấu bọc khối chèn tạm, để gỡ ra lại cho chính xác kể cả khi lần chạy
# trước bị ngắt giữa chừng.
DAU_CHEN = "<!-- CHEN TAM DE CHUP ANH -->"
CUOI_CHEN = "<!-- HET CHEN TAM -->"

# Phải chèn VÀO TRONG khối {% block kich_ban %}. Mẫu con dùng {% extends %}
# nên Jinja bỏ hết những gì nằm ngoài block — nối thêm vào cuối tệp thì đoạn
# này biến mất không một lời báo, và ảnh chụp ra trang chưa bấm nút.
MA_TU_BAM = (
    DAU_CHEN
    + """
<script>
/* scripts/chup_anh.py gỡ khối này ra ngay sau khi chụp xong. */
window.addEventListener('load', () => {
  setTimeout(() => {
    const n = document.getElementById('%s');
    if (n) n.click();
  }, 150);
});
</script>
"""
    + CUOI_CHEN
    + "\n"
)


def tim_chrome() -> str:
    for duong_dan in CHROME:
        if Path(duong_dan).is_file():
            return duong_dan
    raise SystemExit("Không tìm thấy Chrome hoặc Edge để chụp ảnh.")


def cong_trong() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def dung_ds_dangvien(tep: Path) -> None:
    """Dựng DS_DANGVIEN.xlsx giả, đúng các cột app đòi hỏi."""
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "STT", "Họ và tên", "Số thẻ Đảng viên", "Số CCCD", "Ngày sinh",
            "Ngày kết nạp", "Chi bộ đang sinh hoạt", "Chi bộ nơi cư trú",
            "Trạng thái",
        ]
    )
    for i, (ten, cccd, chi_bo, sinh, ket_nap) in enumerate(NGUOI_MAU, 1):
        ws.append([i, ten, f"DCS{i:05d}", cccd, sinh, ket_nap, chi_bo, "", "Đang sinh hoạt"])
    tep.parent.mkdir(parents=True, exist_ok=True)
    wb.save(tep)


def dung_tep_scan(thu_muc: Path) -> None:
    thu_muc.mkdir(parents=True, exist_ok=True)
    for i, ten in enumerate(TEP_SCAN):
        (thu_muc / ten).write_bytes(f"noi dung gia {i}".encode())


def _doc_ra_hang_doi(luong, hang_doi: "queue.Queue[str]") -> None:
    for dong in iter(luong.readline, b""):
        hang_doi.put(dong.decode("utf-8", errors="replace"))
    luong.close()


def doc_token(may_chu: subprocess.Popen, giay: float = 30.0) -> str:
    """Đọc token phiên từ chính dòng app in ra lúc khởi động.

    Không import ``app.main.TOKEN`` trong tiến trình này được: token sinh ngẫu
    nhiên mỗi lần nạp mô-đun, nên bản của script sẽ khác bản của máy chủ và mọi
    lời gọi đều 403. Đọc từ stdout là cách duy nhất không phải mở thêm một cửa
    hậu vào app chỉ để phục vụ việc chụp ảnh.

    Đọc qua luồng riêng chứ không gọi thẳng ``readline()``: máy chủ chưa in gì
    thì ``readline()`` chặn vô hạn, mốc thời gian trong vòng lặp không bao giờ
    được xét tới, và script treo cứng thay vì báo lỗi.
    """
    hang_doi: "queue.Queue[str]" = queue.Queue()
    threading.Thread(
        target=_doc_ra_hang_doi, args=(may_chu.stdout, hang_doi), daemon=True
    ).start()

    het = time.time() + giay
    while time.time() < het:
        try:
            chu = hang_doi.get(timeout=0.5)
        except queue.Empty:
            if may_chu.poll() is not None:
                raise SystemExit("Máy chủ tắt trước khi kịp in địa chỉ.") from None
            continue
        if "?t=" in chu:
            return chu.split("?t=", 1)[1].strip()
    raise SystemExit("Không đọc được token phiên trong thời gian chờ.")


def chen_ma_tu_bam(chu: str, nut: str) -> str:
    """Đặt đoạn tự bấm ngay trước ``{% endblock %}`` cuối cùng của mẫu."""
    dau = "{% endblock %}"
    vi_tri = chu.rfind(dau)
    if vi_tri < 0:
        raise SystemExit("Mẫu không có {% endblock %} để chèn vào.")
    return chu[:vi_tri] + (MA_TU_BAM % nut) + chu[vi_tri:]


def go_ma_chen_tam() -> None:
    """Dọn dấu vết của lần chạy trước bị ngắt giữa chừng.

    Nếu script bị tắt cứng (Ctrl+C, hết giờ) thì khối ``finally`` không chạy và
    dòng tự bấm còn nằm lại trong template. Không dọn thì lần chạy sau chèn
    chồng thêm một lớp nữa, và tệ hơn là app thật cũng tự bấm nút.
    """
    for tep in sorted(THU_MUC_MAU.glob("*.html")):
        chu = tep.read_text(encoding="utf-8")
        if DAU_CHEN not in chu:
            continue
        dau = chu.index(DAU_CHEN)
        cuoi = chu.find(CUOI_CHEN)
        if cuoi < 0:
            raise SystemExit(
                f"{tep.name} có dấu chèn tạm nhưng thiếu dấu kết thúc. "
                "Sửa tay trước khi chạy lại, đừng để script đoán."
            )
        tep.write_text(
            chu[:dau] + chu[cuoi + len(CUOI_CHEN) :].lstrip("\n"),
            encoding="utf-8",
        )
        print(f"  dọn dòng chèn tạm còn sót trong {tep.name}")


def cho_may_chu(dia_chi: str, giay: float = 25.0) -> None:
    het = time.time() + giay
    while time.time() < het:
        try:
            httpx.get(dia_chi, timeout=1.0)
            return
        except httpx.HTTPError:
            time.sleep(0.25)
    raise SystemExit("Máy chủ không lên trong thời gian chờ.")


def chay_het_cac_buoc(khach: httpx.Client, san: Path) -> None:
    """Đưa phiên làm việc đi hết bước 0 → 6 để trang nào cũng có số liệu thật."""
    ds = san / "DS_DANGVIEN.xlsx"
    main = san / "MAIN.xlsx"
    kho = san / "kho"
    scan = san / "scan"
    kho.mkdir(exist_ok=True)
    dung_ds_dangvien(ds)
    dung_tep_scan(scan)

    khach.post(
        "/api/buoc0/luu",
        data={
            "ten_dang_bo": DANG_BO,
            "ten_cap_tren": "Đảng bộ Ủy ban nhân dân tỉnh Thanh Hóa",
            "ma_tinh": MA_TINH,
            "ma_cap_tren": MA_CAP_TREN,
            "ma_co_so": MA_CO_SO,
            "dia_danh": "Thanh Hóa",
        },
    ).raise_for_status()

    bang = khach.post(
        "/api/buoc1/doc_ds",
        data={"duong_dan_ds": str(ds), "duong_dan_main": str(main)},
    ).json()["chi_bo"]
    for i, hang in enumerate(bang, 1):
        hang["ma_to_chuc"] = f"{CO_SO}.000.{i:03d}"
    khach.post(
        "/api/buoc1/nap",
        json={"duong_dan_ds": str(ds), "duong_dan_main": str(main), "chi_bo": bang},
    ).raise_for_status()

    khach.post("/api/buoc2/ghi").raise_for_status()
    khach.post("/api/buoc3/kiem", data={"duong_dan_goc": str(kho)}).raise_for_status()
    khach.post("/api/buoc3/tao").raise_for_status()
    khach.post("/api/buoc4/quet", data={"duong_dan_scan": str(scan)}).raise_for_status()
    khach.post("/api/buoc5/xem").raise_for_status()
    khach.post("/api/buoc5/thuc_thi").raise_for_status()
    khach.post("/api/buoc6/doi_soat").raise_for_status()
    khach.post("/api/buoc6/ghi").raise_for_status()


def chup(chrome: str, dia_chi: str, ra: Path, cao: int = BE_DOC) -> None:
    ra.parent.mkdir(parents=True, exist_ok=True)
    lenh = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--window-size={BE_NGANG},{cao}",
        "--virtual-time-budget=20000",
        f"--screenshot={ra}",
        dia_chi,
    ]
    subprocess.run(lenh, check=False, capture_output=True, timeout=90)
    if not ra.is_file():
        print(f"  ! không chụp được {ra.name}")


def main() -> int:
    chrome = tim_chrome()
    go_ma_chen_tam()
    # Đường dẫn này HIỆN LÊN trong ảnh chụp, mà ảnh sẽ đẩy lên kho công khai.
    # Để trong thư mục dự án thì lộ cây thư mục máy người viết; để trong thư
    # mục tạm thì lộ tên tài khoản Windows. C:\\Users\\Public có trên mọi máy
    # Windows và không nói gì về ai đang dùng.
    san = Path(r"C:\\Users\\Public\\SoHoa_MauChup")
    if san.exists():
        shutil.rmtree(san, ignore_errors=True)
    san.mkdir(parents=True)

    sao_luu = TEP_CAU_HINH.with_suffix(".json.truoc_chup")
    if TEP_CAU_HINH.is_file():
        shutil.copy2(TEP_CAU_HINH, sao_luu)

    goc_mau = {ten: (THU_MUC_MAU / ten).read_text(encoding="utf-8") for ten in TU_BAM}
    cong = cong_trong()
    may_chu = None
    try:
        # Chèn dòng tự bấm TRƯỚC khi máy chủ đọc template.
        for ten, nut in TU_BAM.items():
            tep = THU_MUC_MAU / ten
            tep.write_text(chen_ma_tu_bam(goc_mau[ten], nut), encoding="utf-8")

        # PYTHONUNBUFFERED: stdout của tiến trình con bị gom khối khi nối ống,
        # nên dòng in địa chỉ (kèm token) không tới nơi cho tới khi đầy bộ đệm.
        moi_truong = dict(
            os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1"
        )
        may_chu = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "app.main:app",
                "--host", "127.0.0.1", "--port", str(cong), "--log-level", "warning",
            ],
            cwd=GOC,
            env=moi_truong,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        goc_url = f"http://127.0.0.1:{cong}"
        TOKEN = doc_token(may_chu)
        cho_may_chu(goc_url + "/buoc/0")

        with httpx.Client(
            base_url=goc_url, cookies={"phien_so_hoa": TOKEN}, timeout=60
        ) as k:
            chay_het_cac_buoc(k, san)

        trang = [
            ("buoc0.png", "/buoc/0", 1250),
            ("buoc1.png", "/buoc/1", 1350),
            ("buoc2.png", "/buoc/2", 1250),
            ("buoc3.png", "/buoc/3", 1050),
            ("buoc4_ket_qua.png", "/buoc/4", 1250),
            ("buoc5_ket_qua.png", "/buoc/5", 1150),
            ("buoc6_ket_qua.png", "/buoc/6", 1350),
            ("buoc7.png", "/buoc/7", 1550),
            ("huong_dan.png", "/huong_dan", 1500),
        ]
        for ten, duong_dan, cao in trang:
            print(f"  chụp {ten}")
            chup(chrome, f"{goc_url}{duong_dan}?t={TOKEN}", THU_MUC_ANH / ten, cao)
        return 0
    finally:
        if may_chu is not None:
            may_chu.terminate()
            try:
                may_chu.wait(timeout=10)
            except subprocess.TimeoutExpired:
                may_chu.kill()
        # Trả template về nguyên trạng — kiểm lại chứ không tin là đã trả đúng.
        for ten, chu in goc_mau.items():
            tep = THU_MUC_MAU / ten
            tep.write_text(chu, encoding="utf-8")
            assert tep.read_text(encoding="utf-8") == chu, f"{ten} chưa trả lại được!"
        if sao_luu.is_file():
            shutil.copy2(sao_luu, TEP_CAU_HINH)
            sao_luu.unlink()
        shutil.rmtree(san, ignore_errors=True)
        print("Đã trả lại template và cấu hình về nguyên trạng.")


if __name__ == "__main__":
    raise SystemExit(main())
