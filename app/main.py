"""Ứng dụng web cục bộ — số hóa hồ sơ đảng viên.

Chạy: `start.bat`, hoặc
    .venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Ba lớp bảo vệ dữ liệu cá nhân (85 đảng viên, có CCCD và ngày sinh)
------------------------------------------------------------------
1. Chỉ lắng nghe 127.0.0.1 — máy khác trong mạng cơ quan không truy cập được.
2. Mọi trang và API đều đòi token phiên sinh ngẫu nhiên lúc khởi động, nên một
   trang web độc hại mở ở tab khác không gọi được API dù cùng máy.
3. Không ghi CCCD ra tệp nhật ký.
"""

from __future__ import annotations

import io
import os
import secrets
import sys
import traceback
import webbrowser
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook

from app.core import audit, chan_doan, intake, nhat_ky, report, tree
from app.core import ban_quyen
from app.core.ban_quyen import NGU_CANH_BAN_QUYEN
from app.core.mainbook import (
    TEN_MAIN_MAC_DINH,
    LoiNghiepVu,
    bang_chi_bo_tu_nguoi_dung,
    chuan_bi_bang_chi_bo,
    chuan_hoa_duong_dan_main,
    doc_ds_dangvien,
    doc_main,
    dong_bo,
    ghi_main,
)
from app.core.paths import (
    NGUONG_CANH_BAO_GOC,
    LoiDuongDan,
    an_toan_duoi,
    dam_bao_danh_muc_ton_tai,
    kiem_tra_thu_muc_goc,
    liet_ke_thu_muc_con,
)
from app.core.rename import danh_muc
from app.core.phien import (
    DIA_DANH_MAC_DINH,
    MA_CAP_TREN_MAC_DINH,
    MA_TINH_MAC_DINH,
    PHIEN,
    TEN_BUOC,
)
from app.core.vietnamese import LoiMaToChuc, chuan_hoa_ma_co_so

GOC_APP = Path(__file__).resolve().parent
# Bảng lỗi 8.000 dòng làm treo trình duyệt. Hiện tối đa chừng này, kèm số còn lại.
GIOI_HAN_DONG = 400
TOKEN = secrets.token_urlsafe(16)
TEN_COOKIE = "phien_so_hoa"

# Tắt cả ba đường tài liệu tự sinh của FastAPI. Bỏ mỗi /docs và /redoc là chưa
# đủ: /openapi.json vẫn phơi nguyên sơ đồ mọi API kèm tên tham số, đủ để người
# ngoài dựng lại toàn bộ hợp đồng nội bộ mà không cần đọc mã nguồn.
app = FastAPI(
    title=ban_quyen.TEN_UNG_DUNG,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
# vong_doi() dinh nghia o cuoi tep, gan vao app ngay sau do.
app.mount("/static", StaticFiles(directory=GOC_APP / "static"), name="static")
mau = Jinja2Templates(directory=str(GOC_APP / "templates"))


# --------------------------------------------------------------- xác thực


@app.middleware("http")
async def chan_truy_cap_la(request: Request, goi_tiep):
    duong_dan = request.url.path
    if duong_dan.startswith("/static"):
        return await goi_tiep(request)

    tu_dia_chi = request.query_params.get("t")
    tu_cookie = request.cookies.get(TEN_COOKIE)

    if tu_dia_chi and secrets.compare_digest(tu_dia_chi, TOKEN):
        sach = str(request.url.replace(query=""))
        tra_ve = RedirectResponse(sach, status_code=303)
        tra_ve.set_cookie(TEN_COOKIE, TOKEN, httponly=True, samesite="strict")
        return tra_ve

    if not (tu_cookie and secrets.compare_digest(tu_cookie, TOKEN)):
        return HTMLResponse(
            "<h1>Phiên không hợp lệ</h1>"
            "<p>Mở lại ứng dụng bằng đường dẫn hiện ở cửa sổ đen "
            "(cửa sổ dòng lệnh) vừa bật lên khi chạy <code>start.bat</code>.</p>",
            status_code=403,
        )
    return await goi_tiep(request)


@app.exception_handler(Exception)
async def loi_ngoai_du_tinh(request: Request, loi: Exception):
    """Không để lỗi lạ rơi ra thành HTTP 500 rỗng.

    Trước đây một ngoại lệ ngoài dự tính trả về 500 không có thân JSON; giao
    diện đọc JSON thất bại rồi báo "Không liên lạc được với ứng dụng" — đổ tội
    cho mạng, trong khi nguyên nhân thật chỉ hiện trong cửa sổ dòng lệnh mà
    người dùng không nghĩ tới việc mở ra xem.
    """
    traceback.print_exc()
    mo_ta = f"{type(loi).__name__}: {loi}"
    nhat_ky.ghi("loi", f"{request.url.path} — {mo_ta}")
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {
                "loi": "Ứng dụng gặp lỗi ngoài dự tính:\n"
                + mo_ta
                + "\n\nChụp lại cửa sổ dòng lệnh (cửa sổ đen) rồi báo lỗi."
            },
            status_code=500,
        )
    return HTMLResponse(
        "<h1>Ứng dụng gặp lỗi ngoài dự tính</h1><pre>" + mo_ta + "</pre>",
        status_code=500,
    )


# ------------------------------------------------------------ dựng trang


def _ngu_canh(buoc: int, **them) -> dict:
    ch = PHIEN.cau_hinh
    return {
        "buoc": buoc,
        "ten_buoc": TEN_BUOC,
        "buoc_da_xong": ch.buoc_da_xong,
        "mo_khoa_duoc": ch.mo_khoa_duoc,
        "cau_hinh": ch,
        **NGU_CANH_BAN_QUYEN,
        **them,
    }


