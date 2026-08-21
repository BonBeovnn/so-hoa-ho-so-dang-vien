"""Trạng thái phiên làm việc.

App dùng cho một người, chạy trên một máy, nên không cần cơ sở dữ liệu. Cấu
hình (đường dẫn các tệp, thư mục gốc, bước nào đã xong) nằm trong một tệp JSON
để lần mở sau không phải nhập lại.

Kết quả tính toán trung gian — bảng 85 dòng, danh sách cảnh báo, kế hoạch tạo
cây — chỉ giữ trong bộ nhớ. Tắt app là mất, phải chạy lại bước 1. Đây là lựa
chọn có chủ ý: dữ liệu trung gian cũ dễ khiến người dùng thao tác trên thông
tin đã lỗi thời.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.core.paths import thu_muc_du_lieu
from app.core.vietnamese import LoiMaToChuc, chuan_hoa_ma_co_so

TEP_CAU_HINH = thu_muc_du_lieu() / "cau_hinh.json"

TEN_BUOC = {
    0: "Thông tin đơn vị",
    1: "Nạp dữ liệu",
    2: "Duyệt dữ liệu",
    3: "Tạo cây thư mục",
    4: "Quét tệp scan",
    5: "Luân chuyển tệp",
    6: "Đối soát",
    7: "Báo cáo",
}


# Hai nhóm số đầu của mã tổ chức đảng gần như không đổi trong phạm vi một tỉnh:
# 38 = Thanh Hóa, 168 = Đảng ủy UBND tỉnh. Điền sẵn để người vận hành khỏi phải
# tra, nhưng vẫn cho sửa — khóa cứng thì đơn vị ngoài tỉnh không dùng lại được.
MA_TINH_MAC_DINH = "38"
MA_CAP_TREN_MAC_DINH = "168"
DIA_DANH_MAC_DINH = "Thanh Hóa"


@dataclass
class CauHinh:
    # --- bước 0: nhận diện đơn vị. Mọi chỗ khác trong app đọc từ đây, không
    # được viết thẳng tên hay mã của một đơn vị cụ thể vào mã nguồn.
    ten_dang_bo: str = ""
    ten_cap_tren: str = ""
    ma_tinh: str = MA_TINH_MAC_DINH
    ma_cap_tren: str = MA_CAP_TREN_MAC_DINH
    ma_co_so: str = ""
    dia_danh: str = DIA_DANH_MAC_DINH

    duong_dan_ds: str = ""
    duong_dan_main: str = ""
    duong_dan_goc: str = ""
    duong_dan_scan: str = ""
    duong_dan_bao_cao: str = ""
    buoc_da_xong: list[int] = field(default_factory=list)

    @classmethod
    def nap(cls) -> "CauHinh":
        try:
            d = json.loads(TEP_CAU_HINH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        return cls(
            ten_dang_bo=str(d.get("ten_dang_bo", "")),
            ten_cap_tren=str(d.get("ten_cap_tren", "")),
            ma_tinh=str(d.get("ma_tinh", MA_TINH_MAC_DINH)),
            ma_cap_tren=str(d.get("ma_cap_tren", MA_CAP_TREN_MAC_DINH)),
            ma_co_so=str(d.get("ma_co_so", "")),
            dia_danh=str(d.get("dia_danh", DIA_DANH_MAC_DINH)),
            duong_dan_ds=str(d.get("duong_dan_ds", "")),
            duong_dan_main=str(d.get("duong_dan_main", "")),
            duong_dan_goc=str(d.get("duong_dan_goc", "")),
            duong_dan_scan=str(d.get("duong_dan_scan", "")),
            duong_dan_bao_cao=str(d.get("duong_dan_bao_cao", "")),
            buoc_da_xong=[int(x) for x in d.get("buoc_da_xong", []) if str(x).isdigit()],
        )._chuan_hoa()

    def _chuan_hoa(self) -> "CauHinh":
        """Giữ bất biến: chưa khai đơn vị thì coi như chưa bước nào xong.

        Cần cho tệp cấu hình sinh ra bởi bản cũ — bản đó chưa có bước 0 nên
        ``buoc_da_xong`` ghi [1..7]. Không chuẩn hóa thì bước 1 bị khóa trong
        khi bước 2 vẫn mở, người vận hành nhìn vào không hiểu vì sao.
        """
        if not self.da_khai_don_vi:
            self.buoc_da_xong = []
        elif 0 not in self.buoc_da_xong:
            self.buoc_da_xong = sorted({0, *self.buoc_da_xong})
        return self

    def ghi(self) -> None:
        TEP_CAU_HINH.parent.mkdir(parents=True, exist_ok=True)
        TEP_CAU_HINH.write_text(
            json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @property
    def ma_dang_bo_co_so(self) -> str:
        """``38.168.053`` — tên thư mục cấp 2, ghép từ ba ô của bước 0.

        Rỗng khi chưa làm bước 0; lúc đó cây thư mục vẫn suy ra được mã này từ
        mã chi bộ, chỉ là app không đối chiếu chéo được nữa.
        """
        if not str(self.ma_co_so or "").strip():
            return ""
        try:
            return chuan_hoa_ma_co_so(self.ma_tinh, self.ma_cap_tren, self.ma_co_so)
        except LoiMaToChuc:
            return ""

    @property
    def da_khai_don_vi(self) -> bool:
        return bool(str(self.ten_dang_bo or "").strip() and self.ma_dang_bo_co_so)

    def danh_dau_xong(self, buoc: int) -> None:
        if buoc not in self.buoc_da_xong:
            self.buoc_da_xong.append(buoc)
            self.buoc_da_xong.sort()
        self.ghi()

    def bo_danh_dau_tu(self, buoc: int) -> None:
        """Bước sau phụ thuộc bước trước: sửa bước 1 thì bước 2, 3... phải làm lại."""
        self.buoc_da_xong = [b for b in self.buoc_da_xong if b < buoc]
        self.ghi()

    def mo_khoa_duoc(self, buoc: int) -> bool:
        """Bước n chỉ mở khi bước n-1 đã xong. Bước 0 luôn mở."""
        return buoc == 0 or (buoc - 1) in self.buoc_da_xong


@dataclass
class Phien:
    """Trạng thái sống trong bộ nhớ, không ghi ra đĩa."""

    cau_hinh: CauHinh = field(default_factory=CauHinh.nap)
    ket_qua_dong_bo: Any = None       # KetQuaDongBo từ bước 1
    chi_bo: dict[str, tuple[str, str]] = field(default_factory=dict)
    ke_hoach_cay: Any = None          # KetQuaCay từ bước 3
    thong_tin_ngan_sach: Any = None
    ket_qua_quet: Any = None          # KetQuaQuet từ bước 4
    ket_qua_doi_soat: Any = None      # KetQuaDoiSoat từ bước 6
    tep_bao_cao: dict[str, str] = field(default_factory=dict)

    def dat_lai_tu_buoc(self, buoc: int) -> None:
        if buoc <= 1:
            self.ket_qua_dong_bo = None
            self.chi_bo = {}
        if buoc <= 3:
            self.ke_hoach_cay = None
            self.thong_tin_ngan_sach = None
        if buoc <= 4:
            self.ket_qua_quet = None
        if buoc <= 6:
            self.ket_qua_doi_soat = None
            self.tep_bao_cao = {}
        self.cau_hinh.bo_danh_dau_tu(buoc)


PHIEN = Phien()
