# Lidl Receipt Downloader - Автоматичен старт
# Автоматично инсталира зависимости (ако трябва) и стартира приложението

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Lidl Receipt Downloader" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Проверка за Python
Write-Host "[√] Проверка за Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ Python намерен: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python не е намерен!" -ForegroundColor Red
    Write-Host "  Моля инсталирайте Python 3.8+ от https://www.python.org" -ForegroundColor Red
    Write-Host ""
    pause
    exit 1
}

# Проверка и създаване на виртуална среда
if (-Not (Test-Path "venv")) {
    Write-Host "`n[√] Създаване на виртуална среда..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Виртуална среда създадена" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Грешка при създаване на виртуална среда" -ForegroundColor Red
        pause
        exit 1
    }
}

# Активиране на виртуалната среда
Write-Host "`n[√] Активиране на виртуална среда..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Проверка дали зависимостите са инсталирани
$needsInstall = $false
$pipList = pip list 2>&1

if ($pipList -notmatch "playwright") {
    $needsInstall = $true
}

if ($needsInstall) {
    Write-Host "`n[√] Инсталиране на зависимости..." -ForegroundColor Yellow
    Write-Host "  Първо стартиране - това може да отнеме няколко минути..." -ForegroundColor Cyan
    
    # Upgrade pip
    python -m pip install --upgrade pip --quiet
    
    # Инсталация на зависимости
    pip install -r requirements.txt --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Зависимостите са инсталирани" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Грешка при инсталиране на зависимости" -ForegroundColor Red
        pause
        exit 1
    }
    
    # Инсталация на Playwright браузъри
    Write-Host "`n[√] Инсталиране на Playwright браузър..." -ForegroundColor Yellow
    playwright install chromium
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Chromium инсталиран" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Възможна грешка при инсталиране на Chromium" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ✓ Зависимостите са вече инсталирани" -ForegroundColor Green
}

# Стартиране на приложението
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Стартиране на приложението..." -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Cyan

python lidl_scraper_gui.py

# Деактивиране на venv
deactivate

Write-Host "`n"
