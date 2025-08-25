@echo off
echo =====================================
echo    EcoScanner Dependency Installer
echo =====================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Python is installed.
    python --version
    echo.
    goto install_deps
)

echo Python is not installed or not in PATH.
echo.
echo Please install Python first:
echo.
echo 1. Go to: https://www.python.org/downloads/
echo 2. Download Python (latest version)
echo 3. Run the installer
echo 4. IMPORTANT: Check "Add Python to PATH" at the bottom of the installer
echo 5. Click "Install Now"
echo 6. After installation, close this window and run this script again
echo.
pause
exit

:install_deps
:: Install/upgrade pip
echo Ensuring pip is up to date...
python -m pip install --upgrade pip

:: Install Pillow
echo.
echo Installing Pillow...
python -m pip install Pillow

:: Test the installation
echo.
echo Testing installation...
python -c "from PIL import Image; print('Pillow is working correctly!')"

if %errorlevel% equ 0 (
    echo.
    echo =====================================
    echo    SUCCESS! All dependencies installed
    echo =====================================
) else (
    echo.
    echo =====================================
    echo    WARNING: Pillow may not be working
    echo =====================================
    echo Try running: python -m pip install --user Pillow
)

echo.
pause
