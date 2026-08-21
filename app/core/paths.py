"""Xử lý đường dẫn: duyệt thư mục phía máy chủ, chặn thoát thư mục, kiểm MAX_PATH.

Vì sao cần duyệt thư mục phía máy chủ
-------------------------------------
Trình duyệt KHÔNG lấy được đường dẫn thư mục trên máy. Thẻ
``<input type="file" webkitdirectory>`` chỉ tải nội dung tệp lên, không trả về
đường dẫn thật. Đây là ràng buộc bảo mật của trình duyệt, không phải thiếu sót
khi triển khai.

Vì app chạy ngay trên máy của người dùng, máy chủ tự liệt kê được thư mục và
gửi về cho trình duyệt hiển thị. Người dùng bấm chọn như hộp thoại quen thuộc.

Mặt trái: bất kỳ tab trình duyệt nào khác trên cùng máy cũng gọi được endpoint
này. Ba lớp chặn:
  1. uvicorn chỉ lắng nghe 127.0.0.1 (không bao giờ 0.0.0.0)
  2. Mọi lời gọi phải kèm token phiên sinh ngẫu nhiên lúc khởi động
  3. Chỉ trả về TÊN thư mục, không bao giờ trả nội dung tệp
"""

from __future__ import annotations

import json
import os
import string
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePath

__all__ = [
    "GIOI_HAN_WINDOWS",
    "NGUONG_CANH_BAO_GOC",
    "LoiDuongDan",
    "ThongTinNganSach",
    "an_toan_duoi",
    "dam_bao_danh_muc_ton_tai",
    "dang_dong_goi",
    "do_dai_ten_tep_lon_nhat",
    "kiem_tra_thanh_phan",
    "kiem_tra_thu_muc_goc",
    "liet_ke_o_dia",
    "liet_ke_thu_muc_con",
    "ngan_sach_duong_dan_goc",
    "thu_muc_du_lieu",
    "thu_muc_goc_ung_dung",
]

# Giới hạn cổ điển của Windows. Dùng 259 vì còn 1 ký tự kết thúc chuỗi.
GIOI_HAN_WINDOWS = 259

# Ngưỡng app chặn người dùng, để lại biên an toàn so với ngân sách tính được.
# Cây 4 cấp với dữ liệu thật chiếm 59 ký tự, tên tệp dài nhất 104, nên ngân sách
# thật cho thư mục gốc là 259 - 59 - 1 - 104 = 95. Chặn ở 80 để còn 15 ký tự dự
# phòng cho họ tên dài hơn hoặc mã chi bộ phát sinh về sau.
NGUONG_CANH_BAO_GOC = 80

# Tên bị Windows cấm dùng làm tên thư mục, bất kể phần mở rộng.
TEN_CAM_WINDOWS = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

KY_TU_CAM = set('<>:"/\\|?*') | {chr(c) for c in range(32)}

# Bản mặc định đi kèm mã nguồn/bản đóng gói — chỉ dùng làm nguồn chép lần đầu,
# xem dam_bao_danh_muc_ton_tai() bên dưới. Nơi *đọc* danh mục thật khi app chạy
# là TEP_DANH_MUC, định nghĩa sau khi có thu_muc_du_lieu().
_TEP_DANH_MUC_MAC_DINH = Path(__file__).resolve().parents[1] / "data" / "danh_muc_file.json"


# ------------------------------------------------------ thư mục dữ liệu, "nhà"


def dang_dong_goi() -> bool:
    """True khi chạy từ tệp .exe do PyInstaller đóng gói, False khi chạy bằng mã nguồn."""
    return bool(getattr(sys, "frozen", False))


