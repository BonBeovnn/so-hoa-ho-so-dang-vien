"""Test nhật ký và gói chẩn đoán (M5).

Điểm quan trọng nhất: gói chẩn đoán rất dễ bị chuyển tiếp qua email, nên tuyệt
đối không được mang theo số CCCD của đảng viên.
"""

import io
import zipfile

import pytest

from app.core import chan_doan, nhat_ky
from app.core.phien import CauHinh

CCCD = "099003330003"
THU_MUC_NGUOI = f"{CCCD}_NguyenDinhHao"


@pytest.fixture
def log_tam(tmp_path, monkeypatch):
    tep = tmp_path / "app.log"
    monkeypatch.setattr(nhat_ky, "TEP_LOG", tep)
    monkeypatch.setattr(chan_doan, "TEP_LOG", tep)
    return tep


class TestCheSoDinhDanh:
    def test_che_so_cccd_12_chu_so(self):
        assert nhat_ky.che_so_dinh_danh(CCCD) == "099*********"

    def test_van_giu_ten_nguoi_de_con_lan_ra_duoc(self):
        ra = nhat_ky.che_so_dinh_danh(THU_MUC_NGUOI)
        assert "NguyenDinhHao" in ra
        assert CCCD not in ra

    def test_che_ca_khi_nam_giua_duong_dan(self):
        duong_dan = rf"D:\SoHoa\38.168.053.000.001\{THU_MUC_NGUOI}\002.Ly_lich.1.pdf"
        ra = nhat_ky.che_so_dinh_danh(duong_dan)
        assert CCCD not in ra
        assert "002.Ly_lich.1.pdf" in ra
        assert "38.168.053.000.001" in ra      # mã tổ chức đảng không bị đụng

    def test_khong_che_so_ngan(self):
        """Dấu thời gian 8 chữ số và mã tài liệu phải giữ nguyên."""
        assert nhat_ky.che_so_dinh_danh("20260820 mã 104") == "20260820 mã 104"

    def test_che_ca_so_the_dang_9_chu_so(self):
        assert nhat_ky.che_so_dinh_danh("123456789") == "123******"


class TestGhiNhatKy:
    def test_ghi_duoc_mot_dong(self, log_tam):
        nhat_ky.ghi("info", "Bước 1: 85 đảng viên")
        noi_dung = log_tam.read_text(encoding="utf-8")
        assert "[info]" in noi_dung
        assert "Bước 1: 85 đảng viên" in noi_dung

    def test_nhat_ky_khong_bao_gio_chua_cccd(self, log_tam):
        nhat_ky.ghi("info", f"Đã chép vào {THU_MUC_NGUOI}")
        assert CCCD not in log_tam.read_text(encoding="utf-8")

    def test_khong_lam_sap_app_khi_khong_ghi_duoc(self, tmp_path, monkeypatch):
        """Nhật ký hỏng thì kệ nó, không được kéo cả ứng dụng sập theo."""
        tep = tmp_path / "khong_ton_tai"
        tep.write_text("day la mot tep", encoding="utf-8")
        monkeypatch.setattr(nhat_ky, "TEP_LOG", tep / "app.log")
        nhat_ky.ghi("info", "thu ghi")      # không được ném ngoại lệ

    def test_xoay_vong_khi_qua_lon(self, log_tam, monkeypatch):
        monkeypatch.setattr(nhat_ky, "GIOI_HAN_BYTE", 200)
        for i in range(40):
            nhat_ky.ghi("info", f"dong so {i} " + "x" * 20)
        assert log_tam.with_suffix(".log.1").exists()
        assert log_tam.stat().st_size < 2000

    def test_doc_gan_day_khi_chua_co_nhat_ky(self, log_tam):
        assert "chưa có nhật ký" in nhat_ky.doc_gan_day()


