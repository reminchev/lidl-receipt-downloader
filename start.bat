@echo off
chcp 65001 >nul
REM Lidl Receipt Downloader - Avtomatichen start
REM Avtomatichno instalira zavisimosti (ako tryabva) i startira prilozhenieto

echo.
echo ============================================
echo   Lidl Receipt Downloader
echo ============================================
echo.

REM Proverka za Python
echo [1] Proverka za Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   [X] Python ne e nameren!
    echo       Molya instalirajte Python 3.8+ ot https://www.python.org
    echo.
    pause
    exit /b 1
)
echo   [OK] Python nameren
echo.

REM Proverka i sazdavane na virtualna sreda
if not exist "venv" (
    echo [2] Sazdavane na virtualna sreda...
    python -m venv venv
    if errorlevel 1 (
        echo   [X] Greshka pri sazdavane na virtualna sreda
        pause
        exit /b 1
    )
    echo   [OK] Virtualna sreda sazdadena
    echo.
)

REM Aktivirane na virtualnata sreda
echo [3] Aktivirane na virtualna sreda...
call venv\Scripts\activate.bat

REM Proverka dali zavisimostite sa instalirani
pip show playwright >nul 2>&1
if errorlevel 1 (
    echo.
    echo [4] Instalirane na zavisimosti...
    echo     Parvo startirane - tova mozhe da otneme nyakolko minuti...
    echo.
    
    REM Upgrade pip
    python -m pip install --upgrade pip --quiet
    
    REM Instalacia na zavisimosti
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo   [X] Greshka pri instalirane na zavisimosti
        pause
        exit /b 1
    )
    echo   [OK] Zavisimostite sa instalirani
    echo.
    
    REM Instalacia na Playwright brauzari
    echo [5] Instalirane na Playwright brauzar...
    playwright install chromium
    echo   [OK] Chromium instaliran
    echo.
) else (
    echo   [OK] Zavisimostite sa veche instalirani
    echo.
)

REM Startirane na prilozhenieto
echo ============================================
echo   Startirane na prilozhenieto...
echo ============================================
echo.

python lidl_scraper_gui.py

REM Деактивиране на venv
call deactivate

echo.
pause