def thu_muc_goc_ung_dung() -> Path:
    """"Nhà" của app: cạnh tệp .exe khi đóng gói, thư mục gốc mã nguồn khi chạy bằng Python."""
    if dang_dong_goi():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def thu_muc_du_lieu() -> Path:
    """Nơi ghi cấu hình, nhật ký, manifest — nguồn duy nhất cho mọi module khác.

    PyInstaller ``--onefile`` giải nén mã nguồn vào một thư mục tạm mỗi lần
    chạy rồi xóa khi thoát (``sys._MEIPASS``). Ghi dữ liệu người dùng vào đó
    thì mất hết ngay khi đóng app, nên bản đóng gói phải ghi cạnh tệp .exe —
    nơi duy nhất sống sót qua các lần chạy — thay vì cạnh mã nguồn đã giải nén.
    """
    if dang_dong_goi():
        return thu_muc_goc_ung_dung() / "data"
    return thu_muc_goc_ung_dung() / "app" / "data"


TEP_DANH_MUC = thu_muc_du_lieu() / "danh_muc_file.json"


def dam_bao_danh_muc_ton_tai() -> None:
    """Bản đóng gói: chép danh mục 104 loại mặc định ra cạnh .exe nếu chưa có.

    Không làm gì khi chạy bằng mã nguồn — ở đó ``TEP_DANH_MUC`` đã trỏ thẳng
    vào tệp thật. Khi đóng gói, tệp mặc định chỉ tồn tại trong thư mục tạm bị
    xóa lúc thoát; chép ra một lần để README vẫn đúng lời hứa "sửa
    ``app/data/danh_muc_file.json`` để đổi danh mục" — sửa xong không bị bản
    đóng gói lần chạy sau ghi đè lại mặc định.
    """
    if not dang_dong_goi() or TEP_DANH_MUC.exists() or not _TEP_DANH_MUC_MAC_DINH.is_file():
        return
    TEP_DANH_MUC.parent.mkdir(parents=True, exist_ok=True)
    TEP_DANH_MUC.write_bytes(_TEP_DANH_MUC_MAC_DINH.read_bytes())


class LoiDuongDan(Exception):
    """Lỗi đường dẫn kèm thông báo tiếng Việt, hiển thị thẳng cho người dùng."""


@dataclass
class ThongTinNganSach:
    duong_dan_goc: str
    do_dai_goc: int
    do_dai_tuong_doi_lon_nhat: int
    do_dai_ten_tep: int
    tong_toi_da: int
    con_lai: int
    dat: bool
    thong_bao: str


# --------------------------------------------------------- ngân sách MAX_PATH


@lru_cache(maxsize=1)
def do_dai_ten_tep_lon_nhat() -> int:
    """Độ dài tên tệp dài nhất có thể sinh ra, tính từ danh mục 104 loại.

    Cấu trúc: ``[3 số].[tên tài liệu].[số thứ tự].[đuôi]``
      3 (mã) + 1 + N (tên dài nhất) + 1 + 3 (số thứ tự tới 999) + 1 + 4 (jpeg)
    """
    try:
        du_lieu = json.loads(TEP_DANH_MUC.read_text(encoding="utf-8"))
        dai_nhat = max(len(m["ten_tep"]) for m in du_lieu["muc"].values())
    except (OSError, KeyError, ValueError):
        dai_nhat = 91  # giá trị đã đo được, dùng khi chưa trích danh mục
    return 3 + 1 + dai_nhat + 1 + 3 + 1 + 4


def ngan_sach_duong_dan_goc(do_dai_tuong_doi_lon_nhat: int) -> int:
    """Số ký tự tối đa mà thư mục gốc được phép chiếm."""
    return GIOI_HAN_WINDOWS - do_dai_tuong_doi_lon_nhat - 1 - do_dai_ten_tep_lon_nhat()


