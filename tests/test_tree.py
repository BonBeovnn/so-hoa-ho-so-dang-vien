"""Test tạo cây thư mục 3 cấp: chạy lại an toàn, đổi tên, chuyển chi bộ."""

from pathlib import Path

import pytest

from app.core.mainbook import DongDangVien
from app.core.tree import (
    CHUYEN_CHI_BO,
    DA_CO,
    DOI_TEN,
    LOI,
    TAO_MOI,
    dem_tep_ben_trong,
    do_dai_tuong_doi_lon_nhat,
    duong_dan_tuong_doi,
    lap_ke_hoach,
    thuc_thi,
)

# 1.Dacta_fixV1: ma to chuc dang PHAI co dau cham.
CO_SO = "38.168.053"
VP = "38.168.053.000.001"
QLKH = "38.168.053.000.002"


def dv(ma_id, ten, folder, unit=VP):
    return DongDangVien(
        id=ma_id, so_dong=int(ma_id[2:]), name=ten,
        name_convert=folder.split("_")[-1], folder_name=folder, unit_folder=unit,
    )


NHU = dv("ID01", "SẦM THỊ QUỲNH NHƯ", "099001110001_SamThiQuynhNhu")
HAI = dv("ID02", "NGUYỄN ĐÌNH HẢO", "099003330003_NguyenDinhHao")
NHUNG = dv("ID58", "TRẦN THỊ HỒNG NHUẬN", "099002220002_TranThiHongNhuan")


def tao_tep(thu_muc: Path, *ten: str) -> None:
    thu_muc.mkdir(parents=True, exist_ok=True)
    for t in ten:
        (thu_muc / t).write_text("noi dung", encoding="utf-8")


class TestDoDaiTuongDoi:
    def test_tinh_du_ca_cap_dang_bo_co_so(self):
        assert do_dai_tuong_doi_lon_nhat([NHU]) == (
            len(CO_SO) + 1 + len(VP) + 1 + len(NHU.folder_name)
        )

    def test_so_lieu_that_cua_Vien_la_59(self):
        """10 (38.168.053) + 1 + 18 (chi bo) + 1 + 29 (ho ten dai nhat) = 59."""
        assert do_dai_tuong_doi_lon_nhat([NHUNG]) == 59

    def test_danh_sach_rong(self):
        assert do_dai_tuong_doi_lon_nhat([]) == 0

    def test_lay_dong_dai_nhat(self):
        assert do_dai_tuong_doi_lon_nhat([HAI, NHUNG]) == max(
            len(str(duong_dan_tuong_doi(HAI))), len(str(duong_dan_tuong_doi(NHUNG)))
        )

    def test_bo_qua_dong_thieu_ma_chi_bo(self):
        assert do_dai_tuong_doi_lon_nhat([dv("ID99", "AI ĐÓ", "9_AiDo", "")]) == 0


class TestLapKeHoachLanDau:
    def test_thu_muc_goc_rong_thi_tat_ca_deu_tao_moi(self, tmp_path):
        kh = lap_ke_hoach(tmp_path, [NHU, HAI])
        assert kh.tom_tat[TAO_MOI] == 2
        assert kh.don_vi_tao_moi == [VP]
        assert kh.can_thay_doi and not kh.co_loi

    def test_khong_ghi_gi_len_dia(self, tmp_path):
        lap_ke_hoach(tmp_path, [NHU, HAI])
        assert list(tmp_path.iterdir()) == []

    def test_gom_dung_don_vi_khong_trung_lap(self, tmp_path):
        kh = lap_ke_hoach(tmp_path, [NHU, HAI, dv("ID03", "X Y", "3_XY", QLKH)])
        assert sorted(kh.don_vi_tao_moi) == [VP, QLKH]


class TestThucThi:
    def test_tao_dung_cay_ba_cap(self, tmp_path):
        thuc_thi(lap_ke_hoach(tmp_path, [NHU, HAI]))
        assert (tmp_path / CO_SO / VP / NHU.folder_name).is_dir()
        assert (tmp_path / CO_SO / VP / HAI.folder_name).is_dir()

    def test_chay_lai_lan_hai_khong_tao_them_gi(self, tmp_path):
        thuc_thi(lap_ke_hoach(tmp_path, [NHU, HAI]))
        kh2 = lap_ke_hoach(tmp_path, [NHU, HAI])
        assert kh2.tom_tat[DA_CO] == 2
        assert kh2.tom_tat[TAO_MOI] == 0
        assert kh2.don_vi_tao_moi == []
        assert not kh2.can_thay_doi

    def test_chay_lai_khong_dung_toi_tep_ben_trong(self, tmp_path):
        thuc_thi(lap_ke_hoach(tmp_path, [NHU]))
        tao_tep(tmp_path / CO_SO / VP / NHU.folder_name, "002.Ly_lich_dang_vien.1.pdf")
        thuc_thi(lap_ke_hoach(tmp_path, [NHU]))
        assert (tmp_path / CO_SO / VP / NHU.folder_name / "002.Ly_lich_dang_vien.1.pdf").exists()

    def test_bao_so_tep_ben_trong_thu_muc_da_co(self, tmp_path):
        thuc_thi(lap_ke_hoach(tmp_path, [NHU]))
        tao_tep(tmp_path / CO_SO / VP / NHU.folder_name, "a.pdf", "b.pdf")
        kh = lap_ke_hoach(tmp_path, [NHU])
        assert kh.muc[0].so_tep_ben_trong == 2


