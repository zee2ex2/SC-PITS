@echo off
setlocal enabledelayedexpansion
set DIR=%~dp0
cd /d "%DIR%"

call venv\Scripts\activate

if exist dist rmdir /S /Q dist
if exist build rmdir /S /Q build

REM Build with --windowed to suppress console window
pyinstaller --windowed --onedir ^
  --name "SC PITS" ^
  --icon "%DIR%icon_PITS.ico" ^
  --add-data "%DIR%templates;templates" ^
  --add-data "%DIR%static;static" ^
  --add-data "%DIR%icon_PITS.png;." ^
  --hidden-import pystray ^
  --hidden-import PIL ^
  --distpath "%DIR%dist" ^
  --workpath "%DIR%build" ^
  --specpath "%DIR%build" ^
  "%DIR%app.py"

set APP_DIR=%DIR%dist\SC PITS

REM Copy user-facing data next to the exe
copy /Y "%DIR%config.json" "%APP_DIR%\"
copy /Y "%DIR%mainInventory" "%APP_DIR%\"
copy /Y "%DIR%icon_PITS.ico" "%APP_DIR%\"
if not exist "%APP_DIR%\dbs" mkdir "%APP_DIR%\dbs"

echo.
echo ===== Build complete! =====
echo   Executable: %APP_DIR%\SC PITS.exe
echo.
echo To create an installer, run Inno Setup with installer.iss
pause