def kiem_tra_thu_muc_goc(
    duong_dan: str | os.PathLike, do_dai_tuong_doi_lon_nhat: int
) -> ThongTinNganSach:
    """Kiểm thư mục gốc có tồn tại, ghi được, và đủ ngắn cho MAX_PATH không.

    ``do_dai_tuong_doi_lon_nhat`` là độ dài lớn nhất của phần
    ``<Unit_Folder>\\<Folder_name>`` — do gọi từ tầng trên truyền vào vì chỉ
    tầng đó mới biết dữ liệu thật.
    """
    if not str(duong_dan).strip():
        raise LoiDuongDan("Chưa chọn thư mục gốc.")

    p = Path(duong_dan).expanduser()
    try:
        p = p.resolve(strict=False)
    except (OSError, RuntimeError) as loi:
        raise LoiDuongDan(f"Đường dẫn không hợp lệ: {duong_dan}") from loi

    if not p.exists():
        raise LoiDuongDan(
            f"Không tìm thấy thư mục:\n{p}\n"
            "Kiểm tra lại đường dẫn, hoặc bấm Duyệt để chọn thư mục có sẵn."
        )
    if not p.is_dir():
        raise LoiDuongDan(f"Đây là tệp, không phải thư mục:\n{p}")
    if not os.access(p, os.W_OK):
        raise LoiDuongDan(
            f"Không có quyền ghi vào thư mục:\n{p}\n"
            "Chọn thư mục khác, hoặc liên hệ quản trị máy để cấp quyền."
        )

    goc = str(p)
    ngan_sach = ngan_sach_duong_dan_goc(do_dai_tuong_doi_lon_nhat)
    tong = (
        len(goc) + 1 + do_dai_tuong_doi_lon_nhat + 1 + do_dai_ten_tep_lon_nhat()
    )
    dat = len(goc) <= min(ngan_sach, NGUONG_CANH_BAO_GOC)

    if dat:
        thong_bao = (
            f"Đường dẫn gốc dài {len(goc)} ký tự, trong ngưỡng cho phép "
            f"({NGUONG_CANH_BAO_GOC}). Đường dẫn tệp dài nhất sẽ là {tong} ký tự."
        )
    else:
        thong_bao = (
            f"Đường dẫn gốc dài {len(goc)} ký tự, vượt ngưỡng {NGUONG_CANH_BAO_GOC}.\n"
            f"Windows giới hạn đường dẫn ở {GIOI_HAN_WINDOWS + 1} ký tự; tên thư mục "
            f"và tên tệp của hồ sơ đảng viên đã chiếm tới "
            f"{do_dai_tuong_doi_lon_nhat + 1 + do_dai_ten_tep_lon_nhat()} ký tự.\n"
            f"Chọn một thư mục gần gốc ổ đĩa hơn, ví dụ D:\\SoHoa\\HSDV"
        )

    return ThongTinNganSach(
        duong_dan_goc=goc,
        do_dai_goc=len(goc),
        do_dai_tuong_doi_lon_nhat=do_dai_tuong_doi_lon_nhat,
        do_dai_ten_tep=do_dai_ten_tep_lon_nhat(),
        tong_toi_da=tong,
        con_lai=ngan_sach - len(goc),
        dat=dat,
        thong_bao=thong_bao,
    )


# ------------------------------------------------------- an toàn thành phần


def kiem_tra_thanh_phan(ten: str) -> str:
    """Kiểm một thành phần đường dẫn (tên thư mục) có an toàn không.

    Trả lại chính tên đó nếu hợp lệ, ném ``LoiDuongDan`` nếu không. Đây là lớp
    phòng thủ chiều sâu: ``pascal_case`` đã lọc chỉ còn chữ và số, nhưng tên thư
    mục vẫn đi qua đây trước khi chạm hệ thống tệp.
    """
    if not ten or not ten.strip():
        raise LoiDuongDan("Tên thư mục rỗng.")
    if ten != ten.strip():
        raise LoiDuongDan(f"Tên thư mục có khoảng trắng thừa ở đầu/cuối: {ten!r}")
    if ten in (".", ".."):
        raise LoiDuongDan(f"Tên thư mục không hợp lệ: {ten!r}")
    if os.sep in ten or (os.altsep and os.altsep in ten):
        raise LoiDuongDan(f"Tên thư mục chứa dấu phân cách đường dẫn: {ten!r}")
    xau = sorted(KY_TU_CAM & set(ten))
    if xau:
        raise LoiDuongDan(f"Tên thư mục chứa ký tự Windows cấm {xau}: {ten!r}")
    if ten.rstrip(". ") != ten:
        raise LoiDuongDan(f"Tên thư mục kết thúc bằng dấu chấm hoặc khoảng trắng: {ten!r}")
    if ten.split(".")[0].upper() in TEN_CAM_WINDOWS:
        raise LoiDuongDan(
            f"{ten!r} trùng tên thiết bị Windows dành riêng — không tạo được thư mục."
        )
    return ten


