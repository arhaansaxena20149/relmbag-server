@echo off
REM RelmBag Windows EXE Build Script
REM Version: 1.2.0

set VERSION=1.2.0
set ICON=assets\icons\pebblit.ico

echo ------------------------------------------------
echo Building RelmBag Player v%VERSION%...
echo ------------------------------------------------

REM Build Player EXE
pyinstaller --noconsole --noconfirm RelmBag.Player.spec

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed for Player app
    pause
    exit /b %ERRORLEVEL%
)

echo ------------------------------------------------
echo Building RelmBag Admin v%VERSION% using spec file...
echo ------------------------------------------------

REM Build Admin EXE
pyinstaller --noconsole --noconfirm RelmBag.Admin.spec

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed for Admin app
    pause
    exit /b %ERRORLEVEL%
)

echo ------------------------------------------------
echo Build Process Complete! Files are in the 'dist' folder.
echo ------------------------------------------------
pause