@app.get("/", response_class=HTMLResponse)
async def trang_chu():
    return RedirectResponse("/buoc/0", status_code=303)


@app.get("/buoc/{so}", response_class=HTMLResponse)
async def trang_buoc(request: Request, so: int):
    if so not in TEN_BUOC:
        return RedirectResponse("/buoc/0", status_code=303)
    if not PHIEN.cau_hinh.mo_khoa_duoc(so):
        return mau.TemplateResponse(
            request, "khoa.html", _ngu_canh(so, buoc_can_lam=so - 1)
        )

    if so == 0:
        return mau.TemplateResponse(
            request,
            "buoc0.html",
            _ngu_canh(
                0,
                ma_tinh_mac_dinh=MA_TINH_MAC_DINH,
                ma_cap_tren_mac_dinh=MA_CAP_TREN_MAC_DINH,
                dia_danh_mac_dinh=DIA_DANH_MAC_DINH,
            ),
        )
    if so == 1:
        return mau.TemplateResponse(request, "buoc1.html", _ngu_canh(1))
    if so == 2:
        if PHIEN.ket_qua_dong_bo is None:
            return RedirectResponse("/buoc/1", status_code=303)
        return mau.TemplateResponse(
            request, "buoc2.html", _ngu_canh(2, kq=PHIEN.ket_qua_dong_bo)
        )
    if so == 3:
        return mau.TemplateResponse(
            request,
            "buoc3.html",
            _ngu_canh(
                3,
                nguong=NGUONG_CANH_BAO_GOC,
                ke_hoach=PHIEN.ke_hoach_cay,
                ngan_sach=PHIEN.thong_tin_ngan_sach,
            ),
        )
    if so == 4:
        return mau.TemplateResponse(request, "buoc4.html", _ngu_canh(4))
    if so == 5:
        if PHIEN.ket_qua_quet is None:
            return RedirectResponse("/buoc/4", status_code=303)
        return mau.TemplateResponse(request, "buoc5.html", _ngu_canh(5))
    if so == 6:
        return mau.TemplateResponse(request, "buoc6.html", _ngu_canh(6))
    if so == 7:
        if PHIEN.ket_qua_doi_soat is None:
            return RedirectResponse("/buoc/6", status_code=303)
        return mau.TemplateResponse(
            request,
            "buoc7.html",
            _ngu_canh(
                7,
                hom_nay=date.today().isoformat(),
                chi_bo=PHIEN.ket_qua_doi_soat.chi_bo,
                mac_dinh=report.ThongTinVanBan.tu_cau_hinh(PHIEN.cau_hinh),
            ),
        )
    return mau.TemplateResponse(request, "chua_lam.html", _ngu_canh(so))


# --------------------------------------------------------------- API dùng chung


@app.get("/huong_dan", response_class=HTMLResponse)
async def trang_huong_dan(request: Request):
    """Hướng dẫn sử dụng ngay trong app — không cần mở tệp Word bên ngoài."""
    return mau.TemplateResponse(
        request,
        "huong_dan.html",
        _ngu_canh(
            PHIEN.cau_hinh.buoc_da_xong[-1] if PHIEN.cau_hinh.buoc_da_xong else 0,
            la_trang_phu=True,
            loai_loi=intake.TEN_LOI,
            loai_canh_bao=intake.TEN_CANH_BAO,
            so_loai_tai_lieu=len(danh_muc()),
        ),
    )


@app.get("/api/duyet")
async def api_duyet(p: str = "", tep: str = ""):
    """Hộp thoại chọn thư mục/tệp do máy chủ dựng.

    Trình duyệt không lấy được đường dẫn thư mục trên máy, nên máy chủ phải tự
    liệt kê rồi gửi về. Xem app/core/paths.py để biết lý do đầy đủ.
    """
    try:
        duoi = {d.strip().lower() for d in tep.split(",") if d.strip()} or None
        return JSONResponse(liet_ke_thu_muc_con(p or None, duoi))
    except LoiDuongDan as loi:
        return JSONResponse({"loi": str(loi)}, status_code=400)


def _trang_thai_phien() -> str:
    """Tóm tắt phiên làm việc cho gói chẩn đoán — chỉ con số, không có tên người."""
    ch = PHIEN.cau_hinh
    dong = [
        "TRẠNG THÁI PHIÊN LÀM VIỆC",
        "=" * 60,
        f"Bước đã xong: {ch.buoc_da_xong or '(chưa bước nào)'}",
        "",
    ]

    kq = PHIEN.ket_qua_dong_bo
    if kq is None:
        dong.append("Bước 1: chưa nạp dữ liệu.")
    else:
        dong.append(
            f"Bước 1: {len(kq.dong)} đảng viên · {len(PHIEN.chi_bo)} chi bộ · "
            f"thêm mới {len(kq.them_moi)} · dòng cần sửa {len(kq.du_lieu_ban)} · "
            f"lỗi chặn: {kq.co_loi_chan}"
        )

    if PHIEN.ke_hoach_cay is not None:
        dong.append(f"Bước 3: {PHIEN.ke_hoach_cay.tom_tat}")

    quet = PHIEN.ket_qua_quet
    if quet is not None:
        ten_manifest = Path(quet.manifest).name if quet.manifest else "(chưa ghi)"
        dong.append(
            f"Bước 4: {len(quet.tep)} tệp · hợp lệ {len(quet.hop_le)} · "
            f"lỗi {len(quet.loi)} {quet.tom_tat_loi}"
        )
        dong.append(f"Bước 5: {quet.tom_tat_hanh_dong} · manifest {ten_manifest}")

    ds = PHIEN.ket_qua_doi_soat
    if ds is not None:
        dong.append(
            f"Bước 6: ƯT1 {ds.tien_do[1]} · chờ chuyển PDF {ds.so_cho_chuyen_pdf} · "
            f"thiếu thư mục {ds.thieu_thu_muc}"
        )
    if PHIEN.tep_bao_cao:
        dong.append(
            "Bước 7: " + ", ".join(Path(v).name for v in PHIEN.tep_bao_cao.values())
        )

    return "\n".join(dong)


