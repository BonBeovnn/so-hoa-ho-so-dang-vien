"""Thông tin tác giả và bản quyền — một nguồn duy nhất cho cả app.

Tên tác giả xuất hiện ở bốn chỗ: chân trang giao diện, trang Hướng dẫn, thuộc
tính tệp ``.docx``/``.xlsx`` xuất ra, và tệp ``LICENSE`` ở gốc kho mã nguồn.
Gom vào một chỗ để sửa một lần là đổi hết, và để không ai phải đi tìm xem app
đang tự xưng là của ai.

Vì sao có mặt trong thuộc tính tệp báo cáo
-----------------------------------------
Tệp ``.docx`` do app dựng ra sẽ đi vòng quanh cơ quan rồi ra khỏi cơ quan. Ghi
tác giả vào ``core_properties`` là dấu vết bản quyền đi theo tệp mà không làm
bẩn nội dung văn bản — phần thân báo cáo tuyệt đối không được có dòng quảng cáo
nào, vì đó là văn bản hành chính của Đảng ủy chứ không phải sản phẩm phần mềm.
"""

from __future__ import annotations

__all__ = [
    "GIAY_PHEP",
    "MO_TA_NGAN",
    "NAM",
    "NGU_CANH_BAN_QUYEN",
    "TAC_GIA",
    "TEN_UNG_DUNG",
    "TEN_HIEU",
    "dong_ban_quyen",
]

TEN_UNG_DUNG = "Số hóa hồ sơ đảng viên"
TEN_HIEU = "Mèo máy"
TAC_GIA = "@anhduc97"
NAM = "2026"
GIAY_PHEP = "Giấy phép sử dụng có điều kiện — xem tệp LICENSE"
MO_TA_NGAN = (
    "Ứng dụng cục bộ hỗ trợ lập cây thư mục, đặt tên, luân chuyển và đối soát "
    "hồ sơ đảng viên theo Quy định 208-QĐ/TW và Nghị định 30/2020/NĐ-CP."
)


def dong_ban_quyen() -> str:
    """``© 2026 @anhduc97`` — dùng cho chân trang và thuộc tính tệp."""
    return f"\u00a9 {NAM} {TAC_GIA}"


# Đưa thẳng vào ngữ cảnh mẫu Jinja để mọi trang đều có, không phải nhớ truyền.
NGU_CANH_BAN_QUYEN = {
    "ten_ung_dung": TEN_UNG_DUNG,
    "ten_hieu": TEN_HIEU,
    "tac_gia": TAC_GIA,
    "ban_quyen": dong_ban_quyen(),
    "giay_phep": GIAY_PHEP,
}
