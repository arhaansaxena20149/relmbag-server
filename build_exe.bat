@echo off
REM RelmBag Windows EXE Build Script
REM Version: 1.6

set VERSION=1.6

echo ------------------------------------------------
echo Verifying Dependencies...
echo ------------------------------------------------
py -m pip install PyQt5 Pillow requests bcrypt flask PyInstaller

echo ------------------------------------------------
echo Building RelmBag Player v%VERSION%...
echo ------------------------------------------------

REM Build Player EXE using the Windows spec file
REM Using --onefile flag in command line to override if spec is weird
py -m PyInstaller --noconfirm --clean --onefile "RelmBag Player Windows.spec"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed for Player app
    pause
    exit /b %ERRORLEVEL%
)

echo ------------------------------------------------
echo Building RelmBag Admin v%VERSION%...
echo ------------------------------------------------

REM Build Admin EXE using the Windows spec file
py -m PyInstaller --noconfirm --clean --onefile "RelmBag Admin Windows.spec"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed for Player app
    pause
    exit /b %ERRORLEVEL%
)

echo ------------------------------------------------
echo Building RelmBag Admin v%VERSION%...
echo ------------------------------------------------

REM Build Admin EXE using the Windows spec file
py -m PyInstaller --noconfirm --clean "RelmBag Admin Windows.spec"

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
