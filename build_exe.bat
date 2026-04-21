@echo off
REM RelmBag Windows EXE Build Script
REM Version: 1.9 - Requires Python 3.11 or 3.12 (NOT 3.14 - PyQt5 has no wheels for it)

set VERSION=1.3
set PYTHON_CMD=py -3.12

REM Check if Python 3.12 is available, fallback to 3.11 if not
%PYTHON_CMD% --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    set PYTHON_CMD=py -3.11
    %PYTHON_CMD% --version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Python 3.11 or 3.12 is required but not found. Please install from python.org
        pause
        exit /b 1
    )
)

echo Using Python: %PYTHON_CMD%
echo ------------------------------------------------
echo Verifying Dependencies...
echo ------------------------------------------------
%PYTHON_CMD% -m pip install PyQt5 Pillow requests bcrypt flask PyInstaller

echo ------------------------------------------------
echo Building RelmBag Player v%VERSION%...
echo ------------------------------------------------

REM Build Player EXE using the Windows spec file
%PYTHON_CMD% -m PyInstaller --noconfirm --clean "RelmBag Player Windows.spec"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed for Player app
    pause
    exit /b %ERRORLEVEL%
)

echo ------------------------------------------------
echo Building RelmBag Admin v%VERSION%...
echo ------------------------------------------------

REM Build Admin EXE using the Windows spec file
%PYTHON_CMD% -m PyInstaller --noconfirm --clean "RelmBag Admin Windows.spec"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed for Admin app
    pause
    exit /b %ERRORLEVEL%
)

REM Cleanup root from old release EXEs
del /Q RelmBag.Player.*.exe 2>nul
del /Q RelmBag.Admin.*.exe 2>nul

REM Copy new release EXEs to root
copy /Y "dist\RelmBag Player.exe" "RelmBag.Player.%VERSION%.exe" >nul
copy /Y "dist\RelmBag Admin.exe" "RelmBag.Admin.%VERSION%.exe" >nul

echo ------------------------------------------------
echo Build Process Complete!
echo Files are in the 'dist' folder and versioned copies in root.
echo ------------------------------------------------
pause
