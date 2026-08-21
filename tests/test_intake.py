"""Test quét tệp scan, đặt tên và luân chuyển (bước 4–5).

Toàn bộ chạy trên thư mục tạm, không đụng tới dữ liệu thật của Viện.
Bộ dữ liệu thử dựng ngay trong test: tệp đúng + đủ 7 mã lỗi + 2 mã cảnh báo.
"""

import csv
from pathlib import Path

import pytest

from app.core import intake, rename
from app.core.intake import BO_QUA, COPY, LOI, BoiCanh
from app.core.mainbook import DongDangVien
from app.core.paths import LoiDuongDan

VP = "38.168.053.000.001"
QLKH = "38.168.053.000.002"


def dv(ma_id: str, ten: str, cccd: str, unit: str = VP, chi_bo: str = "Chi bộ Văn phòng"):
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


@pytest.fixture
def bc(so_cai):
    return BoiCanh.tu_so_cai(
        so_cai,
        {
            "Chi bộ Văn phòng": ("A", VP),
            "Chi bộ Phòng quản lý khoa học": ("B", QLKH),
        },
    )


@pytest.fixture
def kho(tmp_path):
    """Thư mục nguồn (scan) và thư mục gốc (đích), tách hẳn nhau."""
    nguon = tmp_path / "scan"
    dich = tmp_path / "kho"
    nguon.mkdir()
    dich.mkdir()
    return nguon, dich


def dat_tep(thu_muc: Path, ten: str, noi_dung: bytes = b"noi dung mau") -> Path:
    p = thu_muc / ten
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(noi_dung)
    return p


def thu_muc_cua(goc: Path, d: DongDangVien) -> Path:
    from app.core.tree import duong_dan_tuong_doi

    return goc / duong_dan_tuong_doi(d)


def chay_het(nguon, dich, bc):
    kq = intake.quet(nguon, bc)
    intake.lap_ke_hoach(kq, dich, bc)
    return intake.thuc_thi(kq)


class TestPhanTichTen:
    def test_bon_phan_co_tien_to_chi_bo(self):
        assert intake.phan_tich_ten("A.ID01.65.1.pdf") == ("A", "ID01", 65, 1, ".pdf")

    def test_ba_phan_khong_tien_to(self):
        assert intake.phan_tich_ten("ID01.65.1.pdf") == ("", "ID01", 65, 1, ".pdf")

    def test_chu_thuong_van_doc_duoc(self):
        assert intake.phan_tich_ten("a.id01.2.1.JPG") == ("A", "ID01", 2, 1, ".jpg")

    # --- hậu tố số thứ tự là TÙY CHỌN (đặc tả DactaKetLuan) -----------------

    def test_khong_co_hau_to_van_doc_duoc(self):
        """``A.ID01.65.pdf`` — ba phần bắt buộc, số thứ tự để app tự cấp."""
        assert intake.phan_tich_ten("A.ID01.65.pdf") == ("A", "ID01", 65, 0, ".pdf")

    def test_khong_tien_to_cung_khong_hau_to(self):
        assert intake.phan_tich_ten("ID01.65.pdf") == ("", "ID01", 65, 0, ".pdf")

    def test_bon_phan_khong_nham_giua_hai_cach_doc(self):
        """``A.ID01.65`` và ``ID01.65.1`` cùng 4 đoạn nhưng đọc khác nhau.

        Vị trí của mã ``IDxx`` là thứ phân biệt, nên không có ca nhập nhằng.
        """
        assert intake.phan_tich_ten("A.ID01.65.pdf")[0] == "A"
        assert intake.phan_tich_ten("A.ID01.65.pdf")[3] == 0
        assert intake.phan_tich_ten("ID01.65.1.pdf")[0] == ""
        assert intake.phan_tich_ten("ID01.65.1.pdf")[3] == 1

    @pytest.mark.parametrize(
        "ten",
        [
            "linh tinh.pdf",
            "Hồ sơ đảng viên Lư Xuân Bắc.doc",
            "A.ID01.65.1.2.pdf",
            "A.XX01.65.1.pdf",
            "A.ID01.abc.1.pdf",
            "ID01.pdf",           # thiếu mã tài liệu
            "65.1.pdf",           # thiếu mã đảng viên
            "A1.ID01.65.pdf",     # tiền tố chi bộ phải là chữ
        ],
    )
    def test_khong_tach_duoc(self, ten):
        assert intake.phan_tich_ten(ten) is None