class TestDoiTenThuMucSai:
    def test_ca_ID58_doi_ten_va_giu_nguyen_tep(self, tmp_path):
        """Dữ liệu bẩn thật: thư mục đã tạo theo tên còn dấu, có tệp bên trong."""
        ten_cu = "099002220002_TrànThịHòngNhuận"
        tao_tep(tmp_path / CO_SO / VP / ten_cu, "002.Ly_lich_dang_vien.1.pdf", "005.QD.1.pdf")

        kh = lap_ke_hoach(tmp_path, [NHUNG], {"ID58": ten_cu})
        assert kh.tom_tat[DOI_TEN] == 1
        assert kh.muc[0].so_tep_ben_trong == 2
        assert "sai chuẩn" in kh.muc[0].ghi_chu

        thuc_thi(kh)
        moi = tmp_path / CO_SO / VP / NHUNG.folder_name
        assert moi.is_dir()
        assert not (tmp_path / CO_SO / VP / ten_cu).exists()
        assert (moi / "002.Ly_lich_dang_vien.1.pdf").exists()
        assert (moi / "005.QD.1.pdf").exists()

    def test_khong_biet_ten_cu_thi_coi_nhu_tao_moi(self, tmp_path):
        tao_tep(tmp_path / CO_SO / VP / "099002220002_TrànThịHòngNhuận", "a.pdf")
        kh = lap_ke_hoach(tmp_path, [NHUNG])  # không truyền tên cũ
        assert kh.tom_tat[TAO_MOI] == 1


class TestChuyenChiBo:
    def test_dang_vien_chuyen_sinh_hoat_thi_thu_muc_di_theo(self, tmp_path):
        cu = dv("ID02", "NGUYỄN ĐÌNH HẢO", HAI.folder_name, VP)
        thuc_thi(lap_ke_hoach(tmp_path, [cu]))
        tao_tep(tmp_path / CO_SO / VP / HAI.folder_name, "002.Ly_lich_dang_vien.1.pdf")

        moi = dv("ID02", "NGUYỄN ĐÌNH HẢO", HAI.folder_name, QLKH)
        kh = lap_ke_hoach(tmp_path, [moi])
        assert kh.tom_tat[CHUYEN_CHI_BO] == 1
        assert kh.muc[0].so_tep_ben_trong == 1

        thuc_thi(kh)
        assert (tmp_path / CO_SO / QLKH / HAI.folder_name / "002.Ly_lich_dang_vien.1.pdf").exists()
        assert not (tmp_path / CO_SO / VP / HAI.folder_name).exists()

    def test_khong_de_lai_thu_muc_rong_o_chi_bo_cu(self, tmp_path):
        thuc_thi(lap_ke_hoach(tmp_path, [HAI]))
        moi = dv("ID02", "NGUYỄN ĐÌNH HẢO", HAI.folder_name, QLKH)
        thuc_thi(lap_ke_hoach(tmp_path, [moi]))
        assert not (tmp_path / CO_SO / VP / HAI.folder_name).exists()


