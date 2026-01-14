@echo off
chcp 65001 >nul
REM Lidl Receipt Downloader - Auto Start

echo.
echo ============================================
echo   Lidl Receipt Downloader
echo ============================================
echo.

REM Check for Python
echo [1] Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   [X] Python not found!
    echo       Please install Python 3.8+ from https://www.python.org
    echo.
    pause
    exit /b 1
)
echo   [OK] Python found
echo.

REM Check and create virtual environment
if not exist "venv" (
    echo [2] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo   [X] Error creating virtual environment
        pause
        exit /b 1
    )
    echo   [OK] Virtual environment created
    echo.
)

REM Activate virtual environment
echo [3] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
pip show playwright >nul 2>&1
if errorlevel 1 (
    echo.
    echo [4] Installing dependencies...
    echo     First run - this may take a few minutes...
    echo.
    
    REM Upgrade pip
    python -m pip install --upgrade pip --quiet
    
    REM Install dependencies
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo   [X] Error installing dependencies
        pause
        exit /b 1
    )
    echo   [OK] Dependencies installed
    echo.
    
    REM Install Playwright browsers
    echo [5] Installing Playwright browser...
    playwright install chromium
    echo   [OK] Chromium installed
    echo.
) else (
    echo   [OK] Dependencies already installed
    echo.
)

REM Start the application
echo ============================================
echo   Starting application...
echo ============================================
echo.

python lidl_scraper_gui.py

REM Deactivate venv
call deactivate

echo.
pause
