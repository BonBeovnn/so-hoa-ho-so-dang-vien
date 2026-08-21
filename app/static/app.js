/* Kịch bản dùng chung. Không thư viện ngoài — app chạy hoàn toàn ngoại tuyến. */

function hien(el) { if (el) el.hidden = false; }
function an(el) { if (el) el.hidden = true; }

/* Số lượng tệp lên tới hàng nghìn. "8000" đọc chậm hơn "8.000" một nhịp, mà
   nhịp đó lặp lại ở mọi bước. Dùng Intl để đúng quy ước phân nhóm tiếng Việt
   thay vì tự chèn dấu chấm bằng tay. */
const _dinhDangSo = new Intl.NumberFormat('vi-VN');
function soVN(n) {
  return typeof n === 'number' && Number.isFinite(n) ? _dinhDangSo.format(n) : n;
}

/** Gọi API, tự hiển thị lỗi vào #hop-loi. Trả về null nếu lỗi.
    duLieu là FormData thì gửi biểu mẫu, là object thì gửi JSON. */
async function goiApi(dia_chi, duLieu) {
  const hopLoi = document.getElementById('hop-loi');
  const bao = (t) => { if (hopLoi) { hopLoi.textContent = t; hien(hopLoi); } };

  let tra;
  try {
    tra = await fetch(dia_chi, (duLieu instanceof FormData)
      ? { method: 'POST', body: duLieu }
      : { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(duLieu) });
  } catch (e) {
    /* Chỉ lỗi mạng thật mới rơi vào đây: ứng dụng đã tắt hẳn. */
    bao('Không liên lạc được với ứng dụng.\n'
      + 'Kiểm tra xem cửa sổ đen (cửa sổ dòng lệnh) còn đang chạy không.');
    return null;
  }

  let d = null;
  try { d = await tra.json(); } catch (e) { d = null; }

  if (!tra.ok) {
    /* Máy chủ CÓ trả lời, chỉ là trả lỗi. Không được báo mất liên lạc: bản cũ
       đổ tội cho mạng nên người dùng không biết lỗi thật nằm ở đâu. */
    bao((d && d.loi)
      || ('Ứng dụng báo lỗi ' + tra.status + '.\n'
          + 'Xem cửa sổ đen (cửa sổ dòng lệnh) để biết chi tiết.'));
    return null;
  }
  if (hopLoi) an(hopLoi);
  return d;
}

/* ------------------------------------------- hộp thoại chọn thư mục / tệp
   Trình duyệt không lấy được đường dẫn thư mục trên máy, nên máy chủ tự liệt
   kê rồi gửi về. Xem app/core/paths.py để biết lý do đầy đủ. */

let _oDich = null;      // id của ô nhập sẽ nhận kết quả
let _cheDo = 'thu_muc'; // 'thu_muc' hoặc 'tep'
let _duoi = '';         // ví dụ '.xlsx'
let _hienTai = null;
let _nutMo = null;      // phần tử đang được focus lúc mở, để trả focus về

function moDuyet(idO, cheDo, duoi) {
  _oDich = idO;
  _cheDo = cheDo || 'thu_muc';
  _duoi = duoi || '';
  _nutMo = document.activeElement;
  document.getElementById('duyet-tieu-de').textContent =
    _cheDo === 'tep' ? 'Chọn tệp ' + _duoi : 'Chọn thư mục';
  document.getElementById('duyet-chon').hidden = (_cheDo === 'tep');

  const dangCo = document.getElementById(idO).value.trim();
  const batDau = dangCo ? dangCo.replace(/[\\/][^\\/]*$/, '') : '';
  hien(document.getElementById('lop-duyet'));
  /* Đưa focus vào hộp thoại: không làm thì phím Tab tiếp theo rơi xuống
     trang phía sau, người dùng bàn phím lạc ra ngoài mà không biết. */
  document.querySelector('#lop-duyet .hop-dau .dong').focus();
  taiThuMuc(batDau);
}

