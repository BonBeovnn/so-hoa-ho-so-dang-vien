"""Tạo và bảo trì cây thư mục 4 cấp.

    <thư mục gốc>\\
    └── 38.168.053\\                              cấp 2 — đảng bộ cơ sở, app tự sinh
        └── 38.168.053.000.001\\                  cấp 3 — chi bộ (Unit_Folder)
            └── 099001110001_SamThiQuynhNhu\\     cấp 4 — đảng viên (Folder_name)

Tên thư mục chi bộ **có dấu chấm**, đúng Quy định 208-QĐ/TW (``1.Dacta_fixV1``)
và đúng cây thật đang có tại ``With_APP\\38.168.053``. Cấp đảng bộ cơ sở lấy ba
nhóm số đầu của mã chi bộ nên app tự suy ra được; người dùng chỉ chọn thư mục
chứa nó.

Luôn lập kế hoạch trước, thực thi sau. ``lap_ke_hoach`` không ghi gì lên đĩa —
giao diện hiển thị đúng những gì sắp xảy ra rồi người dùng mới bấm Thực thi.

Bốn tình huống phải phân biệt
-----------------------------
* **tao_moi**       — chưa có thư mục nào, tạo mới.
* **da_co**         — đã đúng chỗ đúng tên, bỏ qua (chạy lại nhiều lần vẫn an toàn).
* **doi_ten**       — đúng chi bộ nhưng tên cũ sai, ví dụ dữ liệu bẩn dòng ID58.
* **chuyen_chi_bo** — đảng viên chuyển sinh hoạt sang chi bộ khác; thư mục cùng
  tệp bên trong phải chuyển theo, tuyệt đối không tạo thư mục rỗng thứ hai.

Không bao giờ tự động gộp hai thư mục. Nếu cả nguồn và đích cùng tồn tại, việc
đó cần người quyết định — báo lỗi và dừng mục đó lại.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from app.core.mainbook import DongDangVien
from app.core.paths import LoiDuongDan, ghep, kiem_tra_thanh_phan
from app.core.vietnamese import LoiMaToChuc, ma_dang_bo_co_so

__all__ = [
    "KetQuaCay",
    "MucKeHoach",
    "dem_tep_ben_trong",
    "do_dai_tuong_doi_lon_nhat",
    "duong_dan_tuong_doi",
    "lap_ke_hoach",
    "thuc_thi",
]

TAO_MOI = "tao_moi"
DA_CO = "da_co"
DOI_TEN = "doi_ten"
CHUYEN_CHI_BO = "chuyen_chi_bo"
LOI = "loi"

NHAN = {
    TAO_MOI: "Tạo mới",
    DA_CO: "Đã có, bỏ qua",
    DOI_TEN: "Đổi tên cho đúng chuẩn",
    CHUYEN_CHI_BO: "Chuyển sang chi bộ mới",
    LOI: "Lỗi, cần xử lý tay",
}


@dataclass
class MucKeHoach:
    id: str
    ho_ten: str
    hanh_dong: str
    duong_dan_dich: str
    duong_dan_nguon: str | None = None
    so_tep_ben_trong: int = 0
    ghi_chu: str = ""

    @property
    def nhan(self) -> str:
        return NHAN[self.hanh_dong]


@dataclass
class KetQuaCay:
    goc: str = ""
    co_so_tao_moi: list[str] = field(default_factory=list)
    co_so_da_co: list[str] = field(default_factory=list)
    don_vi_tao_moi: list[str] = field(default_factory=list)
    don_vi_da_co: list[str] = field(default_factory=list)
    muc: list[MucKeHoach] = field(default_factory=list)

    @property
    def tom_tat(self) -> dict[str, int]:
        d = {k: 0 for k in NHAN}
        for m in self.muc:
            d[m.hanh_dong] += 1
        return d

    @property
    def co_loi(self) -> bool:
        return any(m.hanh_dong == LOI for m in self.muc)

    @property
    def can_thay_doi(self) -> bool:
        return (
            any(m.hanh_dong != DA_CO for m in self.muc)
            or bool(self.don_vi_tao_moi)
            or bool(self.co_so_tao_moi)
        )


def duong_dan_tuong_doi(d: DongDangVien) -> Path:
    """Phần đường dẫn tính từ thư mục gốc.

    ``<đảng bộ cơ sở>\\<chi bộ>\\<đảng viên>`` — cấp đảng bộ cơ sở lấy ba nhóm số
    đầu của mã chi bộ, ví dụ ``38.168.053.000.001`` cho ra ``38.168.053``.
    """
    return Path(ma_dang_bo_co_so(d.unit_folder), d.unit_folder, d.folder_name)


def do_dai_tuong_doi_lon_nhat(dong: list[DongDangVien]) -> int:
    """Độ dài lớn nhất của phần đường dẫn tính từ thư mục gốc.

    Dùng để tính ngân sách MAX_PATH. Với dữ liệu thật của Viện:
    ``38.168.053`` (10) + 1 + ``38.168.053.000.001`` (18) + 1 +
    ``099002220002_TranThiHongNhuan`` (29) = 59 ký tự.
    """
    dai = 0
    for d in dong:
        if not d.unit_folder:
            continue
        try:
            dai = max(dai, len(str(duong_dan_tuong_doi(d))))
        except LoiMaToChuc:
            continue
    return dai


def dem_tep_ben_trong(thu_muc: Path) -> int:
    """Đếm số tệp trong thư mục, tính cả thư mục con. Dùng để cảnh báo trước khi di chuyển."""
    if not thu_muc.is_dir():
        return 0
    return sum(1 for p in thu_muc.rglob("*") if p.is_file())


def _tim_tat_ca_thu_muc(
    goc: Path, d: DongDangVien, ten_cu: str | None
) -> tuple[Path | None, list[tuple[Path, str]]]:
    """Tìm MỌI thư mục đang tồn tại có thể thuộc về một đảng viên.

    Phải quét hết chứ không dừng ở kết quả đầu tiên. Lý do: thư mục đích có thể
    đã đúng tên đúng chỗ TRONG KHI thư mục tên cũ vẫn còn nguyên tệp bên trong.
    Nếu dừng sớm ở thư mục đích, app sẽ báo "đã có, bỏ qua" và bỏ rơi vĩnh viễn
    số tệp nằm trong thư mục cũ.

    Trả về ``(thư mục đích nếu tồn tại, danh sách thư mục lạc chỗ)``.
    """
    thu_muc_chi_bo = goc / duong_dan_tuong_doi(d).parent
    dich = thu_muc_chi_bo / d.folder_name
    dich_ton_tai = dich if dich.is_dir() else None
    lac_cho: list[tuple[Path, str]] = []

    if ten_cu and ten_cu != d.folder_name:
        cu = thu_muc_chi_bo / ten_cu
        if cu.is_dir():
            lac_cho.append((cu, DOI_TEN))

    # Quét mọi thư mục chi bộ khác trong cây — bắt hai trường hợp: đảng viên
    # chuyển sinh hoạt, và thư mục chi bộ còn ở dạng cũ không dấu chấm.
    ten_can_tim = {d.folder_name} | ({ten_cu} if ten_cu else set())
    for chi_bo in _moi_thu_muc_chi_bo(goc):
        if chi_bo == thu_muc_chi_bo:
            continue
        for ten in ten_can_tim:
            ung_vien = chi_bo / ten
            if ung_vien.is_dir():
                lac_cho.append((ung_vien, CHUYEN_CHI_BO))

    return dich_ton_tai, lac_cho


def _moi_thu_muc_chi_bo(goc: Path) -> list[Path]:
    """Liệt kê mọi thư mục chi bộ đang có trong cây, ở cả hai độ sâu.

    Quét cả ``<gốc>/*`` lẫn ``<gốc>/*/*`` vì cây cũ có thể còn thiếu cấp đảng bộ
    cơ sở, hoặc còn tên chi bộ dạng cũ không dấu chấm.
    """
    ra: list[Path] = []
    try:
        with os.scandir(goc) as cap1:
            for a in cap1:
                if not a.is_dir():
                    continue
                ra.append(Path(a.path))
                try:
                    with os.scandir(a.path) as cap2:
                        ra.extend(Path(b.path) for b in cap2 if b.is_dir())
                except OSError:
                    continue
    except OSError:
        pass
    return ra


def lap_ke_hoach(
    goc: str | os.PathLike,
    dong: list[DongDangVien],
    ten_cu_theo_id: dict[str, str] | None = None,
) -> KetQuaCay:
    """Lập kế hoạch tạo cây thư mục. KHÔNG ghi gì lên đĩa."""
    goc = Path(goc).expanduser().resolve(strict=False)
    ten_cu_theo_id = ten_cu_theo_id or {}
    kq = KetQuaCay(goc=str(goc))

    don_vi_can_co: list[tuple[str, str]] = []
    for d in dong:
        if not d.unit_folder:
            continue
        try:
            cap = (ma_dang_bo_co_so(d.unit_folder), d.unit_folder)
        except LoiMaToChuc:
            continue
        if cap not in don_vi_can_co:
            don_vi_can_co.append(cap)

    for co_so, chi_bo in don_vi_can_co:
        if co_so not in kq.co_so_tao_moi and co_so not in kq.co_so_da_co:
            (kq.co_so_da_co if (goc / co_so).is_dir() else kq.co_so_tao_moi).append(co_so)
        co = (goc / co_so / chi_bo).is_dir()
        (kq.don_vi_da_co if co else kq.don_vi_tao_moi).append(chi_bo)

    for d in dong:
        if not d.unit_folder:
            kq.muc.append(
                MucKeHoach(
                    d.id, d.name, LOI, "",
                    ghi_chu="Chưa xác định được mã thư mục chi bộ. "
                            "Sửa ở bước 1 rồi quay lại bước này.",
                )
            )
            continue

        try:
            tuong_doi = duong_dan_tuong_doi(d)
            for phan in tuong_doi.parts:
                kiem_tra_thanh_phan(phan)
            dich = ghep(goc, *tuong_doi.parts)
        except (LoiDuongDan, LoiMaToChuc) as loi:
            kq.muc.append(MucKeHoach(d.id, d.name, LOI, "", ghi_chu=str(loi)))
            continue

        dich_ton_tai, lac_cho = _tim_tat_ca_thu_muc(goc, d, ten_cu_theo_id.get(d.id))

        # Thư mục đích đã đúng NHƯNG còn thư mục lạc chỗ: tuyệt đối không được
        # báo "đã có, bỏ qua" — làm vậy là bỏ rơi tệp trong thư mục kia.
        if dich_ton_tai and lac_cho:
            danh_sach = "\n".join(str(p) for p, _ in lac_cho)
            kq.muc.append(
                MucKeHoach(
                    d.id, d.name, LOI, str(dich), str(lac_cho[0][0]),
                    so_tep_ben_trong=sum(dem_tep_ben_trong(p) for p, _ in lac_cho),
                    ghi_chu=f"Tồn tại đồng thời nhiều thư mục cho cùng một đảng viên:\n"
                            f"{danh_sach}\n{dich}\n"
                            "Cần người kiểm tra và gộp thủ công — app không tự gộp.",
                )
            )
            continue

        if dich_ton_tai:
            kq.muc.append(
                MucKeHoach(
                    d.id, d.name, DA_CO, str(dich),
                    so_tep_ben_trong=dem_tep_ben_trong(dich),
                )
            )
            continue

        if not lac_cho:
            kq.muc.append(MucKeHoach(d.id, d.name, TAO_MOI, str(dich)))
            continue

        if len(lac_cho) > 1:
            danh_sach = "\n".join(str(p) for p, _ in lac_cho)
            kq.muc.append(
                MucKeHoach(
                    d.id, d.name, LOI, str(dich), str(lac_cho[0][0]),
                    so_tep_ben_trong=sum(dem_tep_ben_trong(p) for p, _ in lac_cho),
                    ghi_chu=f"Tìm thấy nhiều thư mục cũ cho cùng một đảng viên:\n"
                            f"{danh_sach}\nCần người xác định thư mục nào là đúng.",
                )
            )
            continue

        nguon, hanh_dong = lac_cho[0]
        ghi_chu = (
            f"Thư mục cũ ở {nguon.parent.name}, chuyển sang {d.unit_folder}."
            if hanh_dong == CHUYEN_CHI_BO
            else f"Tên cũ {nguon.name!r} sai chuẩn, đổi thành {d.folder_name!r}."
        )
        kq.muc.append(
            MucKeHoach(
                d.id, d.name, hanh_dong, str(dich), str(nguon),
                so_tep_ben_trong=dem_tep_ben_trong(nguon), ghi_chu=ghi_chu,
            )
        )

    return kq


def thuc_thi(ke_hoach: KetQuaCay) -> KetQuaCay:
    """Áp kế hoạch lên đĩa. Trả về kế hoạch đã cập nhật trạng thái từng mục.

    An toàn khi chạy lại: mọi thao tác tạo đều dùng ``exist_ok=True``, thao tác
    di chuyển đều kiểm đích chưa tồn tại trước khi chạm vào.
    """
    goc = Path(ke_hoach.goc)
    goc.mkdir(parents=True, exist_ok=True)

    # Thư mục chi bộ nằm dưới thư mục đảng bộ cơ sở, nên mkdir với parents=True
    # tạo luôn cả hai cấp. Lấy đường dẫn đầy đủ từ chính kế hoạch đã lập.
    for m in ke_hoach.muc:
        if m.duong_dan_dich:
            Path(m.duong_dan_dich).parent.mkdir(parents=True, exist_ok=True)

    for m in ke_hoach.muc:
        if m.hanh_dong in (DA_CO, LOI):
            continue
        dich = Path(m.duong_dan_dich)
        try:
            if m.hanh_dong == TAO_MOI:
                dich.mkdir(parents=True, exist_ok=True)
            else:  # doi_ten hoặc chuyen_chi_bo
                nguon = Path(m.duong_dan_nguon)
                if not nguon.is_dir():
                    m.hanh_dong = LOI
                    m.ghi_chu = f"Không còn tìm thấy thư mục nguồn:\n{nguon}"
                    continue
                if dich.exists():
                    m.hanh_dong = LOI
                    m.ghi_chu = f"Thư mục đích đã xuất hiện trong lúc chạy:\n{dich}"
                    continue
                dich.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(nguon), str(dich))
        except OSError as loi:
            m.hanh_dong = LOI
            m.ghi_chu = f"Hệ điều hành từ chối: {loi}"

    return ke_hoach
