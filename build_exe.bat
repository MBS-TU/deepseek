@echo off
setlocal
cd /d "%~dp0"

set "PY=venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name FeiyuPet ^
  --icon assets\icon.ico ^
  --version-file version_info.txt ^
  --add-data "assets;assets" ^
  --hidden-import pynput.keyboard._win32 ^
  --hidden-import pynput.mouse._win32 ^
  --distpath dist ^
  --workpath build ^
  main.py

if errorlevel 1 (
  echo.
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo Build complete: dist\FeiyuPet.exe
pause
