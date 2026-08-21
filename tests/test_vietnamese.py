"""Test chuẩn hóa tiếng Việt.

Các ca kiểm lấy trực tiếp từ dữ liệu thật trong With_APP/MAIN.xlsx,
đặc biệt là ca ID58 — dòng dữ liệu đang hỏng trong tệp gốc.
"""

import unicodedata

import pytest

from app.core.vietnamese import (
    LoiMaToChuc,
    bo_dau,
    chuan_hoa_ma_co_so,
    chuan_hoa_ma_to_chuc,
    con_dau,
    dung_folder_name,
    ma_dang_bo_co_so,
    pascal_case,
    slug_tai_lieu,
    thuoc_dang_bo_co_so,
)

# Gia tri Folder_name DANG BI HONG trong With_APP/MAIN.xlsx dong ID58.
# Viet bang escape de khong phu thuoc cach trinh soan thao chuan hoa Unicode.
# Doc la: "Tran Thi Hong Nhuan" nhung con sot dau huyen va dau nang.
HONG_NHUNG_HONG = "TrànThịHòngNhuan"


class TestBoDau:
    def test_chu_D_gach_ngang_la_ca_bien_quan_trong_nhat(self):
        """Đ/đ là chữ cái riêng, NFD không tách được. Đây là lỗi dễ mắc nhất."""
        assert bo_dau("Đ") == "D"
        assert bo_dau("đ") == "d"

    def test_chung_minh_NFD_don_thuan_la_sai(self):
        """Ghim lại bằng chứng: công thức NFD phổ biến KHÔNG xử lý được Đ."""
        chi_dung_nfd = "".join(
            c
            for c in unicodedata.normalize("NFD", "NGUYỄN ĐÌNH HẢO")
            if unicodedata.category(c) != "Mn"
        )
        assert chi_dung_nfd == "NGUYEN ĐINH HAO"  # còn sót Đ
        assert bo_dau("NGUYỄN ĐÌNH HẢO") == "NGUYEN DINH HAO"  # hàm của ta đúng

    @pytest.mark.parametrize(
        "vao,ra",
        [
            ("NGUYỄN ĐÌNH HẢO", "NGUYEN DINH HAO"),
            ("SẦM THỊ QUỲNH NHƯ", "SAM THI QUYNH NHU"),
            ("ĐỖ QUỐC CHIẾN", "DO QUOC CHIEN"),
            ("LƯU THỊ HÂN", "LUU THI HAN"),
            ("TRẦN THỊ HỒNG NHUẬN", "TRAN THI HONG NHUAN"),
            ("HÀ THỊ TÚ ÁNH", "HA THI TU ANH"),
        ],
    )
    def test_ten_that_tu_du_lieu(self, vao, ra):
        assert bo_dau(vao) == ra

    def test_nguyen_am_hai_dau(self):
        """Ầ = A + mũ + huyền. Công cụ cũ chỉ bóc được mũ nên còn sót huyền."""
        assert bo_dau("Ầ") == "A"
        assert bo_dau("Ệ") == "E"
        assert bo_dau("Ộ") == "O"
        assert bo_dau("Ự") == "U"
        assert bo_dau("Ỡ") == "O"

    def test_du_29_chu_cai_tieng_viet(self):
        bang = "AĂÂBCDĐEÊGHIKLMNOÔƠPQRSTUƯVXY"
        assert len(bang) == 29
        assert bo_dau(bang) == "AAABCDDEEGHIKLMNOOOPQRSTUUVXY"

    def test_giu_nguyen_khoang_trang_va_hoa_thuong(self):
        assert bo_dau("Quyết định kết nạp đảng viên") == "Quyet dinh ket nap dang vien"

    def test_chuoi_rong(self):
        assert bo_dau("") == ""
        assert bo_dau(None) == ""


class TestConDau:
    def test_chuoi_sach(self):
        assert con_dau("NguyenDinhHao") == []

    def test_bat_duoc_du_lieu_hong_ID58_dang_NFD(self):
        """Gia tri that trong MAIN.xlsx dong ID58 luu o dang NFD (dau tach roi).

        Dung bang normalize() thay vi go truc tiep, vi trinh soan thao co the
        tu chuan hoa ky tu ve NFC va lam ca kiem mat y nghia.
        """
        nfd = unicodedata.normalize("NFD", HONG_NHUNG_HONG)
        assert con_dau(nfd) == ["̀", "̣"]  # dau huyen, dau nang

    def test_bat_duoc_du_lieu_hong_ID58_dang_NFC(self):
        """Cung noi dung nhung luu dang NFC (dau gan lien) cung phai bat duoc."""
        nfc = unicodedata.normalize("NFC", HONG_NHUNG_HONG)
        assert con_dau(nfc) == ["à", "ò", "ị"]

    def test_sua_duoc_ca_hai_dang_ve_cung_mot_ket_qua(self):
        """Bat ke NFD hay NFC, bo_dau phai cho ra cung chuoi sach."""
        nfd = unicodedata.normalize("NFD", HONG_NHUNG_HONG)
        nfc = unicodedata.normalize("NFC", HONG_NHUNG_HONG)
        assert bo_dau(nfd) == bo_dau(nfc) == "TranThiHongNhuan"
        assert con_dau(bo_dau(nfd)) == []

    def test_bat_duoc_chu_D_con_sot(self):
        assert con_dau("NguyenĐinhHai") == ["Đ"]


