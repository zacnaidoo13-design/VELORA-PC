@echo off
cd /d "%~dp0"
py -m pip install --upgrade pip
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --clean --onefile --windowed --name VELORA velora.py
if errorlevel 1 (echo Build failed & pause & exit /b 1)
echo Built: dist\VELORA.exe
pause