class TestBoQuyTacLoi:
    """Mỗi mã lỗi E01–E07 phải có ít nhất một ca — D.3 bắt buộc."""

    def test_E01_ten_khong_dung_dang(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon, "Hồ sơ đảng viên Lư Xuân Bắc.doc")
        kq = intake.quet(nguon, bc)
        assert kq.tep[0].ma_loi == "E01"
        assert "A.ID01.65" in kq.tep[0].thong_bao

    def test_E02_khong_co_id_trong_so_cai(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon, "ID99.65.1.pdf")
        kq = intake.quet(nguon, bc)
        assert kq.tep[0].ma_loi == "E02"
        assert "ID01" in kq.tep[0].thong_bao      # nói rõ khoảng mã đang có

    def test_E03_ma_tai_lieu_ngoai_danh_muc(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon, "ID01.210.1.pdf")
        kq = intake.quet(nguon, bc)
        assert kq.tep[0].ma_loi == "E03"
        assert "104" in kq.tep[0].thong_bao

    def test_E04_tien_to_chi_bo_lech(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon, "B.ID01.65.1.pdf")     # ID01 ở chi bộ A
        kq = intake.quet(nguon, bc)
        assert kq.tep[0].ma_loi == "E04"
        assert "Chi bộ Văn phòng" in kq.tep[0].thong_bao

    def test_tien_to_dung_thi_khong_bao_loi(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon, "A.ID01.65.1.pdf")
        kq = intake.quet(nguon, bc)
        assert kq.tep[0].hop_le

    def test_E05_duoi_khong_cho_phep(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.zip")
        kq = intake.quet(nguon, bc)
        assert kq.tep[0].ma_loi == "E05"
        assert "giải nén" in kq.tep[0].thong_bao

    def test_E06_tep_rong(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"")
        kq = intake.quet(nguon, bc)
        assert kq.tep[0].ma_loi == "E06"

    def test_E07_dich_xuat_hien_tep_khac_giua_luc_dang_chay(self, kho, bc, so_cai):
        """Kế hoạch đã lập xong, ai đó chép tay một tệp trùng tên vào đích.

        Đây mới là đường thật dẫn tới E07: số thứ tự cấp nối tiếp nên tệp đã có
        từ trước không bao giờ va tên với tệp mới. Chỉ có tệp xuất hiện SAU khi
        lập kế hoạch mới đâm vào tên đã cấp.
        """
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"ban moi khac han")
        kq = intake.quet(nguon, bc)
        intake.lap_ke_hoach(kq, dich, bc)

        chen_ngang = Path(kq.tep[0].duong_dan_dich)
        chen_ngang.parent.mkdir(parents=True, exist_ok=True)
        chen_ngang.write_bytes(b"ban ai do chep tay vao")

        intake.thuc_thi(kq)
        assert kq.tep[0].ma_loi == "E07"
        assert kq.tep[0].hanh_dong == LOI
        assert chen_ngang.read_bytes() == b"ban ai do chep tay vao"

    def test_trung_ten_nhung_trung_ca_noi_dung_thi_im_lang_bo_qua(self, kho, bc):
        """Chạy lại lần hai không được đổ ra hàng nghìn dòng lỗi giả."""
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"y het nhau")
        kq = intake.quet(nguon, bc)
        intake.lap_ke_hoach(kq, dich, bc)

        chen_ngang = Path(kq.tep[0].duong_dan_dich)
        chen_ngang.parent.mkdir(parents=True, exist_ok=True)
        chen_ngang.write_bytes(b"y het nhau")

        intake.thuc_thi(kq)
        assert kq.tep[0].hanh_dong == BO_QUA
        assert not kq.tep[0].ma_loi

    def test_moi_thong_bao_deu_bang_tieng_viet_khong_co_ma_tran_trui(self, kho, bc):
        nguon, dich = kho
        for ten in ["linh tinh.pdf", "ID99.65.1.pdf", "ID01.210.1.pdf", "ID01.65.1.zip"]:
            dat_tep(nguon, ten)
        kq = intake.quet(nguon, bc)
        for t in kq.loi:
            assert len(t.thong_bao) > 40
            assert t.ma_loi not in t.thong_bao   # mã lỗi trần trụi là vô nghĩa với cán bộ


