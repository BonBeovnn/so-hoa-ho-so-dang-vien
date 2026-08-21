"""Quét thư mục scan, kiểm tra tên tệp, luân chuyển vào cây thư mục (bước 4–5).

Nguyên tắc bất di bất dịch: **chỉ copy, không bao giờ động vào tệp gốc.**
Chạy sai thì xóa thư mục đích rồi chạy lại — bản scan gốc luôn còn nguyên.

Ba giai đoạn tách bạch
----------------------
``quet()``          đọc thư mục nguồn, tách tên tệp, chấm lỗi E01–E06, W01–W02.
                    Chưa cần biết thư mục đích ở đâu. Tên tệp chỉ cần ba phần
                    ``[Chi bộ].[ID].[Mã tài liệu]``; hậu tố số thứ tự là tùy
                    chọn — xem ``phan_tich_ten``.
``lap_ke_hoach()``  ghép với cây thư mục đích: cấp số thứ tự nối tiếp, chọn kho
                    chính hay kho chờ, phát hiện trùng theo SHA-256 (E07), đo
                    dung lượng ổ đĩa. **Không ghi gì lên đĩa.**
``thuc_thi()``      copy thật và ghi ``manifest_<thời điểm>.csv``.

Vì sao so trùng bằng SHA-256 chứ không bằng tên
-----------------------------------------------
Số thứ tự được cấp nối tiếp, nên chạy lần hai cùng một tệp nguồn sẽ sinh ra tên
mới (``.1`` ⇒ ``.2``) và app sẽ chép thêm một bản y hệt. Vì vậy trước khi cấp
số, mỗi tệp nguồn được đối chiếu **nội dung** với các tệp cùng mã đã nằm ở đích:
trùng nội dung ⇒ bỏ qua im lặng. Nhờ đó chạy lại nhiều lần không nhân bản tệp
và cũng không đổ ra hàng nghìn dòng lỗi giả.
"""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.core.mainbook import DongDangVien
from app.core.paths import LoiDuongDan, an_toan_duoi, thu_muc_du_lieu
from app.core.rename import (
    DUOI_CHO_PHEP,
    KHO_CHO,
    MA_LON_NHAT,
    MA_NHO_NHAT,
    dat_ten,
    danh_muc,
    la_kho_chinh,
    so_lon_nhat_hien_co,
    thu_muc_dich,
)
from app.core.tree import duong_dan_tuong_doi
from app.core.vietnamese import LoiMaToChuc

__all__ = [
    "BO_QUA",
    "COPY",
    "LOI",
    "BoiCanh",
    "KetQuaQuet",
    "TepScan",
    "bam_tep",
    "lap_ke_hoach",
    "phan_tich_ten",
    "quet",
    "sua_thu_cong",
    "thuc_thi",
]

COPY = "copy"
BO_QUA = "bo_qua"
LOI = "loi"

NHAN_HANH_DONG = {
    COPY: "Sẽ chép sang",
    BO_QUA: "Đã có y hệt, bỏ qua",
    LOI: "Lỗi, giữ nguyên ở thư mục nguồn",
}

TEN_LOI = {
    "E01": "Tên tệp không đúng dạng",
    "E02": "Không có đảng viên mang mã này",
    "E03": "Mã tài liệu ngoài danh mục",
    "E04": "Tiền tố chi bộ lệch với chi bộ thật",
    "E05": "Đuôi tệp không xử lý được",
    "E06": "Tệp rỗng hoặc không đọc được",
    "E07": "Đích đã có tệp cùng tên, nội dung khác",
}

TEN_CANH_BAO = {
    "W01": "Trùng số thứ tự người scan khai",
    "W02": "Nghi scan lẻ từng trang",
}

NGUONG_W02 = 5      # nhiều hơn 5 tệp cùng một mã là dấu hiệu scan lẻ trang
DEM_BAM = 1 << 20   # đọc 1 MB mỗi lần khi băm

THU_MUC_MANIFEST = thu_muc_du_lieu()


# ------------------------------------------------------------------ dữ liệu


