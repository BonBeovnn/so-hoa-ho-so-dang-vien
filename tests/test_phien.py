"""Test cấu hình phiên làm việc — trọng tâm là bước 0 và khóa bước.

Bất biến quan trọng nhất: **chưa khai đơn vị thì chưa bước nào được coi là
xong.** Không có nó, tệp cấu hình do bản cũ sinh ra (ghi `[1..7]`, không có
bước 0) sẽ khóa bước 1 nhưng vẫn mở bước 2 — người vận hành nhìn vào không
hiểu vì sao.
"""

import json

import pytest

from app.core.phien import (
    DIA_DANH_MAC_DINH,
    MA_CAP_TREN_MAC_DINH,
    MA_TINH_MAC_DINH,
    TEN_BUOC,
    CauHinh,
    Phien,
)


@pytest.fixture
def tep_cau_hinh(tmp_path, monkeypatch):
    tep = tmp_path / "cau_hinh.json"
    monkeypatch.setattr("app.core.phien.TEP_CAU_HINH", tep)
    return tep


def ghi_tho(tep, **truong):
    tep.write_text(json.dumps(truong, ensure_ascii=False), encoding="utf-8")


class TestDanhSachBuoc:
    def test_co_du_tam_buoc_ke_ca_buoc_0(self):
        assert sorted(TEN_BUOC) == list(range(8))

    def test_buoc_0_la_thong_tin_don_vi(self):
        assert TEN_BUOC[0] == "Thông tin đơn vị"


class TestMacDinhKhongKhoaCungDonVi:
    def test_ma_tinh_va_cap_tren_dien_san(self):
        """38 = Thanh Hóa, 168 = Đảng ủy UBND tỉnh — điền sẵn, không khóa."""
        ch = CauHinh()
        assert ch.ma_tinh == MA_TINH_MAC_DINH == "38"
        assert ch.ma_cap_tren == MA_CAP_TREN_MAC_DINH == "168"
        assert ch.dia_danh == DIA_DANH_MAC_DINH == "Thanh Hóa"

    def test_ma_co_so_va_ten_de_trong(self):
        """Mã riêng của đơn vị là chỗ tuyệt đối không được ghi sẵn."""
        ch = CauHinh()
        assert ch.ma_co_so == ""
        assert ch.ten_dang_bo == ""

    def test_sua_duoc_ca_ba_nhom_cho_don_vi_ngoai_tinh(self):
        ch = CauHinh(ma_tinh="42", ma_cap_tren="170", ma_co_so="011")
        assert ch.ma_dang_bo_co_so == "42.170.011"


class TestMaDangBoCoSo:
    def test_ghep_va_dem_so_0(self):
        assert CauHinh(ma_co_so="53").ma_dang_bo_co_so == "38.168.053"

    def test_chua_nhap_thi_rong(self):
        assert CauHinh().ma_dang_bo_co_so == ""

    def test_ma_hong_thi_rong_chu_khong_no(self):
        """Tệp cấu hình có thể bị sửa tay. Hỏng thì coi như chưa khai."""
        assert CauHinh(ma_co_so="abcd").ma_dang_bo_co_so == ""

    def test_da_khai_don_vi_can_ca_ten_lan_ma(self):
        assert not CauHinh(ten_dang_bo="Đảng bộ X").da_khai_don_vi
        assert not CauHinh(ma_co_so="053").da_khai_don_vi
        assert CauHinh(ten_dang_bo="Đảng bộ X", ma_co_so="053").da_khai_don_vi


class TestKhoaBuoc:
    def test_buoc_0_luon_mo(self):
        assert CauHinh().mo_khoa_duoc(0)

    def test_buoc_1_khoa_khi_chua_xong_buoc_0(self):
        assert not CauHinh().mo_khoa_duoc(1)

    def test_buoc_n_mo_khi_xong_buoc_truoc(self):
        ch = CauHinh(ten_dang_bo="Đảng bộ X", ma_co_so="053")
        ch.ghi = lambda: None
        ch.danh_dau_xong(0)
        assert ch.mo_khoa_duoc(1) and not ch.mo_khoa_duoc(2)


class TestNapTepCauHinhCu:
    def test_ban_cu_khong_co_buoc_0_thi_xoa_het_dau_hoan_thanh(self, tep_cau_hinh):
        """Tệp do bản trước sinh ra: đủ 7 bước xong nhưng không có thông tin đơn vị."""
        ghi_tho(tep_cau_hinh, duong_dan_ds="D:/x.xlsx", buoc_da_xong=[1, 2, 3, 4, 5, 6, 7])
        ch = CauHinh.nap()
        assert ch.buoc_da_xong == []
        assert not ch.mo_khoa_duoc(2)

    def test_da_khai_don_vi_thi_them_buoc_0_vao_danh_sach(self, tep_cau_hinh):
        ghi_tho(
            tep_cau_hinh,
            ten_dang_bo="Đảng bộ X",
            ma_co_so="053",
            buoc_da_xong=[1, 2, 3],
        )
        assert CauHinh.nap().buoc_da_xong == [0, 1, 2, 3]

    def test_tep_hong_thi_ve_mac_dinh(self, tep_cau_hinh):
        tep_cau_hinh.write_text("{khong phai json", encoding="utf-8")
        ch = CauHinh.nap()
        assert ch.buoc_da_xong == [] and ch.ma_tinh == "38"

    def test_ghi_roi_nap_lai_giu_nguyen_thong_tin_don_vi(self, tep_cau_hinh):
        goc = CauHinh(
            ten_dang_bo="Đảng bộ Trung tâm Khuyến nông Hà Tĩnh",
            ten_cap_tren="Đảng bộ UBND tỉnh Hà Tĩnh",
            ma_tinh="42",
            ma_cap_tren="170",
            ma_co_so="011",
            dia_danh="Hà Tĩnh",
        )
        goc.ghi()
        lai = CauHinh.nap()
        assert lai.ten_dang_bo == goc.ten_dang_bo
        assert lai.ma_dang_bo_co_so == "42.170.011"
        assert lai.dia_danh == "Hà Tĩnh"


class TestDatLaiPhien:
    def test_dat_lai_tu_buoc_0_xoa_moi_ket_qua(self):
        p = Phien(cau_hinh=CauHinh(ten_dang_bo="Đảng bộ X", ma_co_so="053"))
        p.cau_hinh.ghi = lambda: None
        p.ket_qua_dong_bo = object()
        p.ke_hoach_cay = object()
        p.ket_qua_quet = object()
        p.ket_qua_doi_soat = object()
        p.tep_bao_cao = {"docx": "x"}
        p.dat_lai_tu_buoc(0)
        assert p.ket_qua_dong_bo is None
        assert p.ke_hoach_cay is None
        assert p.ket_qua_quet is None
        assert p.ket_qua_doi_soat is None
        assert p.tep_bao_cao == {}