@app.get("/api/chan_doan")
async def api_goi_chan_doan():
    """Nén nhật ký, cấu hình và tóm tắt trạng thái để gửi kèm khi báo lỗi."""
    nhat_ky.ghi("info", "Xuất gói chẩn đoán")
    du_lieu = chan_doan.dung_goi(
        PHIEN.cau_hinh, _trang_thai_phien(), cong=cong_dang_chay()
    )
    return Response(
        content=du_lieu,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{chan_doan.ten_goi()}"'},
    )


# ------------------------------------------------------------------- bước 0


@app.post("/api/buoc0/luu")
async def api_luu_don_vi(
    ten_dang_bo: str = Form(...),
    ten_cap_tren: str = Form(""),
    ma_tinh: str = Form(MA_TINH_MAC_DINH),
    ma_cap_tren: str = Form(MA_CAP_TREN_MAC_DINH),
    ma_co_so: str = Form(...),
    dia_danh: str = Form(DIA_DANH_MAC_DINH),
):
    """Ghi nhận đơn vị đang dùng app. Mọi bước sau đọc từ đây.

    Đổi tên hoặc đổi mã đảng bộ cơ sở là đổi gốc cây thư mục, nên phải làm lại
    từ bước 1 — không được để sổ cái cũ nằm lẫn với mã tổ chức mới.
    """
    ten_dang_bo = ten_dang_bo.strip()
    if not ten_dang_bo:
        return JSONResponse(
            {
                "loi": "Chưa nhập tên đảng bộ. Tên này in lên báo cáo và phụ lục "
                "nên phải ghi đúng như trong con dấu, ví dụ "
                "Đảng bộ Viện Nông nghiệp Thanh Hóa."
            },
            status_code=400,
        )
    try:
        day_du = chuan_hoa_ma_co_so(ma_tinh, ma_cap_tren, ma_co_so)
    except LoiMaToChuc as loi:
        return JSONResponse({"loi": str(loi)}, status_code=400)

    ch = PHIEN.cau_hinh
    doi_goc = ch.da_khai_don_vi and ch.ma_dang_bo_co_so != day_du
    ch.ten_dang_bo = ten_dang_bo
    ch.ten_cap_tren = ten_cap_tren.strip()
    ch.ma_tinh, ch.ma_cap_tren, ch.ma_co_so = day_du.split(".")
    ch.dia_danh = dia_danh.strip() or DIA_DANH_MAC_DINH

    if doi_goc:
        PHIEN.dat_lai_tu_buoc(1)
    ch.danh_dau_xong(0)
    nhat_ky.ghi("info", f"Bước 0: {ten_dang_bo} — đảng bộ cơ sở {day_du}")
    return JSONResponse(
        {
            "ten_dang_bo": ten_dang_bo,
            "ma_dang_bo_co_so": day_du,
            "mau_ma_chi_bo": f"{day_du}.000.001",
            "da_dat_lai": doi_goc,
        }
    )


# ------------------------------------------------------------------- bước 1


@app.post("/api/buoc1/doc_ds")
async def api_doc_ds(duong_dan_ds: str = Form(...), duong_dan_main: str = Form("")):
    """Đọc DS_DANGVIEN rồi dựng bảng chi bộ để người dùng điền mã tổ chức đảng.

    Theo ``1.Dacta_fixV1``, MAIN.xlsx **được tạo ra từ DS**, không phải chọn từ
    một tệp mẫu. Danh sách chi bộ vì thế lấy thẳng từ DS.
    """
    ds = Path(duong_dan_ds.strip())
    if ds.is_dir():
        return JSONResponse(
            {
                "loi": f"Đây là thư mục chứ không phải tệp danh sách:\n{ds}\n"
                "Bấm Duyệt rồi chọn tệp DS_DANGVIEN.xlsx nằm trong thư mục này."
            },
            status_code=400,
        )
    if not ds.is_file():
        return JSONResponse(
            {
                "loi": f"Không tìm thấy tệp danh sách đảng viên:\n{ds}\n"
                "Bấm Duyệt để chọn tệp DS_DANGVIEN.xlsx."
            },
            status_code=400,
        )
    try:
        nguon = doc_ds_dangvien(ds)
    except LoiNghiepVu as loi:
        return JSONResponse({"loi": str(loi)}, status_code=400)

    mac_dinh = str(ds.parent / TEN_MAIN_MAC_DINH)
    try:
        goi_y = chuan_hoa_duong_dan_main(duong_dan_main.strip() or mac_dinh)
    except LoiNghiepVu:
        # Ở bước này ô "nơi lưu" mới chỉ là gợi ý. Gõ sai thì đề xuất lại chỗ
        # mặc định chứ không chặn việc đọc danh sách; người dùng còn sửa được
        # trước khi bấm "Đối chiếu", và lúc đó mới báo lỗi thật.
        goi_y = Path(mac_dinh)
    return JSONResponse(
        {
            "so_dang_vien": len(nguon),
            "duong_dan_main": str(goi_y),
            "main_da_ton_tai": goi_y.is_file(),
            "ma_co_so": PHIEN.cau_hinh.ma_dang_bo_co_so,
            "chi_bo": chuan_bi_bang_chi_bo(nguon, goi_y),
        }
    )


