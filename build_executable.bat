@echo off
REM ============================================================
REM  IJ 3D Manager -- Build Script (Windows)
REM  Produces a single-file .exe via PyInstaller.
REM
REM  Usage:
REM    Double-click build_executable.bat  OR
REM    Run from cmd: build_executable.bat
REM
REM  Output: dist\IJ-3D-Manager.exe
REM ============================================================
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo ============================================
echo   IJ 3D Manager -- Build Pipeline (Windows)
echo ============================================

REM -- 1. Activate virtual environment ---------------------------------
if exist "venv\Scripts\activate.bat" (
    echo [1/4] Activating virtual environment...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [1/4] Activating virtual environment (.venv)...
    call .venv\Scripts\activate.bat
) else (
    echo [1/4] No virtual environment found -- using system Python.
)

REM -- 2. Install / upgrade PyInstaller --------------------------------
echo [2/4] Installing/upgrading PyInstaller...
pip install --quiet --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: pip install failed. Make sure Python and pip are on PATH.
    pause
    exit /b 1
)

REM -- 3. Locate CustomTkinter assets ----------------------------------
echo [3/4] Locating CustomTkinter package...
for /f "delims=" %%i in ('python -c "import customtkinter; print(customtkinter.__path__[0])" 2^>nul ^| py -c "import customtkinter; print(customtkinter.__path__[0])" 2^>nul') do (
    set CTK_PATH=%%i
)
if "!CTK_PATH!"=="" (
    echo ERROR: Could not locate CustomTkinter. Is it installed?
    pause
    exit /b 1
)
echo        Found: !CTK_PATH!

REM -- 4. Build --------------------------------------------------------
echo [4/4] Building executable...

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "IJ-3D-Manager" ^
    --add-data "!CTK_PATH!;customtkinter" ^
    --add-data "app_icon.png;." ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "customtkinter" ^
    --collect-submodules customtkinter ^
    app.py

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo   Executable: dist\IJ-3D-Manager.exe
echo.
echo   IMPORTANT -- first run:
echo   Copy the executable to a permanent folder.
echo   The database (print_manager_v2.db) and the
echo   media folder (src_media\) are created next
echo   to the .exe on first launch.
echo   Do NOT run from inside a zip or temp folder.
echo ============================================
pause
endlocal