class TestPascalCase:
    @pytest.mark.parametrize(
        "vao,ra",
        [
            ("SẦM THỊ QUỲNH NHƯ", "SamThiQuynhNhu"),
            ("NGUYỄN ĐÌNH HẢO", "NguyenDinhHao"),
            ("NGUYỄN TRỌNG QUYẾN", "NguyenTrongQuyen"),
            ("PHÙNG THỊ LÝ", "PhungThiLy"),
            ("LƯ XUÂN BẮC", "LuXuanBac"),
            ("LÊ THỊ THÊM", "LeThiThem"),
            ("HÀ THỊ TÚ ÁNH", "HaThiTuAnh"),
        ],
    )
    def test_ten_that_tu_MAIN(self, vao, ra):
        assert pascal_case(vao) == ra

    def test_sua_dung_ca_du_lieu_hong_ID58(self):
        """MAIN.xlsx đang lưu 'TrànThịHòngNhuận'. Giá trị đúng phải là:"""
        assert pascal_case("TRẦN THỊ HỒNG NHUẬN") == "TranThiHongNhuan"

    def test_khoang_trang_thua(self):
        assert pascal_case("  LÊ  THỊ   THÊM  ") == "LeThiThem"

    def test_ket_qua_luon_chi_co_ascii(self):
        for ten in ["ĐỖ THỊ CHÍNH", "HUỲNH HỮU UYÊN", "NGỌ VĂN THỎA"]:
            assert pascal_case(ten).isascii()
            assert pascal_case(ten).isalnum()

    def test_chuoi_rong(self):
        assert pascal_case("") == ""


class TestSlugTaiLieu:
    def test_bo_dau_va_thay_khoang_trang(self):
        assert (
            slug_tai_lieu("Lý lịch của người xin vào Đảng")
            == "Ly_lich_cua_nguoi_xin_vao_Dang"
        )

    def test_ky_tu_dac_biet_gop_thanh_mot_gach_duoi(self):
        assert (
            slug_tai_lieu("Kết luận minh oan/không vi phạm")
            == "Ket_luan_minh_oan_khong_vi_pham"
        )

    def test_khong_co_gach_duoi_thua_o_hai_dau(self):
        s = slug_tai_lieu("  (Quyết định) nghỉ hưu.  ")
        assert not s.startswith("_") and not s.endswith("_")


class TestMaToChuc:
    """1.Dacta_fixV1: ten thu muc chi bo PHAI co dau cham theo Quy dinh 208-QD/TW."""

    def test_giu_nguyen_dang_co_dau_cham(self):
        assert chuan_hoa_ma_to_chuc("38.168.053.000.001") == "38.168.053.000.001"

    def test_them_dau_cham_vao_dang_14_so_lien(self):
        assert chuan_hoa_ma_to_chuc("38168053000001") == "38.168.053.000.001"

    def test_du_7_chi_bo_that(self):
        ra = [chuan_hoa_ma_to_chuc(f"38.168.053.000.00{i}") for i in range(1, 8)]
        assert ra == [f"38.168.053.000.00{i}" for i in range(1, 8)]
        assert all(len(x) == 18 for x in ra)

    def test_dung_vi_du_trong_dac_ta(self):
        """E:\38.168.007.000.015\012345678901_NguyenVanA"""
        assert chuan_hoa_ma_to_chuc("38.168.007.000.015") == "38.168.007.000.015"

    @pytest.mark.parametrize("xau", ["", "   ", "38.168", "381680530000012", "abc"])
    def test_ma_sai_thi_bao_loi_tieng_viet(self, xau):
        with pytest.raises(LoiMaToChuc) as e:
            chuan_hoa_ma_to_chuc(xau)
        assert "Traceback" not in str(e.value)

    def test_bao_ro_dang_dung(self):
        with pytest.raises(LoiMaToChuc) as e:
            chuan_hoa_ma_to_chuc("38.168.053")
        assert "38.168.053.000.001" in str(e.value)