@app.post("/api/buoc1/nap")
async def api_nap(request: Request):
    """Đối chiếu DS vào sổ cái, dùng bảng chi bộ người dùng vừa điền.

    Chưa ghi gì lên đĩa — bước 2 mới ghi.
    """
    than = await request.json()
    ds = Path(str(than.get("duong_dan_ds", "")).strip())

    if not ds.is_file():
        return JSONResponse(
            {"loi": f"Không tìm thấy tệp danh sách đảng viên:\n{ds}"},
            status_code=400,
        )
    try:
        # Người dùng thường đưa vào THƯ MỤC vì ô này tên là "nơi lưu"; hàm này
        # tự thêm MAIN.xlsx, và chặn mọi đuôi khác .xlsx vì bước 2 ghi đè.
        main = chuan_hoa_duong_dan_main(than.get("duong_dan_main", ""))
    except LoiNghiepVu as loi:
        return JSONResponse({"loi": str(loi)}, status_code=400)
    if not main.parent.is_dir():
        return JSONResponse(
            {"loi": f"Không tìm thấy thư mục để lưu sổ cái:\n{main.parent}"},
            status_code=400,
        )

    try:
        nguon = doc_ds_dangvien(ds)
        chi_bo = bang_chi_bo_tu_nguoi_dung(
            than.get("chi_bo") or [], PHIEN.cau_hinh.ma_dang_bo_co_so
        )
        hien_co = doc_main(main)
        kq = dong_bo(nguon, chi_bo, hien_co)
    except LoiNghiepVu as loi:
        return JSONResponse({"loi": str(loi)}, status_code=400)

    PHIEN.dat_lai_tu_buoc(1)
    PHIEN.ket_qua_dong_bo = kq
    PHIEN.chi_bo = chi_bo
    PHIEN.cau_hinh.duong_dan_ds = str(ds)
    PHIEN.cau_hinh.duong_dan_main = str(main)
    PHIEN.cau_hinh.danh_dau_xong(1)
    nhat_ky.ghi(
        "info",
        f"Bước 1: {len(kq.dong)} đảng viên, {len(chi_bo)} chi bộ, "
        f"thêm mới {len(kq.them_moi)}, lỗi chặn {kq.co_loi_chan}",
    )

    return JSONResponse(
        {
            "duong_dan_main": str(main),
            "so_dang_vien": len(kq.dong),
            "so_chi_bo": len(chi_bo),
            "them_moi": len(kq.them_moi),
            "roi_danh_sach": len(kq.roi_danh_sach),
            "du_lieu_ban": len(kq.du_lieu_ban),
            "canh_bao": sum(1 for c in kq.canh_bao if c.muc == "canh_bao"),
            "loi": sum(1 for c in kq.canh_bao if c.muc == "loi"),
            "co_loi_chan": kq.co_loi_chan,
        }
    )


# ------------------------------------------------------------------- bước 2


@app.post("/api/buoc2/ghi")
async def api_ghi_so_cai():
    """Người dùng đã xem bảng và duyệt — ghi sổ cái ra đĩa."""
    kq = PHIEN.ket_qua_dong_bo
    if kq is None:
        return JSONResponse({"loi": "Chưa nạp dữ liệu. Quay lại bước 1."}, status_code=400)
    if kq.co_loi_chan:
        return JSONResponse(
            {"loi": "Còn lỗi phải xử lý trước khi ghi sổ cái. Xem bảng Lỗi bên dưới."},
            status_code=400,
        )
    try:
        ghi_main(Path(PHIEN.cau_hinh.duong_dan_main), kq.dong, PHIEN.chi_bo)
    except LoiNghiepVu as loi:
        return JSONResponse({"loi": str(loi)}, status_code=400)

    PHIEN.cau_hinh.danh_dau_xong(2)
    nhat_ky.ghi("info", f"Bước 2: ghi sổ cái {len(kq.dong)} dòng")
    return JSONResponse(
        {"da_ghi": PHIEN.cau_hinh.duong_dan_main, "so_dong": len(kq.dong)}
    )


# ------------------------------------------------------------------- bước 3


@app.post("/api/buoc3/kiem")
async def api_kiem_goc(duong_dan_goc: str = Form(...)):
    """Kiểm thư mục gốc và lập kế hoạch tạo cây. Chưa ghi gì lên đĩa."""
    kq = PHIEN.ket_qua_dong_bo
    if kq is None:
        return JSONResponse({"loi": "Chưa nạp dữ liệu. Quay lại bước 1."}, status_code=400)

    tuong_doi = tree.do_dai_tuong_doi_lon_nhat(kq.dong)
    try:
        ngan_sach = kiem_tra_thu_muc_goc(duong_dan_goc, tuong_doi)
    except LoiDuongDan as loi:
        return JSONResponse({"loi": str(loi)}, status_code=400)

    if not ngan_sach.dat:
        PHIEN.thong_tin_ngan_sach = ngan_sach
        return JSONResponse({"loi": ngan_sach.thong_bao}, status_code=400)

    ten_cu = {
        s.id: s.gia_tri_cu for s in kq.du_lieu_ban if s.truong == "Folder_name"
    }
    ke_hoach = tree.lap_ke_hoach(ngan_sach.duong_dan_goc, kq.dong, ten_cu)

    PHIEN.thong_tin_ngan_sach = ngan_sach
    PHIEN.ke_hoach_cay = ke_hoach
    PHIEN.cau_hinh.duong_dan_goc = ngan_sach.duong_dan_goc
    PHIEN.cau_hinh.ghi()

    return JSONResponse(
        {
            "thong_bao": ngan_sach.thong_bao,
            "co_so_tao_moi": len(ke_hoach.co_so_tao_moi),
            "co_so_da_co": len(ke_hoach.co_so_da_co),
            "don_vi_tao_moi": len(ke_hoach.don_vi_tao_moi),
            "don_vi_da_co": len(ke_hoach.don_vi_da_co),
            "tom_tat": ke_hoach.tom_tat,
            "co_loi": ke_hoach.co_loi,
            "can_thay_doi": ke_hoach.can_thay_doi,
        }
    )


