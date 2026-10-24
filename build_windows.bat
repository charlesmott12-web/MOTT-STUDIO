@echo off
setlocal
cd /d "%~dp0"
echo Building Mott Studio for Windows using free tools...
where py >nul 2>nul
if errorlevel 1 (
 echo Python 3.11 or 3.12 is needed ONLY on the computer building the EXE.
 echo Visit https://www.python.org/downloads/windows/ and install Python.
 pause
 exit /b 1
)
py -m venv .buildenv
if errorlevel 1 goto fail
call .buildenv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto fail
python -m pip install -r requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto fail
python -m PyInstaller --noconfirm --clean --windowed --onedir --name "MottStudio" mott_studio.py
if errorlevel 1 goto fail
 echo.
 echo Build complete: dist\MottStudio\MottStudio.exe
 echo Keep the whole MottStudio folder together. Copy it to any Windows PC.
 pause
 exit /b 0
:fail
echo Build failed. Read the error above.
pause
exit /b 1
