# Hướng dẫn đẩy mã nguồn lên GitHub công khai

Dành cho tác giả. Làm đúng thứ tự dưới đây, **không bỏ bước 1**.

> **Điều cần thuộc trước tiên:** Git công khai là **không thu hồi được**. Xóa một
> tệp ở lần commit sau **không** xóa nó khỏi lịch sử, và trong khoảng thời gian
> nó còn trên GitHub thì các dịch vụ quét mã nguồn đã kịp sao lưu. Một dòng
> `manifest_*.csv` lọt ra là lộ số căn cước công dân của đảng viên có thật.

---

## Bước 1 — Soi dữ liệu cá nhân (bắt buộc)

```bat
cd D:\So_hoa_du_lieu_Dang_vien_Vien_chuc\3.So_Hoa\APP
.venv\Scripts\python.exe scripts\kiem_truoc_khi_day.py
```

Script chỉ soi **những tệp Git sẽ theo dõi** (đã trừ `.gitignore`) và tìm:

* dãy 9–12 chữ số có thể là số căn cước hoặc số thẻ đảng viên;
* đường dẫn ổ đĩa lộ tên tài khoản Windows;
* tệp `.xlsx` `.csv` `.docx` `.log` lẽ ra phải bị chặn mà vẫn lọt vào;
* tệp nhị phân lớn hơn 2 MB.

Chỉ đẩy khi script in **“Không thấy gì đáng ngại.”**

### Những thứ tuyệt đối không được lên GitHub

| Thứ | Vì sao |
| :--- | :--- |
| `app/data/manifest_*.csv` | Đường dẫn đích chứa tên thư mục đảng viên, mà tên đó **có số căn cước** |
| `app/data/app.log` | Nhật ký vận hành, có đường dẫn ổ đĩa thật của cơ quan |
| `app/data/cau_hinh.json` | Đường dẫn ổ đĩa thật |
| `DS_DANGVIEN.xlsx`, `MAIN.xlsx` | Toàn bộ danh sách đảng viên |
| `vendor/` | 29 tệp `.whl`, gần 10 MB, chỉ chạy với đúng một phiên bản Python |

`.gitignore` đã chặn sẵn tất cả. **Đừng dùng `git add -f` để lách.**

> Trong mã nguồn và test, mọi họ tên và số căn cước đều là **hư cấu**: số bắt
> đầu bằng `099` hoặc `0012` là mã tỉnh không tồn tại. Các test chạy trên dữ
> liệu thật của Viện đều kiểm bằng **dấu hiệu kỹ thuật** chứ không ghi tên
> người, và tự bỏ qua khi không tìm thấy tệp thật.

---

## Bước 2 — Chạy lại test và chụp lại ảnh

```bat
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\chup_anh.py
```

Test phải xanh hết. Ảnh chụp dùng đảng bộ hư cấu, không phải dữ liệu Viện.

---

## Bước 3 — Khởi tạo kho và commit đầu tiên

Đặt tên và email cho Git nếu máy chưa cấu hình:

```bat
git config --global user.name "anhduc97"
git config --global user.email "email-cua-anh@example.com"
```

Rồi:

```bat
cd D:\So_hoa_du_lieu_Dang_vien_Vien_chuc\3.So_Hoa\APP
git init -b main
git add .
git status
```

**Đọc kỹ danh sách `git status` in ra.** Thấy bất kỳ tệp nào trong bảng “tuyệt
đối không được lên” ở trên thì dừng lại, sửa `.gitignore`, chạy
`git rm --cached <tệp>` rồi làm lại. Chạy lại script bước 1 một lần nữa cho chắc
— lần này nó dùng đúng danh sách của Git:

```bat
.venv\Scripts\python.exe scripts\kiem_truoc_khi_day.py
git commit -m "Ban dau: ung dung so hoa ho so dang vien"
```

---

## Bước 4 — Tạo kho trên GitHub và đẩy lên

Tạo kho **rỗng** trên GitHub (đừng tick “Add a README” — đã có sẵn rồi), đặt tên
ví dụ `so-hoa-ho-so-dang-vien`. Sau đó:

```bat
git remote add origin https://github.com/anhduc97/so-hoa-ho-so-dang-vien.git
git push -u origin main
```

Lần đầu Git sẽ hỏi đăng nhập. Dùng **Personal Access Token** chứ không phải mật
khẩu tài khoản: GitHub → *Settings* → *Developer settings* → *Personal access
tokens* → *Fine-grained tokens*, cấp quyền `Contents: Read and write` cho đúng
kho này.