@app.post("/api/buoc3/tao")
async def api_tao_cay():
    ke_hoach = PHIEN.ke_hoach_cay
    if ke_hoach is None:
        return JSONResponse(
            {"loi": "Chưa kiểm thư mục gốc. Bấm Xem trước trước đã."}, status_code=400
        )
    tree.thuc_thi(ke_hoach)
    PHIEN.cau_hinh.danh_dau_xong(3)
    nhat_ky.ghi("info", f"Bước 3: tạo cây thư mục {ke_hoach.tom_tat}")
    return JSONResponse({"tom_tat": ke_hoach.tom_tat, "co_loi": ke_hoach.co_loi})


# ------------------------------------------------------------------- bước 4


def _boi_canh_intake() -> intake.BoiCanh | None:
    kq = PHIEN.ket_qua_dong_bo
    if kq is None:
        return None
    return intake.BoiCanh.tu_so_cai(kq.dong, PHIEN.chi_bo)


def _dong_tep(t: intake.TepScan) -> dict:
    """Một dòng tệp gửi cho giao diện. Không kèm CCCD."""
    return {
        "duong_dan": t.duong_dan,
        "ten_goc": t.ten_goc,
        "ma_loi": t.ma_loi,
        "ten_loi": intake.TEN_LOI.get(t.ma_loi, ""),
        "thong_bao": t.thong_bao,
        "canh_bao": [{"ma": m, "cau": c} for m, c in t.canh_bao],
        "id_dang_vien": t.id_dang_vien,
        "ten_dang_vien": t.ten_dang_vien,
        "ma_tai_lieu": t.ma_tai_lieu or "",
        "ten_moi": t.ten_moi,
        "duong_dan_dich": t.duong_dan_dich,
        "kho_cho": t.kho_cho,
        "hanh_dong": t.hanh_dong,
        "sua_thu_cong": t.sua_thu_cong,
    }


def _danh_sach_chon() -> dict:
    """Dữ liệu cho hai ô chọn ở bảng lỗi: 85 đảng viên và 104 loại tài liệu."""
    kq = PHIEN.ket_qua_dong_bo
    dang_vien = [{"id": d.id, "ten": d.name} for d in (kq.dong if kq else [])]
    tai_lieu = [
        {"ma": m.ma, "ten": m.ten_day_du, "uu_tien": m.uu_tien}
        for m in sorted(danh_muc().values(), key=lambda x: x.ma)
    ]
    return {"dang_vien": dang_vien, "tai_lieu": tai_lieu}


@app.post("/api/buoc4/quet")
async def api_quet_scan(duong_dan_scan: str = Form(...)):
    """Quét thư mục scan và chấm lỗi từng tệp. Không đụng tới tệp nào."""
    bc = _boi_canh_intake()
    if bc is None:
        return JSONResponse({"loi": "Chưa nạp dữ liệu. Quay lại bước 1."}, status_code=400)

    thu_muc = Path(duong_dan_scan.strip().strip('"'))
    if thu_muc.is_file():
        return JSONResponse(
            {
                "loi": f"Đây là một tệp chứ không phải thư mục:\n{thu_muc}\n"
                "Chọn thư mục chứa các tệp scan."
            },
            status_code=400,
        )
    if not thu_muc.is_dir():
        return JSONResponse(
            {"loi": f"Không tìm thấy thư mục chứa tệp scan:\n{thu_muc}"}, status_code=400
        )

    goc = Path(PHIEN.cau_hinh.duong_dan_goc or "")
    if not goc.is_dir():
        return JSONResponse(
            {"loi": "Chưa tạo cây thư mục. Quay lại bước 3."}, status_code=400
        )
    if an_toan_duoi(goc, thu_muc) or an_toan_duoi(thu_muc, goc):
        return JSONResponse(
            {
                "loi": f"Thư mục scan và thư mục kho lồng vào nhau:\n{thu_muc}\n{goc}\n"
                "App sẽ chép tệp lên chính nó. Để thư mục scan ở chỗ khác."
            },
            status_code=400,
        )

    kq = intake.quet(thu_muc, bc)
    PHIEN.dat_lai_tu_buoc(4)
    PHIEN.ket_qua_quet = kq
    PHIEN.cau_hinh.duong_dan_scan = str(thu_muc)
    PHIEN.cau_hinh.danh_dau_xong(4)
    nhat_ky.ghi(
        "info",
        f"Bước 4: quét {len(kq.tep)} tệp, hợp lệ {len(kq.hop_le)}, "
        f"lỗi {len(kq.loi)} {kq.tom_tat_loi}",
    )

    dong_loi = kq.loi[:GIOI_HAN_DONG]
    canh_bao = kq.canh_bao[:GIOI_HAN_DONG]
    return JSONResponse(
        {
            "thu_muc": str(thu_muc),
            "tong": len(kq.tep),
            "so_hop_le": len(kq.hop_le),
            "so_loi": len(kq.loi),
            "so_canh_bao": len(kq.canh_bao),
            "tom_tat_loi": kq.tom_tat_loi,
            "ten_loi": intake.TEN_LOI,
            "dong_loi": [_dong_tep(t) for t in dong_loi],
            "dong_canh_bao": [_dong_tep(t) for t in canh_bao],
            "con_lai": max(0, len(kq.loi) - len(dong_loi)),
            **_danh_sach_chon(),
        }
    )


