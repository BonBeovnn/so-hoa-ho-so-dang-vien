"""Soi kho mã nguồn trước khi đẩy lên GitHub công khai.

Chạy:  .venv\\Scripts\\python.exe scripts\\kiem_truoc_khi_day.py

Vì sao cần
----------
Git công khai là **không thu hồi được**. Xóa tệp ở lần commit sau không xóa nó
khỏi lịch sử, và trong khoảng thời gian nó còn trên GitHub thì các dịch vụ quét
mã nguồn đã kịp lưu lại. Một dòng ``manifest_*.csv`` lọt ra là lộ số căn cước
công dân của đảng viên có thật.

Script này soi **đúng những tệp sẽ được đẩy lên** (đã trừ .gitignore) và tìm:

* dãy 9–12 chữ số — có thể là số căn cước hoặc số thẻ đảng viên;
* đường dẫn ổ đĩa của máy người viết mã, kèm tên tài khoản Windows;
* tệp dữ liệu lẽ ra phải bị .gitignore chặn nhưng vẫn lọt vào;
* tệp nhị phân to bất thường.

Trả về mã thoát khác 0 nếu có phát hiện, để dùng được trong hook trước khi đẩy.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]

# Dãy 9–12 chữ số đứng riêng. Cùng bộ quy tắc với app/core/nhat_ky.py.
MAU_DINH_DANH = re.compile(r"(?<!\d)\d{9,12}(?!\d)")

# Đường dẫn tuyệt đối trên máy người viết mã.
MAU_DUONG_DAN = re.compile(r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s\"']+", re.I)

DUOI_DU_LIEU = {".xlsx", ".xls", ".xlsm", ".csv", ".docx", ".doc", ".pdf", ".log", ".zip"}
DUOI_NHI_PHAN = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".whl", ".zip", ".pdf"}

GIOI_HAN_BYTE = 2 * 1024 * 1024

# Số hư cấu dùng trong test và ảnh minh họa. Có mặt là bình thường.
SO_HU_CAU = {
    # Số căn cước bịa dùng trong test và tài liệu. Mở đầu 099 và 0012 là mã
    # tỉnh không tồn tại, nên không đụng vào số của ai.
    "099001110001", "099002220002", "099003330003", "099004440004",
    "001199000111", "001199000222", "001199000333",
    "001199000444", "001199000555", "001199000666",
    "012345678901", "012345678902", "012345678903",
    "123456789",
    # Mã tổ chức đảng viết liền, không phải số định danh cá nhân.
    "381680530000", "38168053000001",
}

# Tệp được phép chứa dãy số dài: chính là nơi định nghĩa và kiểm thử quy tắc.
MIEN_TRU = {
    "scripts/kiem_truoc_khi_day.py",
    "app/core/nhat_ky.py",
    "app/core/chan_doan.py",
}


def tep_se_day_len() -> list[Path]:
    """Danh sách tệp Git sẽ theo dõi, tức là đã trừ .gitignore."""
    try:
        ra = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=GOC,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        print("! Chưa phải kho git. Tự đọc .gitignore để đoán danh sách tệp.")
        print("  Chạy lại sau khi `git init` để có danh sách chính xác của Git.")
        print("")
        return _tep_theo_gitignore()
    return [GOC / dong for dong in ra.stdout.splitlines() if dong.strip()]


def _luat_gitignore() -> tuple[list[str], list[str]]:
    """Đọc .gitignore thành (luật chặn, luật mở lại).

    Chỉ hiểu ba dạng thực sự có trong tệp này: ``thu_muc/``, ``*.duoi`` và
    ``!mo_lai``. Không cố viết lại toàn bộ ngữ pháp gitignore — chỗ nào cần
    chính xác tuyệt đối thì đã có ``git ls-files`` lo.
    """
    tep = GOC / ".gitignore"
    chan: list[str] = []
    mo_lai: list[str] = []
    if not tep.is_file():
        return chan, mo_lai
    for dong in tep.read_text(encoding="utf-8").splitlines():
        dong = dong.strip()
        if not dong or dong.startswith("#"):
            continue
        (mo_lai if dong.startswith("!") else chan).append(dong.lstrip("!"))
    return chan, mo_lai


def _khop(ten: str, mau: str) -> bool:
    from fnmatch import fnmatch

    if mau.endswith("/"):
        thu_muc = mau.rstrip("/")
        return ten == thu_muc or ten.startswith(thu_muc + "/")
    if mau.endswith("/*"):
        return ten.startswith(mau[:-1])
    return fnmatch(ten, mau) or fnmatch(ten.rsplit("/", 1)[-1], mau)


def _tep_theo_gitignore() -> list[Path]:
    chan, mo_lai = _luat_gitignore()
    ra: list[Path] = []
    for tep in sorted(GOC.rglob("*")):
        if not tep.is_file():
            continue
        ten = tep.relative_to(GOC).as_posix()
        if ten.startswith(".git/"):
            continue
        bi_chan = any(_khop(ten, m) for m in chan)
        if bi_chan and not any(_khop(ten, m) for m in mo_lai):
            continue
        ra.append(tep)
    return ra


def doc_chu(tep: Path) -> str | None:
    if tep.suffix.lower() in DUOI_NHI_PHAN:
        return None
    try:
        return tep.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return None


def main() -> int:
    cac_tep = tep_se_day_len()
    print(f"Soi {len(cac_tep)} tệp sẽ được đẩy lên.\n")

    phat_hien: list[str] = []

    for tep in cac_tep:
        ten_tuong_doi = tep.relative_to(GOC).as_posix()

        if tep.suffix.lower() in DUOI_DU_LIEU:
            phat_hien.append(
                f"[TỆP DỮ LIỆU] {ten_tuong_doi} — .gitignore lẽ ra phải chặn đuôi này"
            )

        try:
            co = tep.stat().st_size
        except OSError:
            co = 0
        if co > GIOI_HAN_BYTE:
            phat_hien.append(f"[TỆP TO] {ten_tuong_doi} — {co / 1e6:.1f} MB")

        if ten_tuong_doi in MIEN_TRU:
            continue

        chu = doc_chu(tep)
        if chu is None:
            continue

        for so_dong, dong in enumerate(chu.splitlines(), 1):
            for khop in MAU_DINH_DANH.finditer(dong):
                if khop.group() in SO_HU_CAU:
                    continue
                phat_hien.append(
                    f"[SỐ ĐỊNH DANH?] {ten_tuong_doi}:{so_dong} — {khop.group()}"
                )
            for khop in MAU_DUONG_DAN.finditer(dong):
                phat_hien.append(
                    f"[ĐƯỜNG DẪN MÁY] {ten_tuong_doi}:{so_dong} — {khop.group()}"
                )

    if not phat_hien:
        print("Không thấy gì đáng ngại. Đẩy lên được.")
        return 0

    print(f"{len(phat_hien)} chỗ cần xem lại:\n")
    for dong in phat_hien:
        print("  " + dong)
    print(
        "\nXem từng dòng một. Số hư cấu trong test hoặc ví dụ thì thêm vào SO_HU_CAU\n"
        "trong chính script này; số thật thì XÓA rồi mới đẩy."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
