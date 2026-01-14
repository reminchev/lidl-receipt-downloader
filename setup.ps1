# Lidl Receipt Downloader - Windows Setup Script
# Автоматична инсталация с виртуална среда (venv)

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Lidl Receipt Downloader - Setup" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Проверка за Python
Write-Host "[1/5] Проверка за Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ Python намерен: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python не е намерен!" -ForegroundColor Red
    Write-Host "  Моля инсталирайте Python 3.8+ от https://www.python.org" -ForegroundColor Red
    exit 1
}

# Създаване на виртуална среда
Write-Host "`n[2/5] Създаване на виртуална среда (venv)..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "  ⚠ venv вече съществува, пропускане..." -ForegroundColor Yellow
} else {
    python -m venv venv
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Виртуална среда създадена успешно" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Грешка при създаване на виртуална среда" -ForegroundColor Red
        exit 1
    }
}

# Активиране на виртуалната среда
Write-Host "`n[3/5] Активиране на виртуална среда..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Инсталация на зависимости
Write-Host "`n[4/5] Инсталиране на зависимости..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Зависимостите са инсталирани успешно" -ForegroundColor Green
} else {
    Write-Host "  ✗ Грешка при инсталиране на зависимости" -ForegroundColor Red
    exit 1
}

# Инсталация на Playwright браузъри
Write-Host "`n[5/5] Инсталиране на Playwright браузъри..." -ForegroundColor Yellow
playwright install chromium
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Chromium инсталиран успешно" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Възможна грешка при инсталиране на Chromium" -ForegroundColor Yellow
}

# Завършване
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  ✓ Инсталацията завърши успешно!" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "Следващи стъпки:" -ForegroundColor Yellow
Write-Host "  1. Активирайте виртуалната среда:" -ForegroundColor White
Write-Host "     .\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "`n  2. Стартирайте приложението:" -ForegroundColor White
Write-Host "     python lidl_scraper_gui.py" -ForegroundColor Cyan
Write-Host ""