class TestCanhBao:
    def test_W01_trung_so_thu_tu(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"tep mot")
        dat_tep(nguon, "them/ID01.65.1.pdf", b"tep hai")
        kq = intake.quet(nguon, bc)
        assert all("W01" in [m for m, _ in t.canh_bao] for t in kq.tep)

    def test_W01_van_cap_so_lien_tuc_khong_mat_tep(self, kho, bc, so_cai):
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"tep mot")
        dat_tep(nguon, "them/ID01.65.1.pdf", b"tep hai")
        chay_het(nguon, dich, bc)
        co = sorted(p.name for p in thu_muc_cua(dich, so_cai[0]).iterdir())
        assert co == [rename.dat_ten(65, 1, ".pdf"), rename.dat_ten(65, 2, ".pdf")]

    def test_W02_nghi_scan_le_tung_trang(self, kho, bc):
        nguon, dich = kho
        for i in range(1, 7):
            dat_tep(nguon, f"ID01.65.{i}.pdf", f"trang {i}".encode())
        kq = intake.quet(nguon, bc)
        assert all("W02" in [m for m, _ in t.canh_bao] for t in kq.tep)

    def test_nam_tep_thi_chua_canh_bao(self, kho, bc):
        nguon, dich = kho
        for i in range(1, 6):
            dat_tep(nguon, f"ID01.65.{i}.pdf", f"trang {i}".encode())
        kq = intake.quet(nguon, bc)
        assert not any(t.canh_bao for t in kq.tep)


class TestDatTenVaDanhSo:
    def test_dem_3_chu_so_va_luon_co_so_thu_tu(self):
        assert rename.dat_ten(65, 1, ".pdf").startswith("065.")
        assert rename.dat_ten(1, 1, ".pdf").startswith("001.")
        assert rename.dat_ten(104, 1, ".pdf").startswith("104.")
        assert rename.dat_ten(2, 1, ".pdf").endswith(".1.pdf")

    def test_sap_theo_so_nguoi_scan_khai_khong_theo_thu_tu_he_thong_tep(self, kho, bc, so_cai):
        """Nạp 10, 2, 1 phải ra .1 .2 .3 đúng thứ tự người scan khai."""
        nguon, dich = kho
        for so in (10, 2, 1):
            dat_tep(nguon, f"ID01.65.{so}.pdf", f"noi dung {so}".encode())
        chay_het(nguon, dich, bc)

        thu_muc = thu_muc_cua(dich, so_cai[0])
        theo_so = {}
        for p in thu_muc.iterdir():
            theo_so[rename.phan_tich_ten_dich(p.name)[2]] = p.read_bytes()
        assert theo_so[1] == b"noi dung 1"
        assert theo_so[2] == b"noi dung 2"
        assert theo_so[3] == b"noi dung 10"

    def test_noi_tiep_so_thu_tu_da_co_trong_thu_muc(self, kho, bc, so_cai):
        nguon, dich = kho
        thu_muc = thu_muc_cua(dich, so_cai[0])
        thu_muc.mkdir(parents=True)
        (thu_muc / rename.dat_ten(65, 1, ".pdf")).write_bytes(b"da co tu truoc")

        dat_tep(nguon, "ID01.65.1.pdf", b"tep moi mot")
        dat_tep(nguon, "them/ID01.65.2.pdf", b"tep moi hai")
        chay_het(nguon, dich, bc)

        co = sorted(rename.phan_tich_ten_dich(p.name)[2] for p in thu_muc.iterdir())
        assert co == [1, 2, 3]

    def test_moi_dang_vien_dem_rieng(self, kho, bc, so_cai):
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"cua nguoi mot")
        dat_tep(nguon, "ID02.65.1.pdf", b"cua nguoi hai")
        chay_het(nguon, dich, bc)
        for d in so_cai[:2]:
            co = [p.name for p in thu_muc_cua(dich, d).iterdir()]
            assert co == [rename.dat_ten(65, 1, ".pdf")]

    def test_moi_ma_tai_lieu_dem_rieng(self, kho, bc, so_cai):
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"tai lieu 65")
        dat_tep(nguon, "ID01.2.1.pdf", b"tai lieu 2")
        chay_het(nguon, dich, bc)
        co = sorted(p.name for p in thu_muc_cua(dich, so_cai[0]).iterdir())
        assert co == [rename.dat_ten(2, 1, ".pdf"), rename.dat_ten(65, 1, ".pdf")]