@app.post("/api/buoc4/sua")
async def api_sua_ten_tep(request: Request):
    """Người dùng chỉ đúng đảng viên + loại tài liệu cho một tệp sai tên (§5.6)."""
    kq = PHIEN.ket_qua_quet
    bc = _boi_canh_intake()
    if kq is None or bc is None:
        return JSONResponse({"loi": "Chưa quét thư mục scan. Bấm Quét trước đã."}, status_code=400)

    than = await request.json()
    try:
        t = intake.sua_thu_cong(
            kq,
            str(than.get("duong_dan", "")),
            str(than.get("id_dang_vien", "")),
            than.get("ma_tai_lieu", 0),
            bc,
        )
    except LoiDuongDan as loi:
        return JSONResponse({"loi": str(loi)}, status_code=400)

    return JSONResponse(
        {"tep": _dong_tep(t), "so_loi_con_lai": len(kq.loi), "so_hop_le": len(kq.hop_le)}
    )


@app.get("/api/buoc4/xuat_loi")
async def api_xuat_bang_loi():
    """Xuất bảng lỗi ra .xlsx để mang đi đối chiếu với người scan."""
    kq = PHIEN.ket_qua_quet
    if kq is None:
        return JSONResponse({"loi": "Chưa quét thư mục scan."}, status_code=400)

    wb = Workbook()
    ws = wb.active
    ws.title = "Loi"
    ws.append(["Tệp", "Loại lỗi", "Vấn đề và cách sửa", "Đường dẫn"])
    for t in kq.loi:
        ws.append([t.ten_goc, intake.TEN_LOI.get(t.ma_loi, t.ma_loi), t.thong_bao, t.duong_dan])
    for cot, rong in zip("ABCD", (42, 30, 95, 70)):
        ws.column_dimensions[cot].width = rong

    bo_nho = io.BytesIO()
    wb.save(bo_nho)
    ten = f"Bang_loi_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    return Response(
        content=bo_nho.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{ten}"'},
    )


# ------------------------------------------------------------------- bước 5


@app.post("/api/buoc5/xem")
async def api_xem_luan_chuyen():
    """Lập kế hoạch copy + đổi tên. Chưa ghi gì lên đĩa."""
    kq = PHIEN.ket_qua_quet
    bc = _boi_canh_intake()
    if kq is None or bc is None:
        return JSONResponse(
            {"loi": "Chưa quét thư mục scan. Quay lại bước 4."}, status_code=400
        )
    goc = Path(PHIEN.cau_hinh.duong_dan_goc or "")
    if not goc.is_dir():
        return JSONResponse({"loi": "Chưa tạo cây thư mục. Quay lại bước 3."}, status_code=400)

    intake.lap_ke_hoach(kq, goc, bc)
    if kq.tom_tat_hanh_dong[intake.COPY] == 0:
        # Không có gì để chép cũng là xong. Không đánh dấu thì người dùng kẹt
        # lại ở bước 5, không sang được bước đối soát.
        PHIEN.cau_hinh.danh_dau_xong(5)
    dong = [t for t in kq.tep if t.hanh_dong in (intake.COPY, intake.BO_QUA)]
    return JSONResponse(
        {
            "goc": str(goc),
            "tom_tat": kq.tom_tat_hanh_dong,
            "nhan_hanh_dong": intake.NHAN_HANH_DONG,
            "tong_byte": kq.tong_byte,
            "byte_con_trong": kq.byte_con_trong,
            "du_cho_trong": kq.du_cho_trong,
            "so_dong": len(dong),
            "dong": [_dong_tep(t) for t in dong[:GIOI_HAN_DONG]],
            "con_lai": max(0, len(dong) - GIOI_HAN_DONG),
            "so_loi": len(kq.loi),
        }
    )


@app.post("/api/buoc5/thuc_thi")
async def api_thuc_thi_luan_chuyen():
    kq = PHIEN.ket_qua_quet
    if kq is None or not kq.da_lap_ke_hoach:
        return JSONResponse(
            {"loi": "Chưa xem trước. Bấm Xem trước rồi hãy Thực thi."}, status_code=400
        )
    if not kq.du_cho_trong:
        return JSONResponse(
            {
                "loi": f"Ổ đĩa còn {kq.byte_con_trong / 1e9:.1f} GB, "
                f"không đủ chỗ cho {kq.tong_byte / 1e9:.1f} GB tệp sắp chép.\n"
                "Dọn bớt ổ đĩa rồi thử lại."
            },
            status_code=400,
        )

    try:
        intake.thuc_thi(kq)
    except LoiDuongDan as loi:
        return JSONResponse({"loi": str(loi)}, status_code=400)

    PHIEN.cau_hinh.danh_dau_xong(5)
    nhat_ky.ghi(
        "info", f"Bước 5: {kq.tom_tat_hanh_dong}, manifest {Path(kq.manifest).name}"
    )
    return JSONResponse(
        {
            "tom_tat": kq.tom_tat_hanh_dong,
            "manifest": kq.manifest,
            "so_loi": len(kq.loi),
            "tom_tat_loi": kq.tom_tat_loi,
        }
    )