class TestMaDangBoCoSo:
    def test_lay_ba_nhom_dau(self):
        assert ma_dang_bo_co_so("38.168.053.000.001") == "38.168.053"

    def test_moi_chi_bo_cua_Vien_deu_cho_cung_mot_dang_bo_co_so(self):
        ra = {ma_dang_bo_co_so(f"38.168.053.000.00{i}") for i in range(1, 8)}
        assert ra == {"38.168.053"}

    def test_nhan_ca_dang_khong_dau_cham(self):
        assert ma_dang_bo_co_so("38168053000001") == "38.168.053"


class TestDungFolderName:
    def test_co_so_the_dang(self):
        assert (
            dung_folder_name("099001110001", "SẦM THỊ QUỲNH NHƯ")
            == "099001110001_SamThiQuynhNhu"
        )

    def test_thieu_ca_hai_ma_ca_ID85(self):
        """Quyết định #12: vẫn tạo thư mục, chỉ có phần tên."""
        assert dung_folder_name(None, "LÊ THỊ THÊM") == "LeThiThem"
        assert dung_folder_name("", "LÊ THỊ THÊM") == "LeThiThem"
        assert dung_folder_name("   ", "LÊ THỊ THÊM") == "LeThiThem"

    def test_dung_dau_gach_duoi_khong_phai_dau_cham(self):
        """Dacta1.md mục 4.2 ghi dấu chấm là SAI. Đã đính chính 19/8/2026."""
        ra = dung_folder_name("099003330003", "NGUYỄN ĐÌNH HẢO")
        assert "_" in ra and "." not in ra

    def test_do_dai_nam_trong_ngan_sach_MAX_PATH(self):
        """Thư mục cá nhân dài nhất phải <= 40 ký tự để đường dẫn không vượt 260."""
        dai_nhat = dung_folder_name("099002220002", "TRẦN THỊ HỒNG NHUẬN")
        assert len(dai_nhat) <= 40


class TestMaDangBoCoSo:
    """Bước 0 ghép ba nhóm số. Không khóa cứng mã nào của đơn vị cụ thể."""

    def test_ghep_dung(self):
        assert chuan_hoa_ma_co_so("38", "168", "053") == "38.168.053"

    @pytest.mark.parametrize(
        "tinh, cap_tren, co_so, ra",
        [
            ("38", "168", "7", "38.168.007"),      # tự đệm số 0
            ("8", "68", "7", "08.068.007"),
            ("38", "168", "053", "38.168.053"),
            ("42", "170", "011", "42.170.011"),    # đơn vị tỉnh khác
        ],
    )
    def test_dem_du_chu_so(self, tinh, cap_tren, co_so, ra):
        assert chuan_hoa_ma_co_so(tinh, cap_tren, co_so) == ra

    def test_bo_ky_tu_khong_phai_so(self):
        assert chuan_hoa_ma_co_so(" 38 ", "1-6-8", "05 3") == "38.168.053"

    @pytest.mark.parametrize(
        "tinh, cap_tren, co_so",
        [("", "168", "053"), ("38", "", "053"), ("38", "168", ""), ("38", "168", "  ")],
    )
    def test_thieu_nhom_thi_bao_loi(self, tinh, cap_tren, co_so):
        with pytest.raises(LoiMaToChuc) as e:
            chuan_hoa_ma_co_so(tinh, cap_tren, co_so)
        assert "[2].[3].[3]" in str(e.value)

    @pytest.mark.parametrize(
        "tinh, cap_tren, co_so", [("380", "168", "053"), ("38", "1680", "053"), ("38", "168", "0531")]
    )
    def test_qua_dai_thi_bao_loi(self, tinh, cap_tren, co_so):
        with pytest.raises(LoiMaToChuc):
            chuan_hoa_ma_co_so(tinh, cap_tren, co_so)


class TestThuocDangBoCoSo:
    def test_khop_thi_dung(self):
        assert thuoc_dang_bo_co_so("38.168.053.000.001", "38.168.053")

    def test_lech_nhom_giua_thi_sai(self):
        """Sai một chữ số ở nhóm giữa là cả chi bộ sang cây thư mục khác."""
        assert not thuoc_dang_bo_co_so("38.168.007.000.001", "38.168.053")

    def test_chua_khai_buoc_0_thi_khong_chan(self):
        """Mã cơ sở rỗng nghĩa là chưa đối chiếu được, không phải là sai."""
        assert thuoc_dang_bo_co_so("38.168.053.000.001", "")
