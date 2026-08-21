"""Test xử lý đường dẫn: ngân sách MAX_PATH, chặn thoát thư mục, duyệt thư mục."""

import os
from pathlib import Path

import pytest

from app.core.paths import (
    GIOI_HAN_WINDOWS,
    NGUONG_CANH_BAO_GOC,
    LoiDuongDan,
    an_toan_duoi,
    do_dai_ten_tep_lon_nhat,
    ghep,
    kiem_tra_thanh_phan,
    kiem_tra_thu_muc_goc,
    liet_ke_o_dia,
    liet_ke_thu_muc_con,
    ngan_sach_duong_dan_goc,
)

# Độ dài phần đường dẫn tương đối lớn nhất trong dữ liệu thật, cây 4 cấp:
# 10 (38.168.053) + 1 + 18 (38.168.053.000.001) + 1 + 29 (099002220002_TranThiHongNhuan)
TUONG_DOI_THAT = 59


class TestNganSachMaxPath:
    def test_do_dai_ten_tep_tinh_tu_danh_muc_that(self):
        """3 (mã) + 1 + 91 (tên dài nhất) + 1 + 3 (số thứ tự) + 1 + 4 (jpeg)."""
        assert do_dai_ten_tep_lon_nhat() == 104

    def test_ngan_sach_voi_du_lieu_that(self):
        assert ngan_sach_duong_dan_goc(TUONG_DOI_THAT) == (
            GIOI_HAN_WINDOWS - TUONG_DOI_THAT - 1 - 104
        )
        assert ngan_sach_duong_dan_goc(TUONG_DOI_THAT) == 95

    def test_nguong_chan_thap_hon_ngan_sach_that(self):
        """Ngưỡng app chặn phải để lại biên an toàn so với giới hạn tính được."""
        assert NGUONG_CANH_BAO_GOC < ngan_sach_duong_dan_goc(TUONG_DOI_THAT)

    def test_tinh_dung_tong_va_phan_con_lai(self, tmp_path):
        """Phần số học phải đúng bất kể tmp_path dài bao nhiêu."""
        tt = kiem_tra_thu_muc_goc(tmp_path, TUONG_DOI_THAT)
        assert tt.tong_toi_da == len(str(tmp_path)) + 1 + TUONG_DOI_THAT + 1 + 104
        assert tt.con_lai == 95 - len(str(tmp_path))
        assert tt.do_dai_ten_tep == 104

    def test_thu_muc_goc_ngan_thi_dat(self, tmp_path, monkeypatch):
        """Nới ngưỡng để kiểm nhánh 'đạt' mà không phụ thuộc độ dài tmp_path."""
        import app.core.paths as mp

        monkeypatch.setattr(mp, "NGUONG_CANH_BAO_GOC", 200)
        ngan = tmp_path / "SoHoa"
        ngan.mkdir()
        tt = kiem_tra_thu_muc_goc(ngan, TUONG_DOI_THAT)
        assert tt.dat
        assert "trong ngưỡng cho phép" in tt.thong_bao

    def test_thu_muc_goc_qua_dai_thi_khong_dat(self, tmp_path):
        sau = tmp_path
        while len(str(sau)) <= NGUONG_CANH_BAO_GOC:
            sau = sau / ("thu_muc_long_nhau_rat_dai" [:25])
        sau.mkdir(parents=True, exist_ok=True)
        tt = kiem_tra_thu_muc_goc(sau, TUONG_DOI_THAT)
        assert not tt.dat
        assert str(len(str(sau))) in tt.thong_bao
        assert "gần gốc ổ đĩa hơn" in tt.thong_bao

    def test_thu_muc_khong_ton_tai(self, tmp_path):
        with pytest.raises(LoiDuongDan) as e:
            kiem_tra_thu_muc_goc(tmp_path / "khong_co", TUONG_DOI_THAT)
        assert "Không tìm thấy thư mục" in str(e.value)

    def test_tro_vao_tep_thay_vi_thu_muc(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(LoiDuongDan) as e:
            kiem_tra_thu_muc_goc(f, TUONG_DOI_THAT)
        assert "tệp, không phải thư mục" in str(e.value)

    def test_duong_dan_rong(self):
        with pytest.raises(LoiDuongDan) as e:
            kiem_tra_thu_muc_goc("   ", TUONG_DOI_THAT)
        assert "Chưa chọn thư mục gốc" in str(e.value)

    def test_thong_bao_khong_lo_traceback(self, tmp_path):
        with pytest.raises(LoiDuongDan) as e:
            kiem_tra_thu_muc_goc(tmp_path / "khong_co", TUONG_DOI_THAT)
        assert "Traceback" not in str(e.value)


class TestKiemTraThanhPhan:
    @pytest.mark.parametrize(
        "ten", ["099001110001_SamThiQuynhNhu", "LeThiThem", "38168053000001"]
    )
    def test_ten_that_deu_hop_le(self, ten):
        assert kiem_tra_thanh_phan(ten) == ten

    @pytest.mark.parametrize("ten", ["", "   ", ".", ".."])
    def test_ten_rong_hoac_dac_biet(self, ten):
        with pytest.raises(LoiDuongDan):
            kiem_tra_thanh_phan(ten)

    @pytest.mark.parametrize("ten", ["a/b", "a\\b"])
    def test_chua_dau_phan_cach(self, ten):
        with pytest.raises(LoiDuongDan) as e:
            kiem_tra_thanh_phan(ten)
        assert "phân cách" in str(e.value) or "cấm" in str(e.value)

    @pytest.mark.parametrize("ten", ['a<b', 'a>b', 'a:b', 'a"b', "a|b", "a?b", "a*b"])
    def test_ky_tu_windows_cam(self, ten):
        with pytest.raises(LoiDuongDan):
            kiem_tra_thanh_phan(ten)

    @pytest.mark.parametrize("ten", ["CON", "PRN", "AUX", "NUL", "COM1", "LPT9", "con", "Com3"])
    def test_ten_thiet_bi_danh_rieng(self, ten):
        """Windows không cho tạo thư mục tên CON, PRN, COM1..."""
        with pytest.raises(LoiDuongDan) as e:
            kiem_tra_thanh_phan(ten)
        assert "dành riêng" in str(e.value)

    def test_ket_thuc_bang_dau_cham(self):
        with pytest.raises(LoiDuongDan):
            kiem_tra_thanh_phan("ThuMuc.")

    def test_khoang_trang_thua(self):
        with pytest.raises(LoiDuongDan):
            kiem_tra_thanh_phan(" ThuMuc")


class TestAnToanDuoi:
    def test_con_that_su_nam_duoi(self, tmp_path):
        assert an_toan_duoi(tmp_path, tmp_path / "a" / "b")

    def test_chinh_no(self, tmp_path):
        assert an_toan_duoi(tmp_path, tmp_path)

    def test_thoat_ra_ngoai_bang_hai_cham(self, tmp_path):
        assert not an_toan_duoi(tmp_path, tmp_path / ".." / ".." / "Windows")

    def test_thu_muc_anh_em(self, tmp_path):
        assert not an_toan_duoi(tmp_path / "a", tmp_path / "b")


class TestGhep:
    def test_ghep_binh_thuong(self, tmp_path):
        p = ghep(tmp_path, "38168053000001", "099001110001_SamThiQuynhNhu")
        assert p == tmp_path / "38168053000001" / "099001110001_SamThiQuynhNhu"

    def test_chan_muu_toan_thoat_thu_muc(self, tmp_path):
        with pytest.raises(LoiDuongDan):
            ghep(tmp_path, "..", "Windows")

    def test_chan_dau_phan_cach_lot_vao_thanh_phan(self, tmp_path):
        with pytest.raises(LoiDuongDan):
            ghep(tmp_path, "a\\..\\..\\b")


class TestDuyetThuMuc:
    def test_khong_truyen_gi_thi_tra_ve_o_dia(self):
        kq = liet_ke_thu_muc_con(None)
        assert kq["hien_tai"] is None
        assert kq["o_dia"]

    def test_liet_ke_thu_muc_con(self, tmp_path):
        (tmp_path / "b_hai").mkdir()
        (tmp_path / "a_mot").mkdir()
        (tmp_path / "tep.txt").write_text("x", encoding="utf-8")
        kq = liet_ke_thu_muc_con(tmp_path)
        assert kq["thu_muc"] == ["a_mot", "b_hai"]  # đã sắp xếp

    def test_mac_dinh_khong_tra_ve_ten_tep(self, tmp_path):
        (tmp_path / "bi_mat.xlsx").write_text("x", encoding="utf-8")
        kq = liet_ke_thu_muc_con(tmp_path)
        assert kq["thu_muc"] == []
        assert kq["tep"] == []

    def test_chi_lo_tep_dung_duoi_duoc_yeu_cau(self, tmp_path):
        (tmp_path / "DS_DANGVIEN.xlsx").write_text("x", encoding="utf-8")
        (tmp_path / "bi_mat.docx").write_text("x", encoding="utf-8")
        (tmp_path / "luong.pdf").write_text("x", encoding="utf-8")
        kq = liet_ke_thu_muc_con(tmp_path, {".xlsx"})
        assert kq["tep"] == ["DS_DANGVIEN.xlsx"]

    def test_loc_duoi_khong_phan_biet_hoa_thuong(self, tmp_path):
        (tmp_path / "MAIN.XLSX").write_text("x", encoding="utf-8")
        assert liet_ke_thu_muc_con(tmp_path, {".xlsx"})["tep"] == ["MAIN.XLSX"]

    def test_an_thu_muc_bat_dau_bang_dau_cham(self, tmp_path):
        (tmp_path / ".venv").mkdir()
        (tmp_path / "hien").mkdir()
        assert liet_ke_thu_muc_con(tmp_path)["thu_muc"] == ["hien"]

    def test_co_duong_dan_cha_de_di_len(self, tmp_path):
        assert liet_ke_thu_muc_con(tmp_path)["cha"] == str(tmp_path.parent)

    def test_bao_do_dai_de_giao_dien_canh_bao_som(self, tmp_path):
        assert liet_ke_thu_muc_con(tmp_path)["do_dai"] == len(str(tmp_path))

    def test_thu_muc_khong_ton_tai(self, tmp_path):
        with pytest.raises(LoiDuongDan) as e:
            liet_ke_thu_muc_con(tmp_path / "khong_co")
        assert "Không tìm thấy thư mục" in str(e.value)

    @pytest.mark.skipif(os.name != "nt", reason="Chỉ đúng trên Windows")
    def test_liet_ke_o_dia_windows(self):
        o = liet_ke_o_dia()
        assert "C:\\" in o
        assert all(Path(x).exists() for x in o)