@dataclass
class TepScan:
    """Một tệp trong thư mục scan, mang theo cả kết quả kiểm tra và kế hoạch."""

    duong_dan: str
    ten_goc: str
    kich_thuoc: int = 0
    duoi: str = ""

    # đọc từ tên tệp
    chi_bo_khai: str = ""
    id_dang_vien: str = ""
    ma_tai_lieu: int = 0
    so_khai: int = 0

    # kết quả kiểm tra
    ma_loi: str = ""
    thong_bao: str = ""
    canh_bao: list[tuple[str, str]] = field(default_factory=list)
    sua_thu_cong: bool = False
    ten_dang_vien: str = ""

    # kế hoạch luân chuyển
    hanh_dong: str = ""
    ten_moi: str = ""
    duong_dan_dich: str = ""
    kho_cho: bool = False
    ma_bam: str = ""

    @property
    def hop_le(self) -> bool:
        return not self.ma_loi

    @property
    def nhom(self) -> tuple[str, int]:
        return (self.id_dang_vien, self.ma_tai_lieu)


@dataclass
class KetQuaQuet:
    thu_muc: str = ""
    goc: str = ""
    tep: list[TepScan] = field(default_factory=list)
    tong_byte: int = 0
    byte_con_trong: int = 0
    da_lap_ke_hoach: bool = False
    manifest: str = ""

    @property
    def hop_le(self) -> list[TepScan]:
        return [t for t in self.tep if t.hop_le]

    @property
    def loi(self) -> list[TepScan]:
        return [t for t in self.tep if t.ma_loi]

    @property
    def canh_bao(self) -> list[TepScan]:
        return [t for t in self.tep if t.canh_bao and t.hop_le]

    @property
    def tom_tat_loi(self) -> dict[str, int]:
        d: dict[str, int] = {}
        for t in self.loi:
            d[t.ma_loi] = d.get(t.ma_loi, 0) + 1
        return d

    @property
    def tom_tat_hanh_dong(self) -> dict[str, int]:
        d = {k: 0 for k in NHAN_HANH_DONG}
        for t in self.tep:
            if t.hanh_dong:
                d[t.hanh_dong] += 1
        return d

    @property
    def du_cho_trong(self) -> bool:
        return self.byte_con_trong == 0 or self.byte_con_trong > self.tong_byte * 1.1


@dataclass
class BoiCanh:
    """Mọi thứ cần để kiểm một tên tệp: sổ cái và bảng chi bộ."""

    theo_id: dict[str, DongDangVien] = field(default_factory=dict)
    ma_id_theo_unit: dict[str, str] = field(default_factory=dict)
    ten_chi_bo_theo_ma_id: dict[str, str] = field(default_factory=dict)

    @classmethod
    def tu_so_cai(
        cls, dong: list[DongDangVien], chi_bo: dict[str, tuple[str, str]] | None = None
    ) -> "BoiCanh":
        bc = cls()
        for d in dong:
            bc.theo_id[d.id.upper()] = d
        for ten, (ma_id, ma_to_chuc) in (chi_bo or {}).items():
            if ma_id:
                bc.ma_id_theo_unit[ma_to_chuc] = ma_id.upper()
                bc.ten_chi_bo_theo_ma_id[ma_id.upper()] = ten
        return bc

    @property
    def khoang_id(self) -> str:
        if not self.theo_id:
            return "(sổ cái đang rỗng)"
        ma = sorted(self.theo_id)
        return f"{ma[0]}–{ma[-1]}" if len(ma) > 1 else ma[0]

    def tim(self, ma_id: str) -> DongDangVien | None:
        """Tra đảng viên theo mã ID, chấp nhận cả ``ID1`` lẫn ``id01``."""
        ma_id = (ma_id or "").strip().upper()
        if ma_id in self.theo_id:
            return self.theo_id[ma_id]
        so = ma_id[2:] if ma_id.startswith("ID") else ma_id
        if so.isdigit():
            return self.theo_id.get(f"ID{int(so):02d}")
        return None


# ------------------------------------------------------------- phân tích tên


