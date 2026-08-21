"""Đối soát 104 loại tài liệu và ba mức độ ưu tiên (bước 6).

Đọc thẳng từ **cây thư mục trên đĩa**, không tin vào bộ nhớ của lần chạy trước.
Nhờ vậy đối soát vẫn đúng khi có người chép tay tệp vào kho, và chạy được ngay
sau bước 3 mà không cần bước 5.

Ranh giới "đã có" — chỗ dễ hiểu sai nhất
----------------------------------------
Chỉ tệp **PDF nằm ở kho chính** mới được tính là đã số hóa. Tệp ``.docx``/ảnh
trong ``_CHO_CHUYEN_PDF`` đã đúng tên, đúng chỗ, nhưng chưa đạt chuẩn định dạng
của Thông tư 02/2019/TT-BNV nên vẫn nằm ở cột *chưa có*, đồng thời được liệt kê
riêng ở cột *chờ chuyển PDF*. Báo cáo tách hai dòng đúng như vậy — nói "đã số
hóa 80%" trong khi một phần chưa phải PDF là báo cáo sai sự thật.

Ba mức ưu tiên lấy từ chính danh mục 104 loại (``uu_tien`` 1/2/3), không cắt
theo khoảng số cứng, để danh mục đổi thì đối soát đổi theo.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.mainbook import DongDangVien
from app.core.rename import KHO_CHO, danh_muc, phan_tich_ten_dich
from app.core.tree import duong_dan_tuong_doi
from app.core.vietnamese import LoiMaToChuc

__all__ = [
    "DoiSoatDangVien",
    "KetQuaDoiSoat",
    "TomTatChiBo",
    "TongTheoUuTien",
    "danh_sach_ma_theo_uu_tien",
    "doi_soat",
    "gan_vao_so_cai",
    "tong_so_theo_uu_tien",
]

MUC_UU_TIEN = (1, 2, 3)


def _chi_so(ma: str) -> str:
    """Chỉ giữ chữ số của mã tổ chức đảng, để so khớp không phụ thuộc dấu chấm."""
    return re.sub(r"\D", "", ma or "")


def danh_sach_ma_theo_uu_tien(uu_tien: int) -> list[int]:
    """Các mã tài liệu thuộc một mức ưu tiên, lấy từ danh mục 104 loại."""
    return sorted(m.ma for m in danh_muc().values() if m.uu_tien == uu_tien)


def tong_so_theo_uu_tien() -> dict[int, int]:
    """Mẫu số của từng mức: ƯT1 36 loại, ƯT2 49 loại, ƯT3 19 loại."""
    return {ut: len(danh_sach_ma_theo_uu_tien(ut)) for ut in MUC_UU_TIEN}


@dataclass
class TongTheoUuTien:
    """``x/36`` — đã có bao nhiêu trên tổng số loại của mức đó."""

    co: int = 0
    tong: int = 0

    def __str__(self) -> str:
        return f"{self.co}/{self.tong}"

    @property
    def ti_le(self) -> float:
        return (self.co / self.tong * 100) if self.tong else 0.0


@dataclass
class DoiSoatDangVien:
    id: str
    ho_ten: str
    unit_folder: str
    chi_bo: str
    duong_dan: str = ""
    co_thu_muc: bool = False
    da_co: list[int] = field(default_factory=list)
    cho_chuyen_pdf: list[int] = field(default_factory=list)
    chua_co: list[int] = field(default_factory=list)
    tien_do: dict[int, TongTheoUuTien] = field(default_factory=dict)
    ghi_chu: str = ""

    @property
    def so_tep_da_co(self) -> int:
        return len(self.da_co)


@dataclass
class TomTatChiBo:
    ma_id: str
    ma_to_chuc: str
    ten: str
    so_dang_vien: int = 0
    tien_do: dict[int, TongTheoUuTien] = field(default_factory=dict)
    so_cho_chuyen_pdf: int = 0
    thieu_thu_muc: int = 0


@dataclass
class KetQuaDoiSoat:
    goc: str = ""
    dong: list[DoiSoatDangVien] = field(default_factory=list)
    chi_bo: list[TomTatChiBo] = field(default_factory=list)
    tien_do: dict[int, TongTheoUuTien] = field(default_factory=dict)
    so_cho_chuyen_pdf: int = 0
    thieu_thu_muc: int = 0

    @property
    def so_dang_vien(self) -> int:
        return len(self.dong)

    @property
    def tong_tep_da_co(self) -> int:
        return sum(d.so_tep_da_co for d in self.dong)


def _ma_trong_thu_muc(thu_muc: Path, chi_pdf: bool) -> set[int]:
    """Các mã tài liệu đọc được từ tên tệp trong một thư mục."""
    ra: set[int] = set()
    try:
        with os.scandir(thu_muc) as muc:
            ten_tep = [m.name for m in muc if m.is_file()]
    except OSError:
        return ra
    for ten in ten_tep:
        phan = phan_tich_ten_dich(ten)
        if not phan:
            continue
        ma, _, _, duoi = phan
        if chi_pdf and duoi.lower() != ".pdf":
            continue
        if ma in danh_muc():
            ra.add(ma)
    return ra


def doi_soat(
    goc: str | os.PathLike,
    dong: list[DongDangVien],
    chi_bo: dict[str, tuple[str, str]] | None = None,
) -> KetQuaDoiSoat:
    """Quét cây thư mục, đối chiếu với danh mục 104 loại. Không ghi gì lên đĩa."""
    goc = Path(goc).expanduser().resolve(strict=False)
    tong_ut = tong_so_theo_uu_tien()
    ma_theo_ut = {ut: set(danh_sach_ma_theo_uu_tien(ut)) for ut in MUC_UU_TIEN}
    moi_ma = set(danh_muc())

    kq = KetQuaDoiSoat(goc=str(goc))
    kq.tien_do = {ut: TongTheoUuTien(0, tong_ut[ut] * len(dong)) for ut in MUC_UU_TIEN}

    # Khớp theo CHỮ SỐ của mã tổ chức, không theo chuỗi thô: sổ cái cũ còn ghi
    # mã dạng không dấu chấm (38168053000001) trong khi bảng chi bộ ghi dạng có
    # dấu chấm. So chuỗi thô là trượt sạch, chi bộ nào cũng thành "không rõ mã".
    ten_theo_ma_to_chuc: dict[str, tuple[str, str]] = {}
    for ten, (ma_id, ma_to_chuc) in (chi_bo or {}).items():
        ten_theo_ma_to_chuc[_chi_so(ma_to_chuc)] = (ma_id, ten)

    theo_chi_bo: dict[str, TomTatChiBo] = {}

    for d in dong:
        ma_id, ten_chi_bo = ten_theo_ma_to_chuc.get(
            _chi_so(d.unit_folder), ("", d.chi_bo_dang_sinh_hoat)
        )
        muc = DoiSoatDangVien(
            id=d.id,
            ho_ten=d.name,
            unit_folder=d.unit_folder,
            chi_bo=ten_chi_bo or d.chi_bo_dang_sinh_hoat,
        )

        try:
            thu_muc = goc / duong_dan_tuong_doi(d) if d.unit_folder else None
        except LoiMaToChuc:
            thu_muc = None

        if thu_muc is None:
            muc.ghi_chu = (
                "Chưa xác định được thư mục vì thiếu mã tổ chức đảng của chi bộ."
            )
        else:
            muc.duong_dan = str(thu_muc)
            muc.co_thu_muc = thu_muc.is_dir()
            if not muc.co_thu_muc:
                muc.ghi_chu = "Chưa có thư mục trên đĩa. Chạy lại bước 3."

        if muc.co_thu_muc:
            duong_dan = Path(muc.duong_dan)
            muc.da_co = sorted(_ma_trong_thu_muc(duong_dan, chi_pdf=True))
            muc.cho_chuyen_pdf = sorted(
                _ma_trong_thu_muc(duong_dan / KHO_CHO, chi_pdf=False)
            )
        muc.chua_co = sorted(moi_ma - set(muc.da_co))
        muc.tien_do = {
            ut: TongTheoUuTien(len(set(muc.da_co) & ma_theo_ut[ut]), tong_ut[ut])
            for ut in MUC_UU_TIEN
        }

        tom_tat = theo_chi_bo.setdefault(
            d.unit_folder,
            TomTatChiBo(
                ma_id=ma_id,
                ma_to_chuc=d.unit_folder,
                ten=muc.chi_bo,
                tien_do={ut: TongTheoUuTien(0, 0) for ut in MUC_UU_TIEN},
            ),
        )
        tom_tat.so_dang_vien += 1
        tom_tat.so_cho_chuyen_pdf += len(muc.cho_chuyen_pdf)
        tom_tat.thieu_thu_muc += 0 if muc.co_thu_muc else 1
        for ut in MUC_UU_TIEN:
            tom_tat.tien_do[ut].co += muc.tien_do[ut].co
            tom_tat.tien_do[ut].tong += tong_ut[ut]
            kq.tien_do[ut].co += muc.tien_do[ut].co

        kq.so_cho_chuyen_pdf += len(muc.cho_chuyen_pdf)
        kq.thieu_thu_muc += 0 if muc.co_thu_muc else 1
        kq.dong.append(muc)

    kq.chi_bo = sorted(theo_chi_bo.values(), key=lambda c: (c.ma_id or "zz", c.ma_to_chuc))
    return kq


def _chuoi_ma(cac_ma: list[int]) -> str:
    return ",".join(str(m) for m in cac_ma)


def gan_vao_so_cai(kq: KetQuaDoiSoat, dong: list[DongDangVien]) -> int:
    """Ghi 5 cột đối soát vào từng dòng sổ cái. Trả về số dòng đã cập nhật.

    Chỉ chạm đúng 6 trường đối soát; mọi trường khác — nhất là ``ID`` và
    ``Folder_name`` — giữ nguyên tuyệt đối.
    """
    theo_id = {d.id: d for d in dong}
    dem = 0
    for muc in kq.dong:
        d = theo_id.get(muc.id)
        if d is None:
            continue
        d.tai_lieu_da_co = _chuoi_ma(muc.da_co)
        d.tai_lieu_chua_co = _chuoi_ma(muc.chua_co)
        d.tai_lieu_cho_chuyen_pdf = _chuoi_ma(muc.cho_chuyen_pdf)
        d.tien_do_ut1 = str(muc.tien_do[1])
        d.tien_do_ut2 = str(muc.tien_do[2])
        d.tien_do_ut3 = str(muc.tien_do[3])
        dem += 1
    return dem
