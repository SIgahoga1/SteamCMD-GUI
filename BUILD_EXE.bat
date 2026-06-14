@echo off
rem Build SteamCMDv2.exe (PyInstaller onefile)
rem Requires Python 3.12 installed (py launcher)

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found. Install Python 3.12 from python.org
  pause
  exit /b 1
)

echo Installing dependencies...
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies
  pause
  exit /b 1
)

echo Building exe...
py -3.12 build.py
if errorlevel 1 (
  echo BUILD FAILED
  pause
  exit /b 1
)

echo.
echo DONE! Your exe: dist\SteamCMDv2.exe
pause