def an_toan_duoi(goc: Path, con: Path) -> bool:
    """Kiểm ``con`` có thực sự nằm dưới ``goc`` sau khi giải đường dẫn không.

    Chặn mọi mưu toan thoát ra ngoài bằng ``..`` hoặc liên kết tượng trưng.
    """
    try:
        g = Path(goc).resolve(strict=False)
        c = Path(con).resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    return g == c or g in c.parents


# ------------------------------------------------------------ duyệt thư mục


def liet_ke_o_dia() -> list[str]:
    """Liệt kê các ổ đĩa đang gắn (Windows). Trên hệ khác trả về ``/``."""
    if os.name != "nt":
        return ["/"]
    return [f"{c}:\\" for c in string.ascii_uppercase if Path(f"{c}:\\").exists()]


def liet_ke_thu_muc_con(
    duong_dan: str | os.PathLike | None, duoi_tep: frozenset[str] | set[str] | None = None
) -> dict:
    """Liệt kê thư mục con để giao diện dựng hộp thoại chọn thư mục.

    Mặc định chỉ trả về TÊN thư mục, không bao giờ trả tên tệp. Truyền
    ``duoi_tep={".xlsx"}`` khi cần cho người dùng chọn một tệp cụ thể — khi đó
    chỉ những tệp đúng đuôi trong danh sách mới lộ ra, không bao giờ trả nội
    dung tệp.
    """
    if not duong_dan or not str(duong_dan).strip():
        return {
            "hien_tai": None, "cha": None, "o_dia": liet_ke_o_dia(),
            "thu_muc": [], "tep": [],
        }

    p = Path(duong_dan).expanduser()
    try:
        p = p.resolve(strict=False)
    except (OSError, RuntimeError) as loi:
        raise LoiDuongDan(f"Đường dẫn không hợp lệ: {duong_dan}") from loi

    if not p.is_dir():
        raise LoiDuongDan(f"Không tìm thấy thư mục:\n{p}")

    duoi = {d.lower() for d in duoi_tep} if duoi_tep else set()
    con: list[str] = []
    tep: list[str] = []
    try:
        with os.scandir(p) as muc:
            for m in muc:
                try:
                    if m.name.startswith("."):
                        continue
                    if m.is_dir(follow_symlinks=False):
                        con.append(m.name)
                    elif duoi and Path(m.name).suffix.lower() in duoi:
                        tep.append(m.name)
                except OSError:
                    continue  # bỏ qua mục không đọc được quyền
    except PermissionError as loi:
        raise LoiDuongDan(
            f"Không có quyền đọc thư mục:\n{p}\nChọn thư mục khác."
        ) from loi

    cha = None if p == p.parent else str(p.parent)
    return {
        "hien_tai": str(p),
        "cha": cha,
        "o_dia": liet_ke_o_dia(),
        "thu_muc": sorted(con, key=str.casefold),
        "tep": sorted(tep, key=str.casefold),
        "ghi_duoc": os.access(p, os.W_OK),
        "do_dai": len(str(p)),
    }


def ghep(goc: Path, *thanh_phan: str) -> Path:
    """Ghép đường dẫn sau khi kiểm từng thành phần và xác nhận không thoát ra ngoài."""
    for t in thanh_phan:
        kiem_tra_thanh_phan(t)
    dich = Path(goc, *thanh_phan)
    if not an_toan_duoi(goc, dich):
        raise LoiDuongDan(
            f"Đường dẫn đích nằm ngoài thư mục gốc: {PurePath(*thanh_phan)}"
        )
    return dich
