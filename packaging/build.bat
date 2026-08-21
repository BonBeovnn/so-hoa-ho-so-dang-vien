@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo.
echo ====================================================================
echo   DONG GOI THANH 1 TEP .EXE DUY NHAT (PyInstaller)
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

.venv\Scripts\python.exe -m PyInstaller ^
  --onefile ^
  --console ^
  --name "SoHoa_HoSoDangVien" ^
  --icon "%CD%\packaging\icon.ico" ^
  --distpath "packaging\dist" ^
  --workpath "packaging\build" ^
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
echo   Xong. Tep chay duoc: packaging\dist\SoHoa_HoSoDangVien.exe
echo   Chep rieng tep nay sang may khac la chay duoc, KHONG can cai Python.
echo   Lan dau chay tren mot may se tu sinh thu muc "data" canh tep .exe.
echo.
pause