def phan_tich_ten(ten: str) -> tuple[str, str, int, int, str] | None:
    """Tách tên tệp scan thành ``(chi bộ, ID, mã tài liệu, số thứ tự, đuôi)``.

    Ba phần bắt buộc là ``[Chi bộ].[ID].[Mã tài liệu]``; **hậu tố số thứ tự
    cuối cùng là tùy chọn**. Có thì app tôn trọng thứ tự người scan đã khai;
    không có thì app tự cấp số nối tiếp — và đó là trường hợp bình thường, vì
    hai tệp cùng mã trong một thư mục nguồn thì chính Windows đã bắt đổi tên
    ngay lúc scan rồi, không lọt vào đây được. Số thứ tự trả về ``0`` nghĩa là
    "người scan chưa khai", không phải "số 0".

    Vị trí của mã ``IDxx`` quyết định cách đọc phần còn lại, nên bốn dạng dưới
    đây không bao giờ lẫn vào nhau:

    >>> phan_tich_ten("A.ID01.65.1.pdf")
    ('A', 'ID01', 65, 1, '.pdf')
    >>> phan_tich_ten("A.ID01.65.pdf")
    ('A', 'ID01', 65, 0, '.pdf')
    >>> phan_tich_ten("ID01.65.1.pdf")
    ('', 'ID01', 65, 1, '.pdf')
    >>> phan_tich_ten("ID01.65.pdf")
    ('', 'ID01', 65, 0, '.pdf')
    """
    phan = (ten or "").split(".")
    if not 3 <= len(phan) <= 5:
        return None
    duoi = "." + phan[-1].lower()
    than = phan[:-1]

    # Mã đảng viên chỉ có thể đứng ở vị trí 0 (không có tiền tố chi bộ) hoặc 1
    # (có tiền tố). Tìm ra nó rồi mọi thứ còn lại đọc được không nhập nhằng.
    vi_tri = -1
    for i, o in enumerate(than[:2]):
        u = o.strip().upper()
        if u.startswith("ID") and u[2:].isdigit():
            vi_tri = i
            break
    if vi_tri < 0:
        return None

    chi_bo = than[0].strip().upper() if vi_tri == 1 else ""
    if vi_tri == 1 and not chi_bo.isalpha():
        return None

    con_lai = than[vi_tri + 1:]
    if len(con_lai) not in (1, 2) or not all(o.isdigit() for o in con_lai):
        return None
    so_khai = int(con_lai[1]) if len(con_lai) == 2 else 0
    return chi_bo, than[vi_tri].strip().upper(), int(con_lai[0]), so_khai, duoi


def bam_tep(duong_dan: Path) -> str:
    """SHA-256 của một tệp, đọc theo khối để không nuốt hết bộ nhớ."""
    bam = hashlib.sha256()
    with open(duong_dan, "rb") as f:
        while khoi := f.read(DEM_BAM):
            bam.update(khoi)
    return bam.hexdigest()


# ------------------------------------------------------------------ quét


def _liet_ke(thu_muc: Path) -> list[Path]:
    """Mọi tệp trong thư mục scan, kể cả trong thư mục con, sắp theo tên."""
    ra: list[Path] = []
    for goc, thu_muc_con, ten_tep in os.walk(thu_muc):
        thu_muc_con[:] = [t for t in thu_muc_con if t != KHO_CHO]
        ra.extend(Path(goc) / t for t in ten_tep)
    return sorted(ra, key=lambda p: str(p).lower())


