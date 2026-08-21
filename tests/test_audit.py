"""Test đối soát 104 loại tài liệu và ba mức ưu tiên (bước 6)."""

from pathlib import Path

import pytest

from app.core import audit
from app.core.mainbook import DongDangVien
from app.core.rename import KHO_CHO, dat_ten
from app.core.tree import duong_dan_tuong_doi

VP = "38.168.053.000.001"
QLKH = "38.168.053.000.002"

CHI_BO = {
    "Chi bộ Văn phòng": ("A", VP),
    "Chi bộ Phòng quản lý khoa học": ("B", QLKH),
}


def dv(ma_id, ten, cccd, unit=VP, chi_bo="Chi bộ Văn phòng"):
    from app.core.vietnamese import dung_folder_name, pascal_case

    return DongDangVien(
        id=ma_id,
        so_dong=int(ma_id[2:]),
        name=ten,
        name_convert=pascal_case(ten),
        folder_name=dung_folder_name(cccd, ten),
        unit_folder=unit,
        cccd_id=cccd,
        chi_bo_dang_sinh_hoat=chi_bo,
    )


@pytest.fixture
def so_cai():
    return [
        dv("ID01", "NGUYỄN VĂN A", "012345678901"),
        dv("ID02", "TRẦN THỊ B", "012345678902"),
        dv("ID03", "LÊ VĂN C", "012345678903", QLKH, "Chi bộ Phòng quản lý khoa học"),
    ]


def thu_muc_cua(goc: Path, d: DongDangVien) -> Path:
    return goc / duong_dan_tuong_doi(d)


def dat_tep_dich(goc: Path, d: DongDangVien, ma: int, so: int, duoi: str) -> Path:
    thu_muc = thu_muc_cua(goc, d)
    if duoi != ".pdf":
        thu_muc = thu_muc / KHO_CHO
    thu_muc.mkdir(parents=True, exist_ok=True)
    p = thu_muc / dat_ten(ma, so, duoi)
    p.write_bytes(b"noi dung")
    return p


class TestDanhMucUuTien:
    def test_ranh_gioi_36_49_19(self):
        assert audit.tong_so_theo_uu_tien() == {1: 36, 2: 49, 3: 19}

    def test_ba_muc_cong_lai_du_104_loai_khong_trung_khong_sot(self):
        tat_ca = []
        for ut in (1, 2, 3):
            tat_ca += audit.danh_sach_ma_theo_uu_tien(ut)
        assert sorted(tat_ca) == list(range(1, 105))

    def test_ut1_la_36_ma_dau_tien(self):
        assert audit.danh_sach_ma_theo_uu_tien(1) == list(range(1, 37))
        assert audit.danh_sach_ma_theo_uu_tien(2) == list(range(37, 86))
        assert audit.danh_sach_ma_theo_uu_tien(3) == list(range(86, 105))


