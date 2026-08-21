"""Gói chẩn đoán — nén mọi thứ người hỗ trợ cần vào một tệp ``.zip``.

Vì sao cần
----------
Người vận hành là cán bộ văn phòng. Khi có sự cố, thứ họ gửi được thường chỉ là
một câu "app báo lỗi" kèm ảnh chụp màn hình đã cắt mất phần quan trọng. Một nút
bấm cho ra tệp zip đính kèm email là cách rẻ nhất để rút ngắn vòng hỏi–đáp.

Ranh giới dữ liệu cá nhân
-------------------------
Gói này rất dễ bị chuyển tiếp qua email cho người ngoài cơ quan. Vì vậy **mọi
dãy 9–12 chữ số đều bị che** trước khi đưa vào gói — số CCCD nằm ngay trong tên
thư mục đảng viên (``099003330003_NguyenDinhHao``) nên chỉ cần ghi một đường
dẫn là nó lọt ra ngoài. Tên người vẫn giữ vì không có tên thì nhật ký vô dụng,
và tên đảng viên không phải bí mật như số định danh.
"""

from __future__ import annotations

import io
import os
import platform
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from app.core.nhat_ky import TEP_LOG, che_so_dinh_danh, doc_gan_day
from app.core.paths import thu_muc_du_lieu, thu_muc_goc_ung_dung

__all__ = ["THU_MUC_DU_LIEU", "dung_goi", "ten_goi", "thong_tin_he_thong"]

THU_MUC_DU_LIEU = thu_muc_du_lieu()
SO_THU_MUC_LIET_KE = 60


def _phien_ban_goi() -> list[str]:
    ra = []
    for ten in ("fastapi", "uvicorn", "openpyxl", "docx", "jinja2", "pydantic"):
        try:
            mo_dun = __import__(ten)
            ra.append(f"  {ten:12} {getattr(mo_dun, '__version__', '(không rõ)')}")
        except ImportError:
            ra.append(f"  {ten:12} CHƯA CÀI")
    return ra


def thong_tin_he_thong(cong: int | None = None) -> str:
    dong = [
        "THÔNG TIN MÁY VÀ ỨNG DỤNG",
        "=" * 60,
        f"Thời điểm xuất gói : {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Python             : {sys.version.split()[0]} ({platform.machine()})",
        f"Hệ điều hành       : {platform.platform()}",
        f"Thư mục app        : {thu_muc_goc_ung_dung()}",
        f"Cổng đang chạy     : {cong if cong is not None else '(không rõ)'}",
        "",
        "Thư viện:",
        *_phien_ban_goi(),
    ]
    return "\n".join(dong)


def _tom_tat_cay(goc: str) -> str:
    """Đếm thư mục và tệp trong kho, kèm vài chục thư mục đầu để đối chiếu."""
    # Path("") ra thành "." — không chặn thì gói chẩn đoán sẽ đi liệt kê toàn bộ
    # thư mục app, kể cả .venv, cho ra vài nghìn dòng vô nghĩa.
    if not str(goc or "").strip():
        return "Chưa có kho hồ sơ: chưa chạy bước 3."
    duong_dan = Path(goc)
    if not duong_dan.is_dir():
        return f"Chưa có kho hồ sơ, hoặc không mở được: {goc!r}"

    thu_muc = tep = 0
    theo_nguoi: list[tuple[str, int]] = []
    for hien_tai, cac_thu_muc, cac_tep in os.walk(duong_dan):
        thu_muc += len(cac_thu_muc)
        tep += len(cac_tep)
        if len(theo_nguoi) < SO_THU_MUC_LIET_KE and cac_tep:
            theo_nguoi.append(
                (str(Path(hien_tai).relative_to(duong_dan)), len(cac_tep))
            )

    dong = [
        f"Kho hồ sơ    : {duong_dan}",
        f"Tổng thư mục : {thu_muc}",
        f"Tổng tệp     : {tep}",
        "",
        f"{SO_THU_MUC_LIET_KE} thư mục đầu tiên có tệp:",
    ]
    dong += [f"  {so:>4} tệp  {ten}" for ten, so in theo_nguoi]
    return che_so_dinh_danh("\n".join(dong))


def _manifest_moi_nhat() -> tuple[str, str] | None:
    cac_tep = sorted(THU_MUC_DU_LIEU.glob("manifest_*.csv"))
    if not cac_tep:
        return None
    tep = cac_tep[-1]
    try:
        return tep.name, che_so_dinh_danh(tep.read_text(encoding="utf-8-sig"))
    except OSError:
        return None


def ten_goi() -> str:
    return f"GoiChanDoan_{datetime.now():%Y%m%d_%H%M%S}.zip"


def dung_goi(cau_hinh, trang_thai: str = "", cong: int | None = None) -> bytes:
    """Dựng tệp zip trong bộ nhớ. Không để lại tệp tạm nào trên đĩa."""
    bo_nho = io.BytesIO()
    with zipfile.ZipFile(bo_nho, "w", zipfile.ZIP_DEFLATED) as goi:
        goi.writestr("thong_tin.txt", thong_tin_he_thong(cong))
        goi.writestr("trang_thai.txt", che_so_dinh_danh(trang_thai))
        goi.writestr(
            "duong_dan.txt",
            che_so_dinh_danh(
                "\n".join(
                    f"{ten:20} = {gia_tri}"
                    for ten, gia_tri in vars(cau_hinh).items()
                )
            ),
        )
        goi.writestr("cay_thu_muc.txt", _tom_tat_cay(getattr(cau_hinh, "duong_dan_goc", "")))
        goi.writestr("app.log", che_so_dinh_danh(doc_gan_day()))

        cu = TEP_LOG.with_suffix(TEP_LOG.suffix + ".1")
        if cu.exists():
            try:
                goi.writestr(
                    "app.log.1",
                    che_so_dinh_danh(cu.read_text(encoding="utf-8", errors="replace")),
                )
            except OSError:
                pass

        manifest = _manifest_moi_nhat()
        if manifest:
            goi.writestr(manifest[0], manifest[1])

        goi.writestr(
            "DOC_TOI.txt",
            "GÓI CHẨN ĐOÁN — ỨNG DỤNG SỐ HÓA HỒ SƠ ĐẢNG VIÊN\n"
            "=" * 60 + "\n\n"
            "Gói này do chính ứng dụng tạo ra để gửi kèm khi báo lỗi.\n\n"
            "Đã che số định danh: mọi dãy 9–12 chữ số trong gói đều bị thay\n"
            "bằng dấu sao, nên gửi qua email không làm lộ số CCCD của đảng viên.\n\n"
            "Gói KHÔNG chứa: nội dung tệp hồ sơ, ngày sinh, số thẻ đảng viên.\n",
        )
    return bo_nho.getvalue()