# ------------------------------------------------------------------- bước 6


def _muc_tien_do(td) -> dict:
    return {"co": td.co, "tong": td.tong, "ti_le": round(td.ti_le, 1)}


@app.post("/api/buoc6/doi_soat")
async def api_doi_soat():
    """Quét cây thư mục, đối chiếu 104 loại tài liệu. Chưa ghi gì vào sổ cái."""
    kq_dong_bo = PHIEN.ket_qua_dong_bo
    if kq_dong_bo is None:
        return JSONResponse({"loi": "Chưa nạp dữ liệu. Quay lại bước 1."}, status_code=400)
    goc = Path(PHIEN.cau_hinh.duong_dan_goc or "")
    if not goc.is_dir():
        return JSONResponse({"loi": "Chưa tạo cây thư mục. Quay lại bước 3."}, status_code=400)

    kq = audit.doi_soat(goc, kq_dong_bo.dong, PHIEN.chi_bo)
    PHIEN.dat_lai_tu_buoc(6)
    PHIEN.ket_qua_doi_soat = kq

    return JSONResponse(
        {
            "goc": kq.goc,
            "so_dang_vien": kq.so_dang_vien,
            "tong_tep_da_co": kq.tong_tep_da_co,
            "so_cho_chuyen_pdf": kq.so_cho_chuyen_pdf,
            "thieu_thu_muc": kq.thieu_thu_muc,
            "tien_do": {str(ut): _muc_tien_do(kq.tien_do[ut]) for ut in audit.MUC_UU_TIEN},
            "chi_bo": [
                {
                    "ma_id": c.ma_id,
                    "ma_to_chuc": c.ma_to_chuc,
                    "ten": c.ten,
                    "so_dang_vien": c.so_dang_vien,
                    "tien_do": {
                        str(ut): _muc_tien_do(c.tien_do[ut]) for ut in audit.MUC_UU_TIEN
                    },
                    "cho_chuyen_pdf": c.so_cho_chuyen_pdf,
                    "thieu_thu_muc": c.thieu_thu_muc,
                }
                for c in kq.chi_bo
            ],
            "dong": [
                {
                    "id": d.id,
                    "ho_ten": d.ho_ten,
                    "chi_bo": d.chi_bo,
                    "ut1": str(d.tien_do[1]),
                    "ut2": str(d.tien_do[2]),
                    "ut3": str(d.tien_do[3]),
                    "ti_le_ut1": round(d.tien_do[1].ti_le, 1),
                    "so_da_co": d.so_tep_da_co,
                    "cho_chuyen_pdf": len(d.cho_chuyen_pdf),
                    "ghi_chu": d.ghi_chu,
                }
                for d in kq.dong
            ],
        }
    )


@app.post("/api/buoc6/ghi")
async def api_ghi_doi_soat():
    """Người dùng đã xem kết quả — ghi 6 cột đối soát vào MAIN.xlsx."""
    kq = PHIEN.ket_qua_doi_soat
    kq_dong_bo = PHIEN.ket_qua_dong_bo
    if kq is None or kq_dong_bo is None:
        return JSONResponse({"loi": "Chưa đối soát. Bấm Đối soát trước đã."}, status_code=400)

    so_dong = audit.gan_vao_so_cai(kq, kq_dong_bo.dong)
    try:
        ghi_main(Path(PHIEN.cau_hinh.duong_dan_main), kq_dong_bo.dong, PHIEN.chi_bo)
    except LoiNghiepVu as loi:
        return JSONResponse({"loi": str(loi)}, status_code=400)

    PHIEN.cau_hinh.danh_dau_xong(6)
    nhat_ky.ghi(
        "info",
        f"Bước 6: ghi đối soát {so_dong} dòng, ƯT1 {kq.tien_do[1]}, "
        f"chờ chuyển PDF {kq.so_cho_chuyen_pdf}",
    )
    return JSONResponse({"so_dong": so_dong, "da_ghi": PHIEN.cau_hinh.duong_dan_main})


# ------------------------------------------------------------------- bước 7


