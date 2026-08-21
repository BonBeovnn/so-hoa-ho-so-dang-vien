@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ====================================================================
echo   CAI DAT UNG DUNG SO HOA HO SO DANG VIEN
echo ====================================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo   [LOI] Khong tim thay Python tren may nay.
  echo.
  echo   Tai Python 3.14 ban 64-bit tai https://www.python.org/downloads/
  echo   Khi cai nho TICH vao o "Add Python to PATH".
  echo.
  pause
  exit /b 1
)

for /f "delims=" %%v in ('python -c "import sys,platform;print(sys.version.split()[0], platform.machine())"') do set PYVER=%%v
echo   Python tren may: %PYVER%
echo.

if not exist ".venv\Scripts\python.exe" (
  echo   Dang tao moi truong rieng cho ung dung...
  python -m venv .venv
  if errorlevel 1 (
    echo   [LOI] Khong tao duoc moi truong. Xem thong bao ben tren.
    pause
    exit /b 1
  )
)

set DA_CAI=0

if exist "vendor\*.whl" (
  echo   Dang cai tu thu muc vendor ^(khong can mang^)...
  .venv\Scripts\python.exe -m pip install --quiet --no-index --find-links vendor -r requirements.txt
  if errorlevel 1 (
    echo.
    echo   [!] Cai tu vendor khong xong.
    echo       Cac tep .whl trong vendor dung cho Python 3.14 ban 64-bit tren Windows.
    echo       May nay dang chay: %PYVER%
    echo       Se thu tai tu Internet...
    echo.
  ) else (
    set DA_CAI=1
  )
)

if "%DA_CAI%"=="0" (
  echo   Dang tai thu vien tu Internet...
  .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
  if errorlevel 1 (
    echo.
    echo   [LOI] Cai dat that bai. Xem thong bao ben tren.
    echo.
    echo   May khong co mang VA vendor khong dung phien ban Python?
    echo   Cach xu ly: cai dung Python 3.14 ban 64-bit, hoac xin nguoi ban giao
    echo   dung lai thu muc "vendor" tren may co cung phien ban Python voi may nay.
    echo.
    pause
    exit /b 1
  )
)

.venv\Scripts\python.exe -c "import fastapi, uvicorn, openpyxl, docx" 2>nul
if errorlevel 1 (
  echo   [LOI] Cai xong nhung van thieu thu vien. Lien he nguoi ban giao.
  pause
  exit /b 1
)

echo.
echo   Cai dat xong.
echo.
echo   Muon kiem tra may nay chay dung khong, go lenh:
echo       .venv\Scripts\python.exe -m pytest -q
echo   Ket qua dung phai la tat ca test deu xanh.
echo.
echo   Bam dup vao start.bat de chay ung dung.
echo.
pause
