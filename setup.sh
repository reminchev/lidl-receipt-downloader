#!/bin/bash
# Lidl Receipt Downloader - Linux/macOS Setup Script
# Автоматична инсталация с виртуална среда (venv)

echo ""
echo "============================================"
echo "  Lidl Receipt Downloader - Setup"
echo "============================================"
echo ""

# Проверка за Python
echo "[1/5] Проверка за Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "  ✓ Python намерен: $PYTHON_VERSION"
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version)
    echo "  ✓ Python намерен: $PYTHON_VERSION"
    PYTHON_CMD="python"
else
    echo "  ✗ Python не е намерен!"
    echo "  Моля инсталирайте Python 3.8+ от https://www.python.org"
    exit 1
fi

# Създаване на виртуална среда
echo ""
echo "[2/5] Създаване на виртуална среда (venv)..."
if [ -d "venv" ]; then
    echo "  ⚠ venv вече съществува, пропускане..."
else
    $PYTHON_CMD -m venv venv
    if [ $? -eq 0 ]; then
        echo "  ✓ Виртуална среда създадена успешно"
    else
        echo "  ✗ Грешка при създаване на виртуална среда"
        exit 1
    fi
fi

# Активиране на виртуалната среда
echo ""
echo "[3/5] Активиране на виртуална среда..."
source venv/bin/activate

# Инсталация на зависимости
echo ""
echo "[4/5] Инсталиране на зависимости..."
pip install --upgrade pip
pip install -r requirements.txt
if [ $? -eq 0 ]; then
    echo "  ✓ Зависимостите са инсталирани успешно"
else
    echo "  ✗ Грешка при инсталиране на зависимости"
    exit 1
fi

# Инсталация на Playwright браузъри
echo ""
echo "[5/5] Инсталиране на Playwright браузъри..."
playwright install chromium
if [ $? -eq 0 ]; then
    echo "  ✓ Chromium инсталиран успешно"
else
    echo "  ⚠ Възможна грешка при инсталиране на Chromium"
fi

# Завършване
echo ""
echo "============================================"
echo "  ✓ Инсталацията завърши успешно!"
echo "============================================"
echo ""

echo "Следващи стъпки:"
echo "  1. Активирайте виртуалната среда:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Стартирайте приложението:"
echo "     python lidl_scraper_gui.py"
echo ""