class TestDoiSoat:
    def test_co_ma_1_2_65_thi_da_co_dung_ba_ma_do(self, tmp_path, so_cai):
        for ma in (1, 2, 65):
            dat_tep_dich(tmp_path, so_cai[0], ma, 1, ".pdf")
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)
        assert kq.dong[0].da_co == [1, 2, 65]

    def test_chua_co_la_phan_bu_trong_1_104(self, tmp_path, so_cai):
        dat_tep_dich(tmp_path, so_cai[0], 5, 1, ".pdf")
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)
        assert len(kq.dong[0].chua_co) == 103
        assert 5 not in kq.dong[0].chua_co

    def test_tep_kho_cho_khong_duoc_tinh_la_da_co(self, tmp_path, so_cai):
        """Tệp .docx/.jpg chưa đạt chuẩn TT 02/2019 nên vẫn là chưa có."""
        dat_tep_dich(tmp_path, so_cai[0], 7, 1, ".jpg")
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)
        muc = kq.dong[0]
        assert muc.da_co == []
        assert muc.cho_chuyen_pdf == [7]
        assert 7 in muc.chua_co

    def test_tep_khong_dung_chuan_ten_thi_bo_qua(self, tmp_path, so_cai):
        thu_muc = thu_muc_cua(tmp_path, so_cai[0])
        thu_muc.mkdir(parents=True)
        (thu_muc / "Ly lich dang vien.pdf").write_bytes(b"x")
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)
        assert kq.dong[0].da_co == []

    def test_nhieu_tep_cung_ma_van_chi_tinh_mot_lan(self, tmp_path, so_cai):
        dat_tep_dich(tmp_path, so_cai[0], 2, 1, ".pdf")
        dat_tep_dich(tmp_path, so_cai[0], 2, 2, ".pdf")
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)
        assert kq.dong[0].da_co == [2]
        assert kq.dong[0].tien_do[1].co == 1

    def test_tien_do_ba_muc(self, tmp_path, so_cai):
        for ma in (1, 2, 3):          # ƯT1
            dat_tep_dich(tmp_path, so_cai[0], ma, 1, ".pdf")
        for ma in (40, 41):           # ƯT2
            dat_tep_dich(tmp_path, so_cai[0], ma, 1, ".pdf")
        dat_tep_dich(tmp_path, so_cai[0], 90, 1, ".pdf")   # ƯT3
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)
        td = kq.dong[0].tien_do
        assert (str(td[1]), str(td[2]), str(td[3])) == ("3/36", "2/49", "1/19")

    def test_chua_co_thu_muc_thi_bao_ro_chu_khong_bao_lo_i(self, tmp_path, so_cai):
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)
        assert all(not d.co_thu_muc for d in kq.dong)
        assert kq.thieu_thu_muc == 3
        assert "bước 3" in kq.dong[0].ghi_chu

    def test_thieu_ma_to_chuc_dang_thi_khong_lam_sap(self, tmp_path):
        hong = dv("ID09", "LÊ THỊ THÊM", "", unit="")
        kq = audit.doi_soat(tmp_path, [hong], CHI_BO)
        assert kq.dong[0].co_thu_muc is False
        assert "mã tổ chức đảng" in kq.dong[0].ghi_chu


class TestTomTatChiBo:
    def test_gom_dung_theo_chi_bo(self, tmp_path, so_cai):
        dat_tep_dich(tmp_path, so_cai[0], 1, 1, ".pdf")
        dat_tep_dich(tmp_path, so_cai[1], 2, 1, ".pdf")
        dat_tep_dich(tmp_path, so_cai[2], 3, 1, ".pdf")
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)

        assert [c.ma_id for c in kq.chi_bo] == ["A", "B"]
        vp, qlkh = kq.chi_bo
        assert (vp.so_dang_vien, vp.tien_do[1].co, vp.tien_do[1].tong) == (2, 2, 72)
        assert (qlkh.so_dang_vien, qlkh.tien_do[1].co, qlkh.tien_do[1].tong) == (1, 1, 36)

    def test_tong_toan_dang_bo(self, tmp_path, so_cai):
        for d in so_cai:
            dat_tep_dich(tmp_path, d, 1, 1, ".pdf")
            dat_tep_dich(tmp_path, d, 2, 1, ".pdf")
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)
        assert kq.tien_do[1].co == 6
        assert kq.tien_do[1].tong == 3 * 36
        assert kq.tong_tep_da_co == 6
        assert round(kq.tien_do[1].ti_le, 2) == round(6 / 108 * 100, 2)


class TestGanVaoSoCai:
    def test_ghi_dung_sau_truong_doi_soat(self, tmp_path, so_cai):
        for ma in (1, 2, 65):
            dat_tep_dich(tmp_path, so_cai[0], ma, 1, ".pdf")
        dat_tep_dich(tmp_path, so_cai[0], 7, 1, ".docx")
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)
        assert audit.gan_vao_so_cai(kq, so_cai) == 3

        d = so_cai[0]
        assert d.tai_lieu_da_co == "1,2,65"
        assert d.tai_lieu_cho_chuyen_pdf == "7"
        assert d.tien_do_ut1 == "2/36"
        assert d.tien_do_ut2 == "1/49"
        assert d.tien_do_ut3 == "0/19"
        assert d.tai_lieu_chua_co.startswith("3,4,5,6,7,8")

    def test_khong_bao_gio_dung_toi_id_va_folder_name(self, tmp_path, so_cai):
        truoc = [(d.id, d.folder_name, d.unit_folder) for d in so_cai]
        dat_tep_dich(tmp_path, so_cai[0], 1, 1, ".pdf")
        kq = audit.doi_soat(tmp_path, so_cai, CHI_BO)
        audit.gan_vao_so_cai(kq, so_cai)
        assert [(d.id, d.folder_name, d.unit_folder) for d in so_cai] == truoc
