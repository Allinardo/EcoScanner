@echo off
title Installing EcoScanner Dependencies
color 0A

echo =====================================
echo    EcoScanner Dependency Installer
echo =====================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH.
    echo.
    
    :: Ask user if they want to install Python
    choice /C YN /M "Do you want to download and install Python automatically"
    if errorlevel 2 goto manual_install
    if errorlevel 1 goto auto_install
    
    :auto_install
    echo.
    echo Downloading Python installer...
    
    :: Detect system architecture
    reg Query "HKLM\Hardware\Description\System\CentralProcessor\0" | find /i "x86" > NUL && set OS_ARCH=32BIT || set OS_ARCH=64BIT
    
    if %OS_ARCH%==64BIT (
        set PYTHON_URL=https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe
        set PYTHON_INSTALLER=python-3.12.0-amd64.exe
    ) else (
        set PYTHON_URL=https://www.python.org/ftp/python/3.12.0/python-3.12.0.exe
        set PYTHON_INSTALLER=python-3.12.0.exe
    )
    
    :: Download Python installer
    powershell -Command "(New-Object Net.WebClient).DownloadFile('%PYTHON_URL%', '%PYTHON_INSTALLER%')"
    
    if not exist %PYTHON_INSTALLER% (
        echo [ERROR] Failed to download Python installer!
        echo Please install Python manually from: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    
    echo.
    echo Installing Python...
    echo IMPORTANT: The installer will open. Please ensure:
    echo   1. Check "Add Python to PATH" at the bottom of the first screen
    echo   2. Click "Install Now"
    echo   3. Wait for installation to complete
    echo   4. Close the installer when done
    echo.
    pause
    
    :: Install Python with PATH automatically added
    start /wait %PYTHON_INSTALLER% /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    
    :: Clean up installer
    del %PYTHON_INSTALLER%
    
    echo.
    echo Python installation attempted. Verifying...
    
    :: Refresh environment variables
    call :RefreshEnv
    
    :: Check again if Python is installed
    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Python still not found in PATH!
        echo.
        echo Please try:
        echo 1. Close this window
        echo 2. Open a NEW Command Prompt
        echo 3. Run this installer again
        echo.
        echo If that doesn't work, manually install Python from:
        echo https://www.python.org/downloads/
        echo.
        echo IMPORTANT: Check "Add Python to PATH" during installation!
        pause
        exit /b 1
    )
    
    goto python_ok
    
    :manual_install
    echo.
    echo Please install Python manually from: https://www.python.org/downloads/
    echo IMPORTANT: Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

:python_ok
echo [OK] Python is installed
python --version
echo.

:: Ensure pip is installed and updated
echo Checking pip installation...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo pip not found. Installing pip...
    echo.
    
    :: Try ensurepip first (comes with Python)
    python -m ensurepip --default-pip >nul 2>&1
    
    if %errorlevel% neq 0 (
        :: If ensurepip fails, download get-pip.py
        echo Downloading get-pip.py...
        powershell -Command "(New-Object Net.WebClient).DownloadFile('https://bootstrap.pypa.io/get-pip.py', 'get-pip.py')"
        
        :: Install pip
        echo Installing pip...
        python get-pip.py
        
        :: Clean up
        del get-pip.py
    )
    
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install pip!
        pause
        exit /b 1
    )
) else (
    echo [OK] pip is installed
    python -m pip --version
)
echo.

:: Upgrade pip to latest version
echo Upgrading pip to latest version...
python -m pip install --upgrade pip
echo.

:: Install Pillow
echo Installing Pillow (PIL fork)...
python -m pip install --upgrade Pillow
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Failed to install with pip directly.
    echo Trying alternative method...
    echo.
    
    :: Try with --user flag if permission issues
    python -m pip install --user --upgrade Pillow
    
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Pillow!
        echo.
        echo Possible solutions:
        echo 1. Run this script as Administrator
        echo 2. Check your internet connection
        echo 3. Try manual installation: python -m pip install Pillow
        pause
        exit /b 1
    )
)
echo.

:: Verify Pillow installation
echo Verifying Pillow installation...
python -c "from PIL import Image; print('[OK] Pillow version:', Image.__version__)"
if %errorlevel% neq 0 (
    echo [ERROR] Pillow installation verification failed!
    echo.
    echo The package may not have installed correctly.
    pause
    exit /b 1
)

echo.
echo =====================================
echo    Installation Complete!
echo =====================================
echo.
echo All dependencies have been successfully installed.
echo You can now run EcoScanner without issues.
echo.
pause
exit /b 0

:: Function to refresh environment variables
:RefreshEnv
echo Refreshing environment variables...
call :GetRegEnv "HKLM\System\CurrentControlSet\Control\Session Manager\Environment" Path Path_HKLM
call :GetRegEnv "HKCU\Environment" Path Path_HKCU
set "Path=%Path_HKLM%;%Path_HKCU%"
goto :eof

:GetRegEnv
for /f "tokens=2*" %%a in ('reg query "%~1" /v "%~2" 2^>nul') do set "%~3=%%b"
goto :eof
