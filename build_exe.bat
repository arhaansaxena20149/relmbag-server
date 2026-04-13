@echo off
REM RelmBag Windows EXE Build Script
REM Version: 1.2

set VERSION=1.2
set ICON=assets\icons\pebblit.ico

echo ------------------------------------------------
echo Building RelmBag Player v%VERSION%...
echo ------------------------------------------------

REM Build Player EXE
py -m PyInstaller --noconfirm --clean --windowed --onefile --name "RelmBag Player" --add-data="assets;assets" -i %ICON% game.py

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed for Player app
    pause
    exit /b %ERRORLEVEL%
)

echo ------------------------------------------------
echo Building RelmBag Admin v%VERSION%...
echo ------------------------------------------------

REM Build Admin EXE
py -m PyInstaller --noconfirm --clean --windowed --onefile --name "RelmBag Admin" --add-data="assets;assets" -i %ICON% admin.py

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed for Admin app
    pause
    exit /b %ERRORLEVEL%
)

copy /Y "dist\RelmBag Player.exe" "RelmBag.Player.%VERSION%.exe" >nul
copy /Y "dist\RelmBag Admin.exe" "RelmBag.Admin.%VERSION%.exe" >nul

echo ------------------------------------------------
echo Build Process Complete! Files are in the 'dist' folder and versioned release copies are in the repo root.
echo ------------------------------------------------
pause