function dongDuyet() {
  const lop = document.getElementById('lop-duyet');
  if (!lop || lop.hidden) return;
  an(lop);
  if (_nutMo && document.contains(_nutMo)) _nutMo.focus();
  _nutMo = null;
}

/* Giữ phím Tab quẩn trong hộp thoại chừng nào nó còn mở. */
function _giuTab(e) {
  const lop = document.getElementById('lop-duyet');
  if (!lop || lop.hidden || e.key !== 'Tab') return;
  const duocFocus = [...lop.querySelectorAll('button, input, select, textarea')]
    .filter((el) => !el.disabled && !el.hidden && el.offsetParent !== null);
  if (!duocFocus.length) return;
  const dau = duocFocus[0];
  const cuoi = duocFocus[duocFocus.length - 1];
  if (e.shiftKey && document.activeElement === dau) { e.preventDefault(); cuoi.focus(); }
  else if (!e.shiftKey && document.activeElement === cuoi) { e.preventDefault(); dau.focus(); }
}

async function taiThuMuc(duongDan) {
  const ds = document.getElementById('duyet-danh-sach');
  ds.replaceChildren();
  const dangDoc = document.createElement('li');
  const nutDoc = document.createElement('button');
  nutDoc.type = 'button';
  nutDoc.disabled = true;
  nutDoc.textContent = 'Đang đọc…';
  dangDoc.appendChild(nutDoc);
  ds.appendChild(dangDoc);

  const q = new URLSearchParams({ p: duongDan || '' });
  if (_cheDo === 'tep' && _duoi) q.set('tep', _duoi);

  let d;
  try {
    const tra = await fetch('/api/duyet?' + q.toString());
    d = await tra.json();
    if (!tra.ok) throw new Error(d.loi);
  } catch (e) {
    ds.replaceChildren();
    const li = document.createElement('li');
    const nut = document.createElement('button');
    nut.type = 'button';
    nut.disabled = true;
    nut.textContent = e.message || 'Không đọc được thư mục.';
    li.appendChild(nut);
    ds.appendChild(li);
    return;
  }

  _hienTai = d.hien_tai;
  document.getElementById('duyet-duong-dan').textContent = d.hien_tai || 'Chọn một ổ đĩa';
  document.getElementById('duyet-do-dai').textContent =
    d.hien_tai ? `${d.do_dai} ký tự` : '';

  const oDia = document.getElementById('duyet-o-dia');
  oDia.replaceChildren();
  (d.o_dia || []).forEach((o) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'nut'; b.textContent = o;
    b.onclick = () => taiThuMuc(o);
    oDia.appendChild(b);
  });

  ds.replaceChildren();
  const them = (nhan, xuLy, lopCss) => {
    const li = document.createElement('li');
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = nhan;
    if (lopCss) b.className = lopCss;
    b.onclick = xuLy;
    li.appendChild(b);
    ds.appendChild(li);
  };

  if (d.cha) them('⬑  .. (lên thư mục cha)', () => taiThuMuc(d.cha));
  (d.thu_muc || []).forEach((t) =>
    them('📁  ' + t, () => taiThuMuc(noi(d.hien_tai, t))));
  (d.tep || []).forEach((t) =>
    them('📄  ' + t, () => chonTep(noi(d.hien_tai, t)), 'la-tep'));

  if (!ds.children.length) them('(thư mục rỗng)', () => {}, null);
}

function noi(cha, con) {
  return cha.endsWith('\\') || cha.endsWith('/') ? cha + con : cha + '\\' + con;
}

function chonTep(duongDan) {
  document.getElementById(_oDich).value = duongDan;
  dongDuyet();
}

document.addEventListener('DOMContentLoaded', () => {
  const nutChon = document.getElementById('duyet-chon');
  if (nutChon) nutChon.onclick = () => {
    if (_hienTai) document.getElementById(_oDich).value = _hienTai;
    dongDuyet();
  };
  const lop = document.getElementById('lop-duyet');
  if (lop) lop.addEventListener('click', (e) => { if (e.target === lop) dongDuyet(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') dongDuyet();
    _giuTab(e);
  });
});