class TestTachKhoChoChuyenPdf:
    def test_pdf_vao_kho_chinh_con_lai_vao_kho_cho(self, kho, bc, so_cai):
        nguon, dich = kho
        dat_tep(nguon, "ID01.2.1.pdf", b"ban pdf")
        dat_tep(nguon, "ID01.1.1.jpg", b"anh chup")
        dat_tep(nguon, "ID01.87.1.docx", b"van ban word")
        chay_het(nguon, dich, bc)

        thu_muc = thu_muc_cua(dich, so_cai[0])
        chinh = sorted(p.name for p in thu_muc.iterdir() if p.is_file())
        cho = sorted(p.name for p in (thu_muc / rename.KHO_CHO).iterdir())
        assert chinh == [rename.dat_ten(2, 1, ".pdf")]
        assert cho == [rename.dat_ten(1, 1, ".jpg"), rename.dat_ten(87, 1, ".docx")]

    def test_tep_kho_cho_van_dung_quy_tac_dat_ten(self, kho, bc, so_cai):
        nguon, dich = kho
        dat_tep(nguon, "ID01.1.1.jpg", b"anh chup")
        chay_het(nguon, dich, bc)
        ten = next((thu_muc_cua(dich, so_cai[0]) / rename.KHO_CHO).iterdir()).name
        assert ten == "001.Ly_lich_nguoi_xin_vao_Dang.1.jpg"

    def test_hai_kho_dem_chung_mot_day_so(self, kho, bc, so_cai):
        """Chuyển kho chờ sang PDF về sau không được trùng số với kho chính."""
        nguon, dich = kho
        dat_tep(nguon, "ID01.2.1.jpg", b"ban chup")
        chay_het(nguon, dich, bc)
        dat_tep(nguon, "them/ID01.2.2.pdf", b"ban pdf")
        chay_het(nguon, dich, bc)

        thu_muc = thu_muc_cua(dich, so_cai[0])
        assert [p.name for p in thu_muc.iterdir() if p.is_file()] == [
            rename.dat_ten(2, 2, ".pdf")
        ]
        assert [p.name for p in (thu_muc / rename.KHO_CHO).iterdir()] == [
            rename.dat_ten(2, 1, ".jpg")
        ]


class TestChayLaiNhieuLan:
    def test_chay_hai_lan_khong_nhan_ban_khong_bao_loi(self, kho, bc, so_cai):
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"noi dung")
        chay_het(nguon, dich, bc)
        kq2 = chay_het(nguon, dich, bc)

        assert kq2.tom_tat_loi == {}
        assert kq2.tep[0].hanh_dong == BO_QUA
        assert len(list(thu_muc_cua(dich, so_cai[0]).iterdir())) == 1

    def test_bo_qua_theo_noi_dung_du_ten_nguon_da_doi(self, kho, bc, so_cai):
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"noi dung")
        chay_het(nguon, dich, bc)

        (nguon / "ID01.65.1.pdf").unlink()
        dat_tep(nguon, "ID01.65.7.pdf", b"noi dung")   # cùng nội dung, khai số khác
        kq = intake.quet(nguon, bc)
        intake.lap_ke_hoach(kq, dich, bc)
        assert kq.tep[0].hanh_dong == BO_QUA
        assert len(list(thu_muc_cua(dich, so_cai[0]).iterdir())) == 1

    def test_tep_nguon_khong_bao_gio_bi_dong_toi(self, kho, bc):
        nguon, dich = kho
        p = dat_tep(nguon, "ID01.65.1.pdf", b"noi dung goc")
        truoc = sorted((x.name, x.read_bytes()) for x in nguon.rglob("*") if x.is_file())
        chay_het(nguon, dich, bc)
        sau = sorted((x.name, x.read_bytes()) for x in nguon.rglob("*") if x.is_file())
        assert truoc == sau
        assert p.exists()


