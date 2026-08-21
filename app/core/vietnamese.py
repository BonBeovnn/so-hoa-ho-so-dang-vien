"""Chuẩn hóa chuỗi tiếng Việt.

Module lá: thuần hàm, không I/O, không phụ thuộc module nào khác.

CẢNH BÁO KỸ THUẬT (ENG-1 trong 0.KEHOACH_TRIENKHAI_v1.md)
---------------------------------------------------------
Công thức bỏ dấu tiếng Việt phổ biến trên mạng:

    ''.join(c for c in unicodedata.normalize('NFD', s)
            if unicodedata.category(c) != 'Mn')

SAI với tiếng Việt. `Đ` (U+0110) và `đ` (U+0111) là **chữ cái riêng** trong
bảng chữ cái, không phải `D` cộng dấu phụ, nên NFD không tách được:

    >>> unicodedata.normalize('NFD', 'Đ') == 'Đ'
    True

Hệ quả nếu dùng công thức trên: `NGUYỄN ĐÌNH HẢO` -> `NGUYEN ĐINH HAI`,
tên thư mục còn chữ `Đ`, sai chuẩn "không dấu" của Kế hoạch.

Phải thay `Đ`/`đ` bằng bảng tra TRƯỚC khi chuẩn hóa NFD.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = [
    "LoiMaToChuc",
    "bo_dau",
    "chuan_hoa_ma_co_so",
    "chuan_hoa_ma_to_chuc",
    "con_dau",
    "dung_folder_name",
    "ma_dang_bo_co_so",
    "pascal_case",
    "slug_tai_lieu",
    "thuoc_dang_bo_co_so",
]

# Các chữ cái tiếng Việt mà NFD KHÔNG tách được vì chúng là chữ cái riêng.
_CHU_CAI_RIENG = str.maketrans({"Đ": "D", "đ": "d"})

# Ký tự được giữ lại trong định danh thư mục / tên tệp sau khi bỏ dấu.
_KY_TU_HOP_LE = re.compile(r"[^A-Za-z0-9]+")


def bo_dau(s: str) -> str:
    """Bỏ toàn bộ dấu tiếng Việt, giữ nguyên hoa/thường và khoảng trắng.

    >>> bo_dau("NGUYỄN ĐÌNH HẢO")
    'NGUYEN DINH HAO'
    >>> bo_dau("TRẦN THỊ HỒNG NHUẬN")
    'TRAN THI HONG NHUAN'
    >>> bo_dau("Quyết định kết nạp đảng viên")
    'Quyet dinh ket nap dang vien'
    """
    if not s:
        return ""
    # Bước 1 — bắt buộc đứng trước NFD.
    s = s.translate(_CHU_CAI_RIENG)
    # Bước 2 — tách dấu phụ rồi loại bỏ.
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def con_dau(s: str) -> list[str]:
    """Trả về danh sách ký tự ngoài ASCII còn sót lại. Dùng để kiểm tra dữ liệu bẩn.

    Rỗng nghĩa là chuỗi đã sạch.

    >>> con_dau("NguyenDinhHao")
    []
    >>> con_dau("TrànThịHòngNhuận")
    ['\\u0300', '\\u0323']
    """
    return sorted({c for c in s if ord(c) > 127})


def pascal_case(ho_ten: str) -> str:
    """Chuyển họ tên đầy đủ thành định danh PascalCase không dấu, không khoảng trắng.

    Dữ liệu nguồn (DS_DANGVIEN.xlsx) viết HOA toàn bộ, nên phải hạ về thường
    rồi mới viết hoa chữ đầu từng từ.

    >>> pascal_case("SẦM THỊ QUỲNH NHƯ")
    'SamThiQuynhNhu'
    >>> pascal_case("NGUYỄN ĐÌNH HẢO")
    'NguyenDinhHao'
    >>> pascal_case("  LÊ  THỊ   THÊU  ")
    'LeThiThem'
    """
    if not ho_ten:
        return ""
    tu = [_KY_TU_HOP_LE.sub("", bo_dau(t)) for t in ho_ten.split()]
    return "".join(t[:1].upper() + t[1:].lower() for t in tu if t)


def slug_tai_lieu(ten: str) -> str:
    """Chuyển tên loại tài liệu thành chuỗi dùng trong tên tệp.

    CHỈ LÀ PHƯƠNG ÁN DỰ PHÒNG. Nguồn chuẩn của 104 tên tài liệu là bảng
    ``N_1..N_104`` trích từ ``LowcodeAPP.MD`` — bảng đó dùng các chữ viết tắt
    đã được thống nhất (QD, GCN, NQ, CV, TB, KL, GGT, PB, HHD, CTXH, LLVT)
    nên KHÔNG suy ra được bằng phép biến đổi cơ học.

    >>> slug_tai_lieu("Lý lịch của người xin vào Đảng")
    'Ly_lich_cua_nguoi_xin_vao_Dang'
    """
    if not ten:
        return ""
    return _KY_TU_HOP_LE.sub("_", bo_dau(ten).strip()).strip("_")


class LoiMaToChuc(ValueError):
    """Mã tổ chức đảng sai định dạng, kèm thông báo tiếng Việt."""


def chuan_hoa_ma_to_chuc(ma: str) -> str:
    """Chuẩn hóa mã tổ chức đảng về đúng dạng có dấu chấm của Quy định 208-QĐ/TW.

    Cấu trúc ``[M1].[M2].[M3].[M4].[M5]``:
      * M1 &mdash; mã đảng bộ tỉnh, 2 chữ số
      * M2 &mdash; mã đảng bộ cấp trên trực tiếp cơ sở, 3 chữ số
      * M3 &mdash; mã đảng bộ cơ sở / chi bộ cơ sở, 3 chữ số
      * M4 &mdash; mã đảng bộ trực thuộc, 3 chữ số (không có thì ghi ``000``)
      * M5 &mdash; mã chi bộ trực thuộc, 3 chữ số

    Nhận cả dạng đã có chấm lẫn dạng 14 chữ số liền, luôn trả về dạng có chấm
    vì **tên thư mục trên đĩa phải có dấu chấm**.

    >>> chuan_hoa_ma_to_chuc("38.168.053.000.001")
    '38.168.053.000.001'
    >>> chuan_hoa_ma_to_chuc("38168053000001")
    '38.168.053.000.001'
    """
    so = re.sub(r"\D", "", ma or "")
    if not so:
        raise LoiMaToChuc("Chưa nhập mã tổ chức đảng.")
    if len(so) != 14:
        raise LoiMaToChuc(
            f"Mã tổ chức đảng {ma!r} có {len(so)} chữ số, phải đúng 14 chữ số "
            "theo dạng [2].[3].[3].[3].[3] — ví dụ 38.168.053.000.001"
        )
    return f"{so[:2]}.{so[2:5]}.{so[5:8]}.{so[8:11]}.{so[11:]}"


def ma_dang_bo_co_so(ma_chi_bo: str) -> str:
    """Lấy phần ``[M1].[M2].[M3]`` — mã đảng bộ cơ sở, dùng làm thư mục cấp trên.

    >>> ma_dang_bo_co_so("38.168.053.000.001")
    '38.168.053'
    """
    return ".".join(chuan_hoa_ma_to_chuc(ma_chi_bo).split(".")[:3])


def chuan_hoa_ma_co_so(ma_tinh: str, ma_cap_tren: str, ma_co_so: str) -> str:
    """Ghép ba nhóm số đầu thành mã đảng bộ cơ sở ``[M1].[M2].[M3]``.

    Đây là mã người dùng nhập ở bước 0. Hai nhóm đầu gần như không đổi trong
    phạm vi một tỉnh — ``38`` là Thanh Hóa, ``168`` là Đảng ủy UBND tỉnh — nên
    giao diện điền sẵn; nhóm thứ ba mới là mã riêng của từng đảng bộ cơ sở, và
    đó chính là chỗ **không được khóa cứng** nếu muốn đơn vị khác dùng chung.

    >>> chuan_hoa_ma_co_so("38", "168", "053")
    '38.168.053'
    >>> chuan_hoa_ma_co_so("38", "168", "7")
    '38.168.007'
    """
    nhom = []
    for ten, gia_tri, do_dai in (
        ("mã đảng bộ tỉnh", ma_tinh, 2),
        ("mã đảng bộ cấp trên trực tiếp cơ sở", ma_cap_tren, 3),
        ("mã đảng bộ cơ sở", ma_co_so, 3),
    ):
        so = re.sub(r"\D", "", str(gia_tri or ""))
        if not so:
            raise LoiMaToChuc(
                f"Chưa nhập {ten}. Mã đảng bộ cơ sở có dạng [2].[3].[3] — "
                f"ví dụ 38.168.053 của Đảng bộ Viện Nông nghiệp Thanh Hóa."
            )
        if len(so) > do_dai:
            raise LoiMaToChuc(
                f"Phần {ten} là {gia_tri!r}, dài {len(so)} chữ số nhưng chỉ được "
                f"{do_dai}. Mã đảng bộ cơ sở có dạng [2].[3].[3] — ví dụ 38.168.053."
            )
        nhom.append(so.zfill(do_dai))
    return ".".join(nhom)


def thuoc_dang_bo_co_so(ma_chi_bo: str, ma_co_so: str) -> bool:
    """Mã chi bộ này có nằm dưới đảng bộ cơ sở đã khai ở bước 0 không?

    >>> thuoc_dang_bo_co_so("38.168.053.000.001", "38.168.053")
    True
    >>> thuoc_dang_bo_co_so("38.168.007.000.001", "38.168.053")
    False
    """
    if not str(ma_co_so or "").strip():
        return True
    return ma_dang_bo_co_so(ma_chi_bo) == ma_co_so


def dung_folder_name(ma_dinh_danh: str | None, ho_ten: str) -> str:
    """Ghép tên thư mục cá nhân theo quy tắc ``[Số CCCD]_[HoTenKhongDau]``.

    Theo ``1.Dacta_fixV1``, mã định danh là **số Căn cước công dân 12 số**, không
    phải số thẻ Đảng. Đã đối chiếu dữ liệu thật: 74/85 dòng có hai số trùng khít
    nhau, 0 dòng lệch, 10 dòng chỉ có CCCD — nên đổi sang CCCD không làm thay
    đổi kết quả nào nhưng đúng quy định.

    Thiếu mã thì trả về mỗi phần tên — đúng quyết định #12 trong đặc tả: vẫn tạo
    thư mục, đưa vào bảng cảnh báo, không chặn tiến độ.

    >>> dung_folder_name("099001110001", "SẦM THỊ QUỲNH NHƯ")
    '099001110001_SamThiQuynhNhu'
    >>> dung_folder_name(None, "LÊ THỊ THÊM")
    'LeThiThem'
    >>> dung_folder_name("   ", "LÊ THỊ THÊM")
    'LeThiThem'
    """
    ten = pascal_case(ho_ten)
    ma = (ma_dinh_danh or "").strip()
    return f"{ma}_{ten}" if ma else ten
