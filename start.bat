@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   Chua cai dat. Hay bam dup vao install.bat truoc.
  echo.
  pause
  exit /b 1
)

echo.
echo   Dang khoi dong ung dung so hoa ho so dang vien...
echo   KHONG dong cua so nay trong luc dang lam viec.
echo.

.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo   Ung dung da dung.
pause