class TestTinhHuongMoHo:
    def test_ton_tai_dong_thoi_hai_thu_muc_thi_bao_loi_khong_tu_gop(self, tmp_path):
        ten_cu = "099002220002_TrànThịHòngNhuận"
        tao_tep(tmp_path / CO_SO / VP / ten_cu, "cu.pdf")
        tao_tep(tmp_path / CO_SO / VP / NHUNG.folder_name, "moi.pdf")

        kh = lap_ke_hoach(tmp_path, [NHUNG], {"ID58": ten_cu})
        assert kh.co_loi
        assert "không tự gộp" in kh.muc[0].ghi_chu

        thuc_thi(kh)
        assert (tmp_path / CO_SO / VP / ten_cu / "cu.pdf").exists()  # không đụng vào
        assert (tmp_path / CO_SO / VP / NHUNG.folder_name / "moi.pdf").exists()

    def test_thieu_ma_chi_bo_thi_bao_loi_khong_chan_nguoi_khac(self, tmp_path):
        thieu = dv("ID99", "AI ĐÓ", "9_AiDo", "")
        kh = lap_ke_hoach(tmp_path, [NHU, thieu])
        assert kh.tom_tat[LOI] == 1
        assert kh.tom_tat[TAO_MOI] == 1  # người còn lại vẫn được tạo
        thuc_thi(kh)
        assert (tmp_path / CO_SO / VP / NHU.folder_name).is_dir()

    def test_ma_chi_bo_sai_dinh_dang_bi_chan(self, tmp_path):
        xau = dv("ID99", "AI ĐÓ", "9_AiDo", "38.168")
        kh = lap_ke_hoach(tmp_path, [xau])
        assert kh.tom_tat[LOI] == 1
        assert "14 chữ số" in kh.muc[0].ghi_chu

    def test_ten_thu_muc_nguy_hiem_bi_chan(self, tmp_path):
        xau = dv("ID99", "AI ĐÓ", "..")
        kh = lap_ke_hoach(tmp_path, [xau])
        assert kh.tom_tat[LOI] == 1

    def test_nguon_bien_mat_giua_chung_thi_bao_loi_ro_rang(self, tmp_path):
        ten_cu = "099002220002_TrànThịHòngNhuận"
        tao_tep(tmp_path / CO_SO / VP / ten_cu, "a.pdf")
        kh = lap_ke_hoach(tmp_path, [NHUNG], {"ID58": ten_cu})
        import shutil

        shutil.rmtree(tmp_path / CO_SO / VP / ten_cu)  # ai đó xóa trong lúc chờ duyệt
        thuc_thi(kh)
        assert kh.muc[0].hanh_dong == LOI
        assert "Không còn tìm thấy thư mục nguồn" in kh.muc[0].ghi_chu


    def test_dich_dung_nhung_con_thu_muc_o_chi_bo_khac_thi_bao_loi(self, tmp_path):
        """Hoi quy 20/8/2026: truoc khi sua, ham dung ngay o thu muc dich va
        bao "da co, bo qua" — bo roi vinh vien tep nam trong thu muc chi bo cu."""
        tao_tep(tmp_path / CO_SO / QLKH / HAI.folder_name, "bi_bo_roi.pdf")
        tao_tep(tmp_path / CO_SO / VP / HAI.folder_name, "dung_cho.pdf")

        kh = lap_ke_hoach(tmp_path, [HAI])
        assert kh.co_loi
        assert kh.muc[0].so_tep_ben_trong == 1
        assert "nhieu thu muc" in kh.muc[0].ghi_chu.replace("ề", "e").lower() or "đồng thời" in kh.muc[0].ghi_chu

        thuc_thi(kh)
        assert (tmp_path / CO_SO / QLKH / HAI.folder_name / "bi_bo_roi.pdf").exists()
        assert (tmp_path / CO_SO / VP / HAI.folder_name / "dung_cho.pdf").exists()

    def test_hai_thu_muc_cu_o_hai_chi_bo_khac_nhau(self, tmp_path):
        tao_tep(tmp_path / CO_SO / QLKH / HAI.folder_name, "a.pdf")
        tao_tep(tmp_path / CO_SO / "38.168.053.000.003" / HAI.folder_name, "b.pdf")
        kh = lap_ke_hoach(tmp_path, [HAI])
        assert kh.co_loi
        assert kh.muc[0].so_tep_ben_trong == 2


class TestDemTepBenTrong:
    def test_dem_ca_thu_muc_con(self, tmp_path):
        tao_tep(tmp_path / "a", "1.pdf", "2.pdf")
        tao_tep(tmp_path / "a" / "_CHO_CHUYEN_PDF", "3.jpg")
        assert dem_tep_ben_trong(tmp_path / "a") == 3

    def test_thu_muc_khong_ton_tai(self, tmp_path):
        assert dem_tep_ben_trong(tmp_path / "khong_co") == 0


class TestDuLieuThat:
    def test_tao_du_7_chi_bo_va_85_dang_vien(self, tmp_path):
        from app.core.mainbook import doc_chi_bo, doc_ds_dangvien, dong_bo

        goc = Path(__file__).resolve().parents[2]
        ds, main = goc / "Without_APP" / "DS_DANGVIEN.xlsx", goc / "With_APP" / "MAIN.xlsx"
        if not ds.exists():
            pytest.skip("Không tìm thấy DS_DANGVIEN.xlsx")

        kq = dong_bo(doc_ds_dangvien(ds), doc_chi_bo(main), [])
        kh = thuc_thi(lap_ke_hoach(tmp_path, kq.dong))

        assert not kh.co_loi, [m.ghi_chu for m in kh.muc if m.hanh_dong == LOI]
        assert kh.tom_tat[TAO_MOI] == 85
        assert [p.name for p in tmp_path.iterdir() if p.is_dir()] == [CO_SO]
        assert len([p for p in (tmp_path / CO_SO).iterdir() if p.is_dir()]) == 7
        assert sum(1 for p in tmp_path.rglob("*") if p.is_dir()) == 1 + 7 + 85

        # Chạy lại phải im lặng hoàn toàn.
        lai = lap_ke_hoach(tmp_path, kq.dong)
        assert lai.tom_tat[DA_CO] == 85 and not lai.can_thay_doi