def _cham_loi(t: TepScan, bc: BoiCanh) -> None:
    """Chấm E01–E06 cho một tệp. Mỗi thông báo nói đủ: sai gì · vì sao · sửa sao."""
    if t.duoi not in DUOI_CHO_PHEP:
        t.ma_loi = "E05"
        cach_sua = (
            "Đây là tệp nén — giải nén ra thư mục rồi quét lại."
            if t.duoi in (".zip", ".rar", ".7z")
            else "Mở tệp lên rồi lưu/xuất sang PDF, sau đó quét lại."
        )
        t.thong_bao = (
            f"Đuôi tệp {t.duoi or '(không có)'} không nằm trong danh sách app xử lý "
            f"({' '.join(DUOI_CHO_PHEP)}). "
            f"v1 không tự chuyển đổi định dạng nên không đặt tên và xếp kho được. "
            f"{cach_sua}"
        )
        return

    phan = phan_tich_ten(t.ten_goc)
    if phan is None:
        t.ma_loi = "E01"
        t.thong_bao = (
            f"Tên tệp không đọc được. App cần ba phần "
            f"[Chi bộ].[ID].[Mã tài liệu] — ví dụ A.ID01.65{t.duoi}. "
            f"Thêm số thứ tự ở cuối (A.ID01.65.1{t.duoi}) nếu muốn tự chọn thứ "
            f"tự, không thêm thì app tự cấp số nối tiếp. Tiền tố chi bộ cũng có "
            f"thể bỏ: ID01.65{t.duoi}. "
            f"Chọn đảng viên và loại tài liệu ở hai ô bên cạnh rồi bấm Sửa, "
            f"app sẽ tự đặt tên đúng cho bản sao."
        )
        return

    t.chi_bo_khai, t.id_dang_vien, t.ma_tai_lieu, t.so_khai, t.duoi = phan

    d = bc.tim(t.id_dang_vien)
    if d is None:
        t.ma_loi = "E02"
        t.thong_bao = (
            f"Sổ cái không có đảng viên nào mang mã {t.id_dang_vien}. "
            f"Mã hiện có trong sổ cái là {bc.khoang_id}. "
            f"Chọn đúng đảng viên ở ô bên cạnh rồi bấm Sửa."
        )
        return
    t.ten_dang_vien = d.name
    t.id_dang_vien = d.id

    if not (MA_NHO_NHAT <= t.ma_tai_lieu <= MA_LON_NHAT) or t.ma_tai_lieu not in danh_muc():
        t.ma_loi = "E03"
        t.thong_bao = (
            f"Mã tài liệu {t.ma_tai_lieu} nằm ngoài danh mục. "
            f"Danh mục chuẩn theo Phụ lục 1 Kế hoạch số hóa đánh số từ "
            f"{MA_NHO_NHAT} đến {MA_LON_NHAT}. "
            f"Chọn đúng loại tài liệu ở ô bên cạnh rồi bấm Sửa."
        )
        return

    if t.chi_bo_khai:
        thuc_te = bc.ma_id_theo_unit.get(d.unit_folder, "")
        if thuc_te and t.chi_bo_khai != thuc_te:
            ten_thuc_te = bc.ten_chi_bo_theo_ma_id.get(thuc_te, d.chi_bo_dang_sinh_hoat)
            t.ma_loi = "E04"
            t.thong_bao = (
                f"Tên tệp khai chi bộ {t.chi_bo_khai} nhưng {d.id} ({d.name}) đang "
                f"sinh hoạt ở chi bộ {thuc_te} — {ten_thuc_te}. "
                f"Một trong hai chỗ bị gõ nhầm nên app không dám đoán. "
                f"Nếu mã {d.id} là đúng thì bấm Sửa để app bỏ qua tiền tố sai; "
                f"nếu ID sai thì chọn lại đảng viên ở ô bên cạnh."
            )
            return

    if t.kich_thuoc <= 0:
        t.ma_loi = "E06"
        t.thong_bao = (
            "Tệp rỗng (0 byte). Máy scan bị gián đoạn hoặc tệp chép dở. "
            "Scan lại tài liệu này rồi quét lại thư mục."
        )
        return
    try:
        with open(t.duong_dan, "rb") as f:
            f.read(1)
    except OSError as loi:
        t.ma_loi = "E06"
        t.thong_bao = (
            f"Không mở được tệp ({loi.strerror or loi}). "
            f"Tệp có thể đang bị chương trình khác giữ, hoặc hỏng. "
            f"Đóng chương trình đang mở tệp rồi quét lại."
        )


def _them_canh_bao(t: TepScan, ma: str, cau: str) -> None:
    if any(m == ma for m, _ in t.canh_bao):
        return
    t.canh_bao.append((ma, cau))


def _cham_canh_bao_nhom(tep: list[TepScan]) -> None:
    """W01 (trùng số khai) và W02 (nghi scan lẻ trang) — xét theo từng nhóm."""
    nhom: dict[tuple[str, int], list[TepScan]] = {}
    for t in tep:
        if t.hop_le:
            nhom.setdefault(t.nhom, []).append(t)

    for (ma_id, ma), cac_tep in nhom.items():
        # so_khai == 0 nghia la khong khai, khong phai khai trung. Dem chung se
        # bao W01 cho moi tep khong co hau to — dung dang canh bao gia.
        dem_so: dict[int, int] = {}
        for t in cac_tep:
            if t.so_khai:
                dem_so[t.so_khai] = dem_so.get(t.so_khai, 0) + 1
        for t in cac_tep:
            if t.so_khai and dem_so[t.so_khai] > 1:
                _them_canh_bao(
                    t,
                    "W01",
                    f"Có {dem_so[t.so_khai]} tệp cùng khai số thứ tự {t.so_khai} cho "
                    f"mã {ma} của {ma_id}. App cấp lại số liên tục theo đúng thứ tự "
                    f"người scan khai nên không mất tệp nào; chỉ cần biết để đối chiếu.",
                )
        if len(cac_tep) > NGUONG_W02:
            for t in cac_tep:
                _them_canh_bao(
                    t,
                    "W02",
                    f"{ma_id} có {len(cac_tep)} tệp cùng mã tài liệu {ma}. "
                    f"Quy ước đã chốt là một tài liệu = một tệp PDF, nên nhiều tệp "
                    f"cùng mã thường là scan lẻ từng trang. Nếu đúng vậy, gộp trang "
                    f"khi scan rồi quét lại; nếu là nhiều tài liệu khác nhau thì bỏ qua.",
                )


