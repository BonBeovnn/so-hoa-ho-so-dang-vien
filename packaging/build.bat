@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

set CHE_DO=onefile
set THU_MUC_RA=packaging\dist
set THU_MUC_LAM_VIEC=packaging\build
if /i "%~1"=="onedir" (
  set CHE_DO=onedir
  set THU_MUC_RA=packaging\dist_onedir
  set THU_MUC_LAM_VIEC=packaging\build_onedir
)

echo.
echo ====================================================================
echo   DONG GOI ^(%CHE_DO%^) BANG PyInstaller
echo ====================================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo   [LOI] Chua co moi truong .venv. Chay install.bat truoc.
  pause
  exit /b 1
)

.venv\Scripts\python.exe -c "import PyInstaller" 2>nul
if errorlevel 1 (
  echo   Dang cai PyInstaller ^(chi can cho lan dong goi, khong di kem ban .exe^)...
  .venv\Scripts\python.exe -m pip install --quiet pyinstaller
  if errorlevel 1 (
    echo   [LOI] Khong cai duoc PyInstaller. Can mang de tai lan dau.
    pause
    exit /b 1
  )
)

if not exist "packaging\icon.ico" (
  echo   Dang dung bieu tuong mau do tu app\static\img\meo-may.svg...
  .venv\Scripts\python.exe -c "import svglib, reportlab" 2>nul
  if errorlevel 1 (
    .venv\Scripts\python.exe -m pip install --quiet svglib reportlab pillow
  )
  .venv\Scripts\python.exe packaging\tao_icon.py
  if errorlevel 1 (
    echo   [LOI] Khong dung duoc bieu tuong. Xem thong bao ben tren.
    pause
    exit /b 1
  )
)

echo.
echo   Dang dong goi... viec nay mat vai phut.
echo.

rem PyInstaller giai nghia duong dan tuong doi trong --add-data/--icon theo
rem --specpath, khong phai theo thu muc dang dung lenh. Dung duong dan tuyet
rem doi (%CD%, tuc APP sau khi cd o tren) de khong bi lech.
rem
rem --noupx: khong nen bang UPX. Nen UPX lam entropy overlay cang cao, day
rem la mot trong nhung dau hieu he thong quet virus theo kieu du doan (may
rem hoc) dung de nghi ngo tep bi dong goi/an giau — tranh duoc chung nao hay
rem chung nay, du ban than PyInstaller --onefile da khong the tranh het.

.venv\Scripts\python.exe -m PyInstaller ^
  --%CHE_DO% ^
  --console ^
  --noupx ^
  --name "SoHoa_HoSoDangVien" ^
  --icon "%CD%\packaging\icon.ico" ^
  --distpath "%THU_MUC_RA%" ^
  --workpath "%THU_MUC_LAM_VIEC%" ^
  --specpath "packaging" ^
  --add-data "%CD%\app\templates;app\templates" ^
  --add-data "%CD%\app\static;app\static" ^
  --add-data "%CD%\app\data\danh_muc_file.json;app\data" ^
  --collect-all uvicorn ^
  --noconfirm ^
  "packaging\khoi_dong.py"

if errorlevel 1 (
  echo.
  echo   [LOI] Dong goi that bai. Xem thong bao PyInstaller ben tren.
  pause
  exit /b 1
)

echo.
if /i "%CHE_DO%"=="onefile" echo   Xong. Tep chay duoc: %THU_MUC_RA%\SoHoa_HoSoDangVien.exe
if /i "%CHE_DO%"=="onefile" echo   Chep rieng tep nay sang may khac la chay duoc, KHONG can cai Python.
if /i not "%CHE_DO%"=="onefile" echo   Xong. Chep CA THU MUC %THU_MUC_RA%\SoHoa_HoSoDangVien sang may khac.
if /i not "%CHE_DO%"=="onefile" echo   Roi chay SoHoa_HoSoDangVien.exe nam trong thu muc do.
echo   Lan dau chay tren mot may se tu sinh thu muc data canh tep .exe.
echo.
echo   Luu y: tep .exe chua ky so nen mot vai phan mem diet virus, vi du Bkav
echo   hoac Windows Defender, co the bao nham do chua ro nguon goc. Day la
echo   canh bao du doan bang may hoc, khong phai virus that. Xem muc
echo   "Neu bi bao nham virus" trong README.md de biet cach kiem chung va
echo   gui bao cao false positive. Neu Bkav chan han viec chay, dung lenh
echo   packaging\build.bat onedir de dong goi thanh 1 thu muc thay vi 1 tep -
echo   cach nay thuong it bi bao nham hon.
echo.
pause