---

## Bước 5 — Dựng lại trang kho cho tử tế

Sau khi đẩy xong, vào trang kho trên GitHub:

1. **About** (bánh răng góc phải): mô tả ngắn, thêm *Topics* —
   `vietnamese`, `government`, `document-management`, `fastapi`, `offline-first`.
2. **Settings → Features**: tắt *Wikis* và *Projects* nếu không dùng; giữ
   *Issues* để nhận báo lỗi.
3. **Settings → Code security**: bật *Secret scanning* và *Push protection* —
   GitHub sẽ chặn ngay nếu lần sau có khóa bí mật lọt vào.
4. Kiểm tra GitHub đã nhận diện đúng giấy phép: vì `LICENSE` là giấy phép tự
   soạn, GitHub sẽ ghi *“Unrecognized license”*. Đó là **đúng ý** — nó nhắc
   người đọc phải mở tệp ra đọc thay vì đoán là MIT.

---

## Về việc “không cho ai copy ý tưởng”

Nói thẳng để anh khỏi trông chờ nhầm chỗ: **mã nguồn đã công khai thì không có
biện pháp kỹ thuật nào ngăn được sao chép.** Làm rối mã (obfuscate) hay biên
dịch sang `.pyc` chỉ làm chậm người tò mò vài giờ, mà lại phá luôn mục tiêu
“mã nguồn mở và sạch để chạy local”. Hai thứ đó loại trừ nhau.

Cái thực sự bảo vệ được là **pháp lý và dấu vết**:

| Lớp | Đã có sẵn trong kho |
| :--- | :--- |
| Giấy phép hạn chế | `LICENSE` — cho dùng nội bộ, **cấm** phân phối lại và dùng thương mại |
| Ghi nhận tác giả | `NOTICE.md`, chân mọi trang giao diện, trang Hướng dẫn |
| Dấu vết trong sản phẩm | Tác giả nằm trong thuộc tính tệp `.docx`/`.xlsx` app xuất ra |
| Mốc thời gian công khai | Chính lịch sử commit trên GitHub — bằng chứng ai làm trước |

Muốn chắc hơn nữa:

* **Đăng ký quyền tác giả** tại Cục Bản quyền tác giả (Bộ VH-TT-DL). Chi phí
  thấp, và giấy chứng nhận là bằng chứng mạnh nhất khi có tranh chấp.
* **Ký commit bằng GPG** để không ai giả mạo được tác giả của commit.
* Nếu về sau muốn thương mại hóa: giữ **phần lõi thật sự có giá trị** ở kho
  riêng, kho công khai chỉ để bản dùng được. Nhưng phải quyết trước khi đẩy —
  tách ra sau khi đã công khai thì không còn nghĩa lý gì.

---

## Bảo trì về sau

Trước **mỗi lần** `git push`:

```bat
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\kiem_truoc_khi_day.py
```

Muốn chạy tự động, đặt tệp `.git/hooks/pre-push` (không có phần mở rộng):

```sh
#!/bin/sh
# PYTHONUTF8=1 bắt buộc: thiếu dòng này, cửa sổ dòng lệnh Git trên Windows
# thường chạy sai codepage và script tiếng Việt bị UnicodeEncodeError ngay
# dòng in đầu tiên — chặn nhầm lệnh đẩy vì lý do không liên quan tới nội dung
# kiểm tra thật.
PYTHONUTF8=1 exec .venv/Scripts/python.exe scripts/kiem_truoc_khi_day.py
```

Hook trả mã thoát khác 0 là Git hủy lệnh đẩy.

---

## Lỡ đẩy nhầm dữ liệu cá nhân thì làm gì

Nhanh và dứt khoát, theo đúng thứ tự:

1. **Xóa kho ngay** (Settings → Danger Zone → Delete this repository). Xóa cả
   kho nhanh hơn và chắc hơn nhiều so với gỡ một tệp khỏi lịch sử.
2. Dọn sạch dữ liệu ở máy, chạy lại `scripts\kiem_truoc_khi_day.py`.
3. Xóa thư mục `.git` cũ, `git init` lại từ đầu — **đừng** cố sửa lịch sử cũ
   rồi đẩy lại; các bản sao (fork, cache) của lịch sử cũ vẫn còn.
4. Vì dữ liệu là thông tin cá nhân của đảng viên, **báo cho lãnh đạo đơn vị**.
   Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân có quy định trách nhiệm
   thông báo khi xảy ra sự cố.
