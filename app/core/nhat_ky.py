"""Nhật ký chạy — ghi ra ``app/data/app.log``.

Mục đích duy nhất: khi người vận hành báo "app bị lỗi" mà cửa sổ dòng lệnh đã
đóng mất, vẫn còn dấu vết để lần lại. Vì vậy nhật ký phải:

* **không bao giờ làm sập app** — mọi lỗi ghi nhật ký đều nuốt im lặng;
* **không chứa số định danh cá nhân** — mọi dãy 9–12 chữ số đều bị che trước
  khi ghi, kể cả khi nó nằm giữa một đường dẫn thư mục;
* **không phình vô hạn** — quá 1 MB thì xoay vòng sang ``app.log.1``.

Che số định danh là bắt buộc chứ không phải cho đẹp: tên thư mục đảng viên có
dạng ``099003330003_NguyenDinhHao``, nên chỉ cần ghi một đường dẫn là số CCCD
nằm luôn trong tệp nhật ký — thứ rất dễ bị gửi kèm khi báo lỗi.
"""

from __future__ import annotations

import re
from datetime import datetime

from app.core.paths import thu_muc_du_lieu

__all__ = ["TEP_LOG", "che_so_dinh_danh", "doc_gan_day", "ghi"]

TEP_LOG = thu_muc_du_lieu() / "app.log"
GIOI_HAN_BYTE = 1_000_000

_MAU_SO_DAI = re.compile(r"\d{9,12}")


def che_so_dinh_danh(chuoi: str) -> str:
    """``099003330003_NguyenDinhHao`` ⇒ ``038*********_NguyenDinhHao``"""

    def _che(khop: re.Match) -> str:
        so = khop.group()
        return so[:3] + "*" * (len(so) - 3)

    return _MAU_SO_DAI.sub(_che, chuoi or "")


def _xoay_vong() -> None:
    try:
        if TEP_LOG.exists() and TEP_LOG.stat().st_size > GIOI_HAN_BYTE:
            cu = TEP_LOG.with_suffix(TEP_LOG.suffix + ".1")
            cu.unlink(missing_ok=True)
            TEP_LOG.rename(cu)
    except OSError:
        pass


def ghi(muc: str, thong_diep: str) -> None:
    """Ghi một dòng nhật ký. Không bao giờ ném ngoại lệ ra ngoài."""
    try:
        _xoay_vong()
        TEP_LOG.parent.mkdir(parents=True, exist_ok=True)
        dong = (
            f"{datetime.now():%Y-%m-%d %H:%M:%S} [{muc}] "
            f"{che_so_dinh_danh(str(thong_diep))}\n"
        )
        with open(TEP_LOG, "a", encoding="utf-8") as f:
            f.write(dong)
    except OSError:
        pass


def doc_gan_day(so_byte: int = 200_000) -> str:
    """Phần cuối của nhật ký, dùng cho gói chẩn đoán."""
    try:
        du_lieu = TEP_LOG.read_bytes()
    except OSError:
        return "(chưa có nhật ký)"
    return du_lieu[-so_byte:].decode("utf-8", errors="replace")
