"""Sinh tên tệp đích theo quy tắc của Kế hoạch số hóa (§5.3 đặc tả chốt).

    [Mã tài liệu 3 số].[Tên tài liệu không dấu].[Số thứ tự].<đuôi gốc>
    065.Ban_tu_kiem_diem_dang_vien_vi_pham.1.pdf

Ba điều dễ làm sai, đã xử lý ở đây
----------------------------------
1. **Đệm đúng 3 chữ số.** `65` ⇒ `065`. Không đệm thì sắp xếp trong File
   Explorer sẽ ra `1, 10, 100, 2` — cán bộ tra tay rất khổ.
2. **Số thứ tự luôn xuất hiện**, kể cả khi loại tài liệu đó chỉ có một tệp.
   Có mặt sẵn thì lần bổ sung sau chỉ việc thêm `.2`, không phải đổi tên tệp cũ.
3. **Đếm tiếp từ tệp đã có trong thư mục đích**, không đếm lại từ 1.
   `RenamePDF_v2.bat` cũ đếm theo thư mục đang đứng nên chạy lần hai là ghi đè
   mất tệp cũ — đây chính là khiếm khuyết `0.DACTA_chitiet.md` đã nêu.

Tên tài liệu lấy từ danh mục 104 loại trích sẵn trong ``app/data``. KHÔNG suy ra
bằng phép biến đổi cơ học từ tên tiếng Việt, vì danh mục dùng các chữ viết tắt
đã thống nhất (QĐ, GCN, NQ, CV, TB, KL, GGT, PB, HHĐ, CTXH, LLVT).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.paths import thu_muc_du_lieu
from app.core.vietnamese import slug_tai_lieu

__all__ = [
    "DUOI_CHO_PHEP",
    "DUOI_KHO_CHINH",
    "KHO_CHO",
    "MA_NHO_NHAT",
    "MA_LON_NHAT",
    "MucTaiLieu",
    "danh_muc",
    "dat_ten",
    "la_kho_chinh",
    "phan_tich_ten_dich",
    "so_lon_nhat_hien_co",
    "ten_tai_lieu",
    "thu_muc_dich",
]

TEP_DANH_MUC = thu_muc_du_lieu() / "danh_muc_file.json"

MA_NHO_NHAT = 1
MA_LON_NHAT = 104

# Thông tư 02/2019/TT-BNV: tài liệu lưu trữ số hóa phải ở dạng PDF. Các đuôi
# khác vẫn nhận vào và vẫn đổi tên đúng chuẩn, nhưng xếp riêng sang kho chờ.
DUOI_KHO_CHINH = (".pdf",)
DUOI_CHO_PHEP = (".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png")
KHO_CHO = "_CHO_CHUYEN_PDF"

# Tên tệp đích: 3 số . tên . số thứ tự . đuôi
MAU_TEN_DICH = re.compile(r"^(\d{3})\.(.+)\.(\d+)\.([^.]+)$")


@dataclass(frozen=True)
class MucTaiLieu:
    ma: int
    ten_day_du: str
    ten_tep: str
    uu_tien: int


@lru_cache(maxsize=1)
def danh_muc() -> dict[int, MucTaiLieu]:
    """Đọc danh mục 104 loại tài liệu. Trả về dict rỗng nếu tệp danh mục hỏng."""
    try:
        du_lieu = json.loads(TEP_DANH_MUC.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    ra: dict[int, MucTaiLieu] = {}
    for khoa, m in du_lieu.get("muc", {}).items():
        try:
            ma = int(khoa)
        except (TypeError, ValueError):
            continue
        ra[ma] = MucTaiLieu(
            ma=ma,
            ten_day_du=str(m.get("ten_day_du", "")),
            ten_tep=str(m.get("ten_tep", "")),
            uu_tien=int(m.get("uu_tien", 0) or 0),
        )
    return ra


def ten_tai_lieu(ma: int) -> str:
    """Tên dùng trong tên tệp cho một mã tài liệu."""
    muc = danh_muc().get(int(ma))
    if muc is None:
        return ""
    return muc.ten_tep or slug_tai_lieu(muc.ten_day_du)


def dat_ten(ma: int, so_thu_tu: int, duoi: str) -> str:
    """``(65, 1, '.pdf')`` ⇒ ``065.Ban_tu_kiem_diem....1.pdf``"""
    duoi = duoi if duoi.startswith(".") else "." + duoi
    return f"{int(ma):03d}.{ten_tai_lieu(ma)}.{int(so_thu_tu)}{duoi.lower()}"


def phan_tich_ten_dich(ten: str) -> tuple[int, str, int, str] | None:
    """Đọc ngược một tên tệp đích thành ``(mã, tên tài liệu, số thứ tự, đuôi)``.

    Dùng để biết trong thư mục đích đã có những số thứ tự nào rồi.
    """
    khop = MAU_TEN_DICH.match(ten)
    if not khop:
        return None
    return int(khop.group(1)), khop.group(2), int(khop.group(3)), "." + khop.group(4)


def la_kho_chinh(duoi: str) -> bool:
    """PDF vào kho chính thức; các đuôi khác nằm ở kho chờ chuyển PDF."""
    return duoi.lower() in DUOI_KHO_CHINH


def thu_muc_dich(thu_muc_dang_vien: Path, duoi: str) -> Path:
    """Chọn giữa thư mục đảng viên và thư mục con ``_CHO_CHUYEN_PDF``."""
    return thu_muc_dang_vien if la_kho_chinh(duoi) else thu_muc_dang_vien / KHO_CHO


def _liet_ke_tep(thu_muc: Path) -> list[str]:
    try:
        with os.scandir(thu_muc) as muc:
            return [m.name for m in muc if m.is_file()]
    except OSError:
        return []


def so_lon_nhat_hien_co(thu_muc_dang_vien: Path, ma: int) -> int:
    """Số thứ tự lớn nhất đang có của một mã tài liệu, tính cả kho chờ.

    Đếm chung hai kho là bắt buộc: khi tệp ở kho chờ được chuyển sang PDF về
    sau, nó phải nhập vào kho chính mà không đụng số của tệp đã có ở đó.
    """
    lon_nhat = 0
    for thu_muc in (thu_muc_dang_vien, thu_muc_dang_vien / KHO_CHO):
        for ten in _liet_ke_tep(thu_muc):
            phan = phan_tich_ten_dich(ten)
            if phan and phan[0] == int(ma):
                lon_nhat = max(lon_nhat, phan[2])
    return lon_nhat