class TestGoiChanDoan:
    def _mo_goi(self, du_lieu: bytes) -> zipfile.ZipFile:
        return zipfile.ZipFile(io.BytesIO(du_lieu))

    def test_du_cac_tep_can_thiet(self, log_tam, tmp_path):
        nhat_ky.ghi("info", "thu mot dong")
        goi = self._mo_goi(chan_doan.dung_goi(CauHinh(), "trạng thái thử", cong=8000))
        ten = set(goi.namelist())
        assert {"thong_tin.txt", "trang_thai.txt", "duong_dan.txt",
                "cay_thu_muc.txt", "app.log", "DOC_TOI.txt"} <= ten

    def test_thong_tin_co_phien_ban_python_va_thu_vien(self, log_tam):
        goi = self._mo_goi(chan_doan.dung_goi(CauHinh(), "", cong=8877))
        chu = goi.read("thong_tin.txt").decode("utf-8")
        assert "Python" in chu and "fastapi" in chu
        assert "8877" in chu

    def test_toan_bo_goi_khong_chua_cccd(self, log_tam, tmp_path, monkeypatch):
        """Kiểm tra thô bạo: dò chuỗi CCCD trong mọi tệp của gói."""
        nhat_ky.ghi("info", f"chép sang {THU_MUC_NGUOI}")
        kho = tmp_path / "kho" / "38.168.053" / "38.168.053.000.001" / THU_MUC_NGUOI
        kho.mkdir(parents=True)
        (kho / "002.Ly_lich_dang_vien.1.pdf").write_bytes(b"x")

        monkeypatch.setattr(chan_doan, "THU_MUC_DU_LIEU", tmp_path / "du_lieu")
        (tmp_path / "du_lieu").mkdir()
        (tmp_path / "du_lieu" / "manifest_20260820_120000.csv").write_text(
            f"duong_dan_goc,ID\nD:\\scan\\a.pdf,ID01\nD:\\kho\\{THU_MUC_NGUOI}\\x.pdf,ID02\n",
            encoding="utf-8-sig",
        )

        ch = CauHinh(duong_dan_goc=str(tmp_path / "kho"))
        goi = self._mo_goi(chan_doan.dung_goi(ch, f"đường dẫn {THU_MUC_NGUOI}"))
        for ten in goi.namelist():
            assert CCCD.encode() not in goi.read(ten), ten

    def test_co_manifest_moi_nhat(self, log_tam, tmp_path, monkeypatch):
        thu_muc = tmp_path / "du_lieu"
        thu_muc.mkdir()
        for ten in ("manifest_20260820_100000.csv", "manifest_20260820_110000.csv"):
            (thu_muc / ten).write_text("duong_dan_goc,ID\n", encoding="utf-8-sig")
        monkeypatch.setattr(chan_doan, "THU_MUC_DU_LIEU", thu_muc)

        goi = self._mo_goi(chan_doan.dung_goi(CauHinh(), ""))
        assert "manifest_20260820_110000.csv" in goi.namelist()
        assert "manifest_20260820_100000.csv" not in goi.namelist()

    def test_dem_dung_so_tep_trong_kho(self, log_tam, tmp_path):
        kho = tmp_path / "kho" / "38.168.053.000.001" / "NguyenVanA"
        kho.mkdir(parents=True)
        for i in range(3):
            (kho / f"00{i + 1}.Tai_lieu.1.pdf").write_bytes(b"x")

        goi = self._mo_goi(
            chan_doan.dung_goi(CauHinh(duong_dan_goc=str(tmp_path / "kho")), "")
        )
        chu = goi.read("cay_thu_muc.txt").decode("utf-8")
        assert "Tổng tệp     : 3" in chu

    def test_bao_ro_khi_chua_co_kho(self, log_tam):
        """Đường dẫn rỗng KHÔNG được hiểu thành thư mục hiện hành.

        Path("") ra thành "." — bản đầu vì thế đi liệt kê cả thư mục app lẫn
        .venv, cho ra gần 4.000 dòng vô nghĩa trong gói gửi đi.
        """
        goi = self._mo_goi(chan_doan.dung_goi(CauHinh(), ""))
        chu = goi.read("cay_thu_muc.txt").decode("utf-8")
        assert "Chưa có kho hồ sơ" in chu
        assert "site-packages" not in chu

    def test_ten_goi_co_dau_thoi_gian(self):
        ten = chan_doan.ten_goi()
        assert ten.startswith("GoiChanDoan_") and ten.endswith(".zip")