def quet(thu_muc: str | os.PathLike, bc: BoiCanh) -> KetQuaQuet:
    """Đọc thư mục scan và chấm lỗi từng tệp. Không ghi gì lên đĩa."""
    thu_muc = Path(thu_muc).expanduser().resolve(strict=False)
    kq = KetQuaQuet(thu_muc=str(thu_muc))
    for p in _liet_ke(thu_muc):
        try:
            kich_thuoc = p.stat().st_size
        except OSError:
            kich_thuoc = 0
        t = TepScan(
            duong_dan=str(p),
            ten_goc=p.name,
            kich_thuoc=kich_thuoc,
            duoi=p.suffix.lower(),
        )
        _cham_loi(t, bc)
        kq.tep.append(t)
    _cham_canh_bao_nhom(kq.tep)
    return kq


# ------------------------------------------------------- kế hoạch luân chuyển


def _thu_muc_dang_vien(goc: Path, d: DongDangVien) -> Path | None:
    try:
        return goc / duong_dan_tuong_doi(d)
    except LoiMaToChuc:
        return None


def _bam_cac_tep_cung_ma(thu_muc_dang_vien: Path, ma: int) -> dict[str, Path]:
    """Băm sẵn các tệp cùng mã đang nằm ở đích, để nhận ra bản đã chép."""
    ra: dict[str, Path] = {}
    from app.core.rename import phan_tich_ten_dich

    for thu_muc in (thu_muc_dang_vien, thu_muc_dang_vien / KHO_CHO):
        try:
            with os.scandir(thu_muc) as muc:
                cac_ten = [m.name for m in muc if m.is_file()]
        except OSError:
            continue
        for ten in cac_ten:
            phan = phan_tich_ten_dich(ten)
            if not phan or phan[0] != int(ma):
                continue
            try:
                ra[bam_tep(thu_muc / ten)] = thu_muc / ten
            except OSError:
                continue
    return ra


