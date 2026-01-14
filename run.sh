#!/bin/bash
# Lidl Receipt Downloader - Linux/macOS Run Script
# Автоматично активира venv и стартира приложението

echo ""
echo "============================================"
echo "  Lidl Receipt Downloader"
echo "============================================"
echo ""

# Проверка за venv
if [ -f "venv/bin/activate" ]; then
    echo "Активиране на виртуална среда..."
    source venv/bin/activate
    echo ""
else
    echo "[!] Виртуална среда не е намерена!"
    echo "    Моля първо изпълнете ./setup.sh"
    echo ""
    exit 1
fi

# Стартиране на приложението
echo "Стартиране на приложението..."
python lidl_scraper_gui.py

# Деактивиране на venv
deactivate

echo ""
echo "Приложението е затворено."
echo ""