@app.post("/api/buoc7/xuat")
async def api_xuat_bao_cao(request: Request):
    """Xuất báo cáo .docx theo thể thức và phụ lục .xlsx."""
    kq = PHIEN.ket_qua_doi_soat
    if kq is None:
        return JSONResponse({"loi": "Chưa đối soát. Quay lại bước 6."}, status_code=400)

    than = await request.json()
    thu_muc_ra = Path(str(than.get("thu_muc_ra", "")).strip().strip('"'))
    if not str(thu_muc_ra):
        thu_muc_ra = Path(PHIEN.cau_hinh.duong_dan_goc)
    if thu_muc_ra.is_file():
        return JSONResponse(
            {"loi": f"Đây là một tệp chứ không phải thư mục:\n{thu_muc_ra}"},
            status_code=400,
        )
    if not thu_muc_ra.parent.is_dir():
        return JSONResponse(
            {"loi": f"Không tìm thấy nơi lưu báo cáo:\n{thu_muc_ra}"}, status_code=400
        )

    pham_vi = str(than.get("pham_vi", "")).strip()
    ten_pham_vi = "toàn Đảng bộ"
    if pham_vi:
        khop = [c for c in kq.chi_bo if c.ma_to_chuc == pham_vi]
        if not khop:
            return JSONResponse(
                {"loi": f"Không có chi bộ nào mang mã {pham_vi}."}, status_code=400
            )
        ten_pham_vi = khop[0].ten

    ngay_thang = str(than.get("ngay", "")).strip()
    try:
        ngay = date.fromisoformat(ngay_thang) if ngay_thang else date.today()
    except ValueError:
        return JSONResponse(
            {"loi": f"Ngày tháng không đọc được: {ngay_thang!r}. Dạng đúng: 2026-08-20."},
            status_code=400,
        )

    noi_nhan = [
        d.strip() for d in str(than.get("noi_nhan", "")).splitlines() if d.strip()
    ]
    mac_dinh = report.ThongTinVanBan.tu_cau_hinh(PHIEN.cau_hinh)
    tt = report.ThongTinVanBan(
        co_quan_chu_quan=str(than.get("co_quan_chu_quan", mac_dinh.co_quan_chu_quan)),
        co_quan_ban_hanh=str(than.get("co_quan_ban_hanh", mac_dinh.co_quan_ban_hanh)),
        so_hieu=str(than.get("so_hieu", mac_dinh.so_hieu)),
        dia_danh=str(than.get("dia_danh", mac_dinh.dia_danh)),
        ngay=ngay,
        kinh_gui=str(than.get("kinh_gui", "")),
        quyen_han=str(than.get("quyen_han", mac_dinh.quyen_han)),
        chuc_vu_ky=str(than.get("chuc_vu_ky", mac_dinh.chuc_vu_ky)),
        ho_ten_ky=str(than.get("ho_ten_ky", "")),
        noi_nhan=noi_nhan or mac_dinh.noi_nhan,
        don_vi_luu=str(than.get("don_vi_luu", mac_dinh.don_vi_luu)),
        pham_vi=pham_vi,
        ten_pham_vi=ten_pham_vi,
        ten_goi=str(than.get("ten_goi", mac_dinh.ten_goi)),
        the_thuc=str(than.get("the_thuc", mac_dinh.the_thuc)),
        can_cu_don_vi=mac_dinh.can_cu_don_vi,
    )

    du_lieu = report.loc_pham_vi(kq, pham_vi)
    tep_docx = report.xuat_bao_cao(du_lieu, tt, thu_muc_ra)
    tep_xlsx = report.xuat_phu_luc(du_lieu, tt, thu_muc_ra)

    PHIEN.tep_bao_cao = {"docx": str(tep_docx), "xlsx": str(tep_xlsx)}
    PHIEN.cau_hinh.duong_dan_bao_cao = str(thu_muc_ra)
    PHIEN.cau_hinh.danh_dau_xong(7)
    nhat_ky.ghi("info", f"Bước 7: xuất {tep_docx.name} và {tep_xlsx.name}")

    return JSONResponse(
        {
            "thu_muc": str(thu_muc_ra),
            "docx": tep_docx.name,
            "xlsx": tep_xlsx.name,
            "so_dang_vien": du_lieu.so_dang_vien,
            "ten_pham_vi": ten_pham_vi,
        }
    )


@app.get("/api/buoc7/tai")
async def api_tai_bao_cao(loai: str = "docx"):
    """Tải tệp vừa xuất. Chỉ nhận đúng hai tệp của lần xuất gần nhất."""
    duong_dan = PHIEN.tep_bao_cao.get(loai if loai in ("docx", "xlsx") else "")
    if not duong_dan or not Path(duong_dan).is_file():
        return JSONResponse({"loi": "Chưa xuất báo cáo lần nào."}, status_code=400)
    return FileResponse(duong_dan, filename=Path(duong_dan).name)


# ---------------------------------------------------------------- khởi động


def cong_dang_chay(mac_dinh: int = 8000) -> int:
    """Đọc cổng thật từ tham số dòng lệnh của uvicorn.

    In sai cổng cho người vận hành là lỗi tưởng nhỏ nhưng chặn đứng họ: địa chỉ
    dán vào trình duyệt sẽ không mở được gì, và họ không có cách nào tự đoán ra.
    """
    argv = sys.argv
    for i, tham_so in enumerate(argv):
        if tham_so == "--port" and i + 1 < len(argv) and argv[i + 1].isdigit():
            return int(argv[i + 1])
        if tham_so.startswith("--port=") and tham_so[7:].isdigit():
            return int(tham_so[7:])
    tu_moi_truong = os.environ.get("UVICORN_PORT", "")
    return int(tu_moi_truong) if tu_moi_truong.isdigit() else mac_dinh


def dia_chi_khoi_dong(cong: int | None = None) -> str:
    return f"http://127.0.0.1:{cong or cong_dang_chay()}/buoc/0?t={TOKEN}"


@asynccontextmanager
async def vong_doi(_app: FastAPI):
    dam_bao_danh_muc_ton_tai()
    dia_chi = dia_chi_khoi_dong()
    nhat_ky.ghi("info", f"Khởi động, cổng {cong_dang_chay()}")
    print("\n" + "=" * 68)
    print("  SO HOA HO SO DANG VIEN - dang chay")
    print("=" * 68)
    print(f"  Mo dia chi nay tren trinh duyet:\n  {dia_chi}")
    print("  Dong cua so nay de tat ung dung.")
    print("=" * 68 + "\n")
    try:
        webbrowser.open(dia_chi)
    except Exception:  # noqa: BLE001 - khong mo duoc trinh duyet thi bo qua
        pass
    yield


app.router.lifespan_context = vong_doi