class TestManifest:
    def test_du_bay_cot_va_mot_dong_moi_tep(self, kho, bc, tmp_path, monkeypatch):
        monkeypatch.setattr(intake, "THU_MUC_MANIFEST", tmp_path / "nhat_ky")
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"tep tot")
        dat_tep(nguon, "linh tinh.pdf", b"tep sai ten")
        kq = chay_het(nguon, dich, bc)

        with open(kq.manifest, encoding="utf-8-sig", newline="") as f:
            hang = list(csv.reader(f))
        assert hang[0] == [
            "duong_dan_goc", "ID", "Ma_tai_lieu", "duong_dan_dich",
            "ten_moi", "trang_thai", "thoi_diem",
        ]
        assert len(hang) == 3
        trang_thai = {h[5] for h in hang[1:]}
        assert trang_thai == {"da_chep", "loi_E01"}

    def test_lan_chay_thu_hai_ghi_bo_qua_trung(self, kho, bc, tmp_path, monkeypatch):
        monkeypatch.setattr(intake, "THU_MUC_MANIFEST", tmp_path / "nhat_ky")
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"tep tot")
        chay_het(nguon, dich, bc)
        kq2 = chay_het(nguon, dich, bc)
        with open(kq2.manifest, encoding="utf-8-sig", newline="") as f:
            hang = list(csv.reader(f))
        assert hang[1][5] == "bo_qua_trung"

    def test_khong_ghi_cccd_vao_manifest(self, kho, bc, tmp_path, monkeypatch):
        """Manifest chỉ định danh người bằng mã ID, không có cột CCCD."""
        monkeypatch.setattr(intake, "THU_MUC_MANIFEST", tmp_path / "nhat_ky")
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"tep tot")
        kq = chay_het(nguon, dich, bc)
        with open(kq.manifest, encoding="utf-8-sig", newline="") as f:
            tieu_de = next(csv.reader(f))
        assert not any("cccd" in c.lower() for c in tieu_de)


class TestSuaThuCong:
    def test_sua_xong_thi_tep_duoc_chep_dung_cho(self, kho, bc, so_cai):
        nguon, dich = kho
        p = dat_tep(nguon, "Hồ sơ đảng viên Lư Xuân Bắc.doc", b"noi dung word")
        kq = intake.quet(nguon, bc)
        assert kq.tep[0].ma_loi == "E01"

        intake.sua_thu_cong(kq, str(p), "ID02", 87, bc)
        intake.lap_ke_hoach(kq, dich, bc)
        intake.thuc_thi(kq)

        cho = thu_muc_cua(dich, so_cai[1]) / rename.KHO_CHO
        assert [x.name for x in cho.iterdir()] == [rename.dat_ten(87, 1, ".doc")]

    def test_tep_goc_khong_bi_doi_ten(self, kho, bc):
        nguon, dich = kho
        p = dat_tep(nguon, "Hồ sơ đảng viên Lư Xuân Bắc.doc", b"noi dung word")
        kq = intake.quet(nguon, bc)
        intake.sua_thu_cong(kq, str(p), "ID02", 87, bc)
        intake.lap_ke_hoach(kq, dich, bc)
        intake.thuc_thi(kq)
        assert p.exists() and p.name == "Hồ sơ đảng viên Lư Xuân Bắc.doc"

    def test_manifest_ghi_ro_la_sua_thu_cong(self, kho, bc, tmp_path, monkeypatch):
        monkeypatch.setattr(intake, "THU_MUC_MANIFEST", tmp_path / "nhat_ky")
        nguon, dich = kho
        p = dat_tep(nguon, "abc.doc", b"noi dung word")
        kq = intake.quet(nguon, bc)
        intake.sua_thu_cong(kq, str(p), "ID02", 87, bc)
        intake.lap_ke_hoach(kq, dich, bc)
        intake.thuc_thi(kq)
        with open(kq.manifest, encoding="utf-8-sig", newline="") as f:
            hang = list(csv.reader(f))
        assert hang[1][5] == "sua_thu_cong"

    def test_khong_sua_duoc_duoi_tep_la(self, kho, bc):
        nguon, dich = kho
        p = dat_tep(nguon, "ho so.zip", b"tep nen")
        kq = intake.quet(nguon, bc)
        with pytest.raises(LoiDuongDan) as e:
            intake.sua_thu_cong(kq, str(p), "ID01", 65, bc)
        assert "PDF" in str(e.value)

    def test_khong_sua_duoc_sang_ma_tai_lieu_la(self, kho, bc):
        nguon, dich = kho
        p = dat_tep(nguon, "abc.pdf", b"noi dung")
        kq = intake.quet(nguon, bc)
        with pytest.raises(LoiDuongDan):
            intake.sua_thu_cong(kq, str(p), "ID01", 999, bc)


