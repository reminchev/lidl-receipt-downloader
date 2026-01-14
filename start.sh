#!/bin/bash
# Lidl Receipt Downloader - Автоматичен старт
# Автоматично инсталира зависимости (ако трябва) и стартира приложението

echo ""
echo "============================================"
echo "  Lidl Receipt Downloader"
echo "============================================"
echo ""

# Проверка за Python
echo "[√] Проверка за Python..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
    echo "  ✓ Python намерен: $(python3 --version)"
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
    echo "  ✓ Python намерен: $(python --version)"
else
    echo "  ✗ Python не е намерен!"
    echo "  Моля инсталирайте Python 3.8+ от https://www.python.org"
    echo ""
    read -p "Натиснете Enter за изход..."
    exit 1
fi

# Проверка и създаване на виртуална среда
if [ ! -d "venv" ]; then
    echo ""
    echo "[√] Създаване на виртуална среда..."
    $PYTHON_CMD -m venv venv
    if [ $? -eq 0 ]; then
        echo "  ✓ Виртуална среда създадена"
    else
        echo "  ✗ Грешка при създаване на виртуална среда"
        read -p "Натиснете Enter за изход..."
        exit 1
    fi
fi

# Активиране на виртуалната среда
echo ""
echo "[√] Активиране на виртуална среда..."
source venv/bin/activate

# Проверка дали зависимостите са инсталирани
NEEDS_INSTALL=false
if ! pip show playwright &> /dev/null; then
    NEEDS_INSTALL=true
fi

if [ "$NEEDS_INSTALL" = true ]; then
    echo ""
    echo "[√] Инсталиране на зависимости..."
    echo "  Първо стартиране - това може да отнеме няколко минути..."
    
    # Upgrade pip
    $PYTHON_CMD -m pip install --upgrade pip --quiet
    
    # Инсталация на зависимости
    pip install -r requirements.txt --quiet
    if [ $? -eq 0 ]; then
        echo "  ✓ Зависимостите са инсталирани"
    else
        echo "  ✗ Грешка при инсталиране на зависимости"
        read -p "Натиснете Enter за изход..."
        exit 1
    fi
    
    # Инсталация на Playwright браузъри
    echo ""
    echo "[√] Инсталиране на Playwright браузър..."
    playwright install chromium
    if [ $? -eq 0 ]; then
        echo "  ✓ Chromium инсталиран"
    else
        echo "  ⚠ Възможна грешка при инсталиране на Chromium"
    fi
else
    echo "  ✓ Зависимостите са вече инсталирани"
fi

# Стартиране на приложението
echo ""
echo "============================================"
echo "  Стартиране на приложението..."
echo "============================================"
echo ""

$PYTHON_CMD lidl_scraper_gui.py

# Деактивиране на venv
deactivate

echo ""