def lap_ke_hoach(kq: KetQuaQuet, goc: str | os.PathLike, bc: BoiCanh) -> KetQuaQuet:
    """Gán tên đích và số thứ tự cho từng tệp hợp lệ. KHÔNG ghi gì lên đĩa."""
    goc = Path(goc).expanduser().resolve(strict=False)
    kq.goc = str(goc)
    kq.tong_byte = 0

    nhom: dict[tuple[str, int], list[TepScan]] = {}
    for t in kq.tep:
        t.hanh_dong = LOI if t.ma_loi else ""
        t.ten_moi = ""
        t.duong_dan_dich = ""
        if t.hop_le:
            nhom.setdefault(t.nhom, []).append(t)

    for (ma_id, ma), cac_tep in nhom.items():
        d = bc.tim(ma_id)
        thu_muc_nguoi = _thu_muc_dang_vien(goc, d) if d else None
        if thu_muc_nguoi is None:
            for t in cac_tep:
                t.ma_loi = "E02"
                t.hanh_dong = LOI
                t.thong_bao = (
                    f"Chưa xác định được thư mục của {ma_id} vì thiếu mã tổ chức "
                    f"đảng của chi bộ. Quay lại bước 1 điền mã chi bộ rồi làm lại."
                )
            continue

        so_hien_co = so_lon_nhat_hien_co(thu_muc_nguoi, ma)
        da_co_theo_bam = _bam_cac_tep_cung_ma(thu_muc_nguoi, ma)
        so_luong_cu = len(da_co_theo_bam)
        ke_tiep = so_hien_co

        # Sắp theo SỐ NGƯỜI SCAN KHAI, không theo thứ tự hệ thống tệp: Kế hoạch
        # quy định số thứ tự chạy theo thời gian tài liệu từ cũ tới mới, mà app
        # không biết ngày tài liệu nên phải tôn trọng thứ tự người scan đã khai.
        # Tệp CÓ khai số đi trước theo đúng số đã khai; tệp không khai xếp sau,
        # sắp theo tên. Không tách hai nhóm thì số 0 nhảy lên đầu và tệp không
        # khai chiếm mất số thứ tự của tệp người scan đã đánh số cẩn thận.
        for t in sorted(
            cac_tep, key=lambda x: (0 if x.so_khai else 1, x.so_khai, x.ten_goc.lower())
        ):
            try:
                t.ma_bam = bam_tep(Path(t.duong_dan))
            except OSError as loi:
                t.ma_loi = "E06"
                t.hanh_dong = LOI
                t.thong_bao = (
                    f"Không đọc được nội dung tệp ({loi.strerror or loi}). "
                    f"Tệp có thể đang bị chương trình khác giữ. Đóng rồi quét lại."
                )
                continue

            cu = da_co_theo_bam.get(t.ma_bam)
            if cu is not None:
                t.hanh_dong = BO_QUA
                t.ten_moi = cu.name
                t.duong_dan_dich = str(cu)
                t.kho_cho = cu.parent.name == KHO_CHO
                continue

            ke_tiep += 1
            t.kho_cho = not la_kho_chinh(t.duoi)
            t.ten_moi = dat_ten(ma, ke_tiep, t.duoi)
            dich = thu_muc_dich(thu_muc_nguoi, t.duoi) / t.ten_moi
            t.duong_dan_dich = str(dich)

            if dich.exists():
                # Hiếm: tên trùng nhưng nội dung khác (đã loại trừ trùng nội dung
                # ở trên). Không bao giờ ghi đè — để người quyết định.
                t.ma_loi = "E07"
                t.hanh_dong = LOI
                t.thong_bao = (
                    f"Thư mục đích đã có tệp tên {t.ten_moi} nhưng nội dung khác "
                    f"tệp này. App không ghi đè để khỏi mất bản đã lưu. "
                    f"Mở cả hai tệp so lại, xóa bản sai ở thư mục đích rồi quét lại."
                )
                continue

            t.hanh_dong = COPY
            kq.tong_byte += t.kich_thuoc

        tong_cung_ma = so_luong_cu + sum(1 for t in cac_tep if t.hanh_dong == COPY)
        if tong_cung_ma > NGUONG_W02:
            for t in cac_tep:
                if t.hop_le:
                    _them_canh_bao(
                        t,
                        "W02",
                        f"Tính cả tệp đã có ở thư mục đích, {ma_id} đang có "
                        f"{tong_cung_ma} tệp cùng mã tài liệu {ma}. Quy ước đã chốt "
                        f"là một tài liệu = một tệp PDF, nên đây thường là dấu hiệu "
                        f"scan lẻ từng trang. Kiểm lại rồi gộp khi scan nếu đúng vậy.",
                    )

    try:
        kq.byte_con_trong = shutil.disk_usage(goc if goc.exists() else goc.anchor).free
    except OSError:
        kq.byte_con_trong = 0
    kq.da_lap_ke_hoach = True
    return kq


def sua_thu_cong(
    kq: KetQuaQuet, duong_dan: str, id_dang_vien: str, ma_tai_lieu: int, bc: BoiCanh
) -> TepScan:
    """Người dùng chỉ đúng đảng viên và loại tài liệu cho một tệp sai tên.

    Chỉ sửa **bản sao ở thư mục đích**; tệp gốc trong thư mục scan tuyệt đối
    không bị đổi tên — đúng quyết định #8.
    """
    tim = [t for t in kq.tep if t.duong_dan == duong_dan]
    if not tim:
        raise LoiDuongDan(f"Không còn thấy tệp này trong kết quả quét:\n{duong_dan}")
    t = tim[0]

    d = bc.tim(id_dang_vien)
    if d is None:
        raise LoiDuongDan(f"Không có đảng viên mang mã {id_dang_vien} trong sổ cái.")
    try:
        ma = int(ma_tai_lieu)
    except (TypeError, ValueError):
        raise LoiDuongDan("Chưa chọn loại tài liệu.") from None
    if ma not in danh_muc():
        raise LoiDuongDan(f"Mã tài liệu {ma} không có trong danh mục 104 loại.")
    if t.duoi not in DUOI_CHO_PHEP:
        raise LoiDuongDan(
            f"Đuôi tệp {t.duoi} vẫn không xử lý được. "
            f"Chuyển sang PDF trước rồi quét lại — đổi tên không giải quyết được."
        )

    t.id_dang_vien = d.id
    t.ten_dang_vien = d.name
    t.ma_tai_lieu = ma
    t.chi_bo_khai = ""
    t.so_khai = t.so_khai or 1
    t.ma_loi = ""
    t.thong_bao = ""
    t.sua_thu_cong = True
    return t


