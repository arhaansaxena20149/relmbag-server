@echo off
REM RelmBag Windows EXE Build Script
REM Version: 1.3 - Requires Python 3.14

set VERSION=1.4

REM --- Find the correct Python executable ---
set PYTHON_EXE=
for /f "tokens=*" %%i in ('where /q py ^&^& py -3.14 -c "import sys; print(sys.executable)" 2^>nul') do set PYTHON_EXE=%%i

if not defined PYTHON_EXE (
    echo [ERROR] Python 3.14 is required but not found. Please install from python.org
    pause
    exit /b 1
)

echo Using Python executable: %PYTHON_EXE%
echo ------------------------------------------------

REM --- Ensure apps are not running to avoid file locks ---
taskkill /F /IM "RelmBag Player.exe" /T >nul 2>&1
taskkill /F /IM "RelmBag Admin.exe" /T >nul 2>&1

REM --- Set a local PyInstaller config directory to avoid global permission issues ---
set PYINSTALLER_CONFIG_DIR="%CD%\.pyinstaller_config"
if exist %PYINSTALLER_CONFIG_DIR% rmdir /s /q %PYINSTALLER_CONFIG_DIR%
mkdir %PYINSTALLER_CONFIG_DIR%
set "PYI_CONFIG_DIR=%PYINSTALLER_CONFIG_DIR%"

echo ------------------------------------------------
echo Installing pip for Python...
echo ------------------------------------------------
"%PYTHON_EXE%" -m ensurepip --upgrade

echo ------------------------------------------------
echo Verifying Dependencies...
echo ------------------------------------------------
"%PYTHON_EXE%" -m pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org
"%PYTHON_EXE%" -m pip install -r requirements_client.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
"%PYTHON_EXE%" -m pip install PyInstaller --trusted-host pypi.org --trusted-host files.pythonhosted.org

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b %ERRORLEVEL%
)

echo ------------------------------------------------
echo Building RelmBag Player v%VERSION%...
echo ------------------------------------------------

REM Ensure dist folder is clean and accessible
if exist "dist" rmdir /s /q "dist"
mkdir "dist"

REM Build Player EXE using the Windows spec file
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean "RelmBag Player Windows.spec"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed for Player app
    pause
    exit /b %ERRORLEVEL%
)

echo ------------------------------------------------
echo Building RelmBag Admin v%VERSION%...
echo ------------------------------------------------

REM Build Admin EXE using the Windows spec file
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean "RelmBag Admin Windows.spec"

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
