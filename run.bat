@echo off
REM Lidl Receipt Downloader - Windows Run Script
REM Автоматично активира venv и стартира приложението

echo.
echo ============================================
echo   Lidl Receipt Downloader
echo ============================================
echo.

REM Проверка за venv
if exist "venv\Scripts\activate.bat" (
    echo Активиране на виртуална среда...
    call venv\Scripts\activate.bat
    echo.
) else (
    echo [!] Виртуална среда не е намерена!
    echo     Моля първо изпълнете setup.ps1
    echo.
    pause
    exit /b 1
)

REM Стартиране на приложението
echo Стартиране на приложението...
python lidl_scraper_gui.py

REM Деактивиране на venv
call venv\Scripts\deactivate.bat

pause