class TestBoDuLieuThu:
    """Bộ 40 tệp — định nghĩa 'xong' của chặng M3."""

    @pytest.fixture
    def bo_40_tep(self, kho, bc, so_cai):
        nguon, dich = kho
        # 30 tệp đúng: 3 đảng viên × 10 mã tài liệu
        for i, d in enumerate(so_cai):
            for ma in range(1, 11):
                dat_tep(nguon, f"{d.id}.{ma}.1.pdf", f"noi dung {d.id} {ma}".encode())
        # 10 tệp lỗi, phủ đủ 6 mã lỗi chấm được lúc quét
        dat_tep(nguon, "loi/Hồ sơ đảng viên.doc", b"x")            # E01
        dat_tep(nguon, "loi/danh sach.docx", b"x")                 # E01
        dat_tep(nguon, "loi/ID99.65.1.pdf", b"x")                  # E02
        dat_tep(nguon, "loi/ID98.65.1.pdf", b"x")                  # E02
        dat_tep(nguon, "loi/ID01.210.1.pdf", b"x")                 # E03
        dat_tep(nguon, "loi/ID01.0.1.pdf", b"x")                   # E03
        dat_tep(nguon, "loi/B.ID01.65.1.pdf", b"x")                # E04
        dat_tep(nguon, "loi/ID01.65.1.zip", b"x")                  # E05
        dat_tep(nguon, "loi/ID01.65.1.rar", b"x")                  # E05
        dat_tep(nguon, "loi/ID02.65.1.pdf", b"")                   # E06
        return nguon, dich

    def test_phan_loai_dung_30_hop_le_10_loi(self, bo_40_tep, bc):
        nguon, dich = bo_40_tep
        kq = intake.quet(nguon, bc)
        assert len(kq.tep) == 40
        assert len(kq.hop_le) == 30
        assert kq.tom_tat_loi == {"E01": 2, "E02": 2, "E03": 2, "E04": 1, "E05": 2, "E06": 1}

    def test_chep_du_30_tep_va_manifest_du_40_dong(
        self, bo_40_tep, bc, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(intake, "THU_MUC_MANIFEST", tmp_path / "nhat_ky")
        nguon, dich = bo_40_tep
        kq = chay_het(nguon, dich, bc)
        assert kq.tom_tat_hanh_dong[COPY] == 30
        assert sum(1 for p in dich.rglob("*") if p.is_file()) == 30
        with open(kq.manifest, encoding="utf-8-sig", newline="") as f:
            assert len(list(csv.reader(f))) == 41    # 1 tiêu đề + 40 tệp

    def test_tep_loi_o_lai_thu_muc_nguon(self, bo_40_tep, bc):
        nguon, dich = bo_40_tep
        chay_het(nguon, dich, bc)
        assert sum(1 for p in nguon.rglob("*") if p.is_file()) == 40


class TestAnToan:
    def test_chua_lap_ke_hoach_thi_khong_thuc_thi_duoc(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf")
        kq = intake.quet(nguon, bc)
        with pytest.raises(LoiDuongDan):
            intake.thuc_thi(kq)

    def test_khong_quet_vao_kho_cho_cua_chinh_minh(self, kho, bc):
        """Thư mục _CHO_CHUYEN_PDF là kho đích, không phải nguồn để quét lại."""
        nguon, dich = kho
        dat_tep(nguon, f"{rename.KHO_CHO}/001.Ly_lich_nguoi_xin_vao_Dang.1.jpg")
        kq = intake.quet(nguon, bc)
        assert kq.tep == []

    def test_do_dung_luong_o_dia(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon, "ID01.65.1.pdf", b"x" * 1000)
        kq = intake.quet(nguon, bc)
        intake.lap_ke_hoach(kq, dich, bc)
        assert kq.tong_byte == 1000
        assert kq.byte_con_trong > 0
        assert kq.du_cho_trong


class TestHauToSoThuTuTuyChon:
    """Đặc tả DactaKetLuan: nhận diện chỉ cần [Đơn vị].[ID].[Mã tài liệu].

    Lý do bỏ được hậu tố: hai tệp cùng mã trong một thư mục scan thì chính
    Windows đã bắt người scan đổi tên ngay lúc lưu, nên chuyện "trùng mã" không
    lọt được vào đây. App vẫn tự cấp số nối tiếp như cũ.
    """

    def test_khong_hau_to_van_duoc_cap_so_1(self, kho, bc, so_cai):
        nguon, dich = kho
        dat_tep(nguon, "A.ID01.65.pdf")
        chay_het(nguon, dich, bc)
        assert (thu_muc_cua(dich, so_cai[0]) / rename.dat_ten(65, 1, ".pdf")).is_file()

    def test_nhieu_tep_khong_hau_to_duoc_cap_so_noi_tiep(self, kho, bc, so_cai):
        nguon, dich = kho
        # Cùng một tên chỉ tồn tại được nếu nằm ở ba thư mục con khác nhau —
        # đúng như ngoài đời, vì trong một thư mục Windows đã chặn trùng tên.
        for i in range(3):
            dat_tep(nguon / f"tap{i}", "A.ID01.65.pdf", f"noi dung {i}".encode())
        chay_het(nguon, dich, bc)
        co = sorted(
            p.name for p in thu_muc_cua(dich, so_cai[0]).iterdir() if p.is_file()
        )
        assert co == [rename.dat_ten(65, i, ".pdf") for i in (1, 2, 3)]

    def test_tep_co_khai_duoc_uu_tien_truoc_tep_khong_khai(self, kho, bc, so_cai):
        """Người scan đã đánh số thì thứ tự đó phải được tôn trọng.

        Tệp không khai xếp sau, nếu không nó chiếm mất số 1 của tệp đã khai.
        """
        nguon, dich = kho
        dat_tep(nguon, "A.ID01.65.1.pdf", b"tep da khai so 1")
        dat_tep(nguon / "them", "A.ID01.65.pdf", b"tep khong khai")
        chay_het(nguon, dich, bc)
        thu_muc = thu_muc_cua(dich, so_cai[0])
        assert (thu_muc / rename.dat_ten(65, 1, ".pdf")).read_bytes() == b"tep da khai so 1"
        assert (thu_muc / rename.dat_ten(65, 2, ".pdf")).read_bytes() == b"tep khong khai"

    def test_khong_bao_W01_gia_cho_tep_khong_khai(self, kho, bc):
        """Trước đây so_khai == 0 bị đếm như "cùng khai số 0" ⇒ W01 hàng loạt."""
        nguon, dich = kho
        for i in range(3):
            dat_tep(nguon / f"tap{i}", "A.ID01.65.pdf", f"noi dung {i}".encode())
        kq = intake.quet(nguon, bc)
        assert all(not t.canh_bao for t in kq.tep), [t.canh_bao for t in kq.tep]

    def test_van_bao_W01_khi_thuc_su_khai_trung(self, kho, bc):
        nguon, dich = kho
        dat_tep(nguon / "tap1", "A.ID01.65.1.pdf", b"mot")
        dat_tep(nguon / "tap2", "A.ID01.65.1.pdf", b"hai")
        kq = intake.quet(nguon, bc)
        assert all(any(m == "W01" for m, _ in t.canh_bao) for t in kq.tep)

    def test_bo_ca_tien_to_lan_hau_to(self, kho, bc, so_cai):
        nguon, dich = kho
        dat_tep(nguon, "ID03.2.pdf")
        chay_het(nguon, dich, bc)
        assert (thu_muc_cua(dich, so_cai[2]) / rename.dat_ten(2, 1, ".pdf")).is_file()

    def test_tien_to_chi_bo_sai_van_bao_E04_khi_khong_co_hau_to(self, kho, bc):
        """Bỏ hậu tố không được làm mất khả năng bắt lỗi tiền tố lệch."""
        nguon, dich = kho
        dat_tep(nguon, "B.ID01.65.pdf")
        kq = intake.quet(nguon, bc)
        assert kq.tep[0].ma_loi == "E04"