# ------------------------------------------------------------------ thực thi


def _ghi_manifest(kq: KetQuaQuet, thoi_diem: datetime) -> Path:
    """Nhật ký từng tệp của lần chạy này.

    Ghi kèm BOM (``utf-8-sig``) để mở bằng Excel không bị vỡ tiếng Việt.
    Không có cột CCCD: manifest chỉ định danh người bằng mã ``ID``.
    """
    THU_MUC_MANIFEST.mkdir(parents=True, exist_ok=True)
    tep = THU_MUC_MANIFEST / f"manifest_{thoi_diem:%Y%m%d_%H%M%S}.csv"
    with open(tep, "w", encoding="utf-8-sig", newline="") as f:
        ghi = csv.writer(f)
        ghi.writerow(
            [
                "duong_dan_goc", "ID", "Ma_tai_lieu", "duong_dan_dich",
                "ten_moi", "trang_thai", "thoi_diem",
            ]
        )
        for t in kq.tep:
            if t.sua_thu_cong and t.hanh_dong == COPY:
                trang_thai = "sua_thu_cong"
            elif t.hanh_dong == COPY:
                trang_thai = "da_chep"
            elif t.hanh_dong == BO_QUA:
                trang_thai = "bo_qua_trung"
            else:
                trang_thai = f"loi_{t.ma_loi}" if t.ma_loi else "bo_qua"
            ghi.writerow(
                [
                    t.duong_dan, t.id_dang_vien, t.ma_tai_lieu or "",
                    t.duong_dan_dich, t.ten_moi, trang_thai,
                    f"{thoi_diem:%Y-%m-%d %H:%M:%S}",
                ]
            )
    return tep


def thuc_thi(kq: KetQuaQuet) -> KetQuaQuet:
    """Chép tệp theo kế hoạch rồi ghi manifest. Tệp gốc không hề bị đụng tới."""
    if not kq.da_lap_ke_hoach:
        raise LoiDuongDan("Chưa lập kế hoạch luân chuyển. Bấm Xem trước trước đã.")
    goc = Path(kq.goc)
    thoi_diem = datetime.now()

    for t in kq.tep:
        if t.hanh_dong != COPY:
            continue
        nguon = Path(t.duong_dan)
        dich = Path(t.duong_dan_dich)
        try:
            if not an_toan_duoi(goc, dich):
                raise OSError("đường dẫn đích nằm ngoài thư mục gốc")
            dich.parent.mkdir(parents=True, exist_ok=True)

            if dich.exists():
                # Xuất hiện trong lúc chạy. Trùng nội dung thì coi như đã có.
                if bam_tep(dich) == t.ma_bam:
                    t.hanh_dong = BO_QUA
                    continue
                t.ma_loi = "E07"
                t.hanh_dong = LOI
                t.thong_bao = (
                    f"Trong lúc đang chạy, thư mục đích xuất hiện tệp {t.ten_moi} "
                    f"có nội dung khác. App dừng lại để khỏi ghi đè. Quét lại."
                )
                continue

            # Chép ra tên tạm rồi mới đổi tên: đứt điện giữa chừng chỉ để lại
            # tệp .dangchep, không tạo ra tệp đích méo mó mà lần sau tưởng thật.
            tam = dich.with_name(dich.name + ".dangchep")
            shutil.copy2(nguon, tam)
            os.replace(tam, dich)
        except OSError as loi:
            t.ma_loi = "E06"
            t.hanh_dong = LOI
            t.thong_bao = f"Chép không thành công: {getattr(loi, 'strerror', None) or loi}"

    kq.manifest = str(_ghi_manifest(kq, thoi_diem))
    return kq
