# 🌐 GitHub Pages – Бързо Ръководство

## ⚡ 3-Минутна Настройка

### Стъпка 1: Активирайте GitHub Pages
1. Отворете вашия GitHub репозиторий
2. Settings → Pages
3. Source: Branch `main`, Folder `/docs`
4. Save

✅ **GitHub Pages е активен!** Адресът е: `https://YOUR_USERNAME.github.io/lidl-receipt-downloader/`

---

## 📤 Как да Качам Отчетите?

### Вариант A: Ръчно (5 минути)

```bash
# 1. Генерирайте отчетите с приложението
# 2. Копирайте файловете
cp ~/Documents/lidl_receipts_*.html docs/reports/
cp ~/Documents/lidl_receipts_*.xlsx docs/reports/

# 3. Направете push
git add docs/reports/
git commit -m "Add new price analysis reports"
git push origin main
```

### Вариант B: Със Python Скрипт (Препоръчано)

```bash
# След генериране на отчетите, направете:
python publish_to_github_pages.py ~/Documents/

# Или за един файл:
python publish_to_github_pages.py ~/Documents/lidl_receipts_20250120_120000_price_analysis.xlsx
```

Скриптът ще:
- ✅ Копира файловете на правилното място
- ✅ Генерира метаданни
- ✅ Показва инструкции за git commit

---

## 🔗 Където Са Файловете?

| Параметър | Стойност |
|-----------|----------|
| **Главна страница** | `https://YOUR_USERNAME.github.io/lidl-receipt-downloader/` |
| **Отчетите** | `https://YOUR_USERNAME.github.io/lidl-receipt-downloader/reports/filename.html` |
| **Локално на компютъра** | `./docs/reports/` |
| **На GitHub** | `docs/reports/` папката в репозиторита |

---

## 📋 Структура на Папката

```
project/
├── docs/                          ← GitHub Pages root
│   ├── index.html                 ← Начална страница
│   ├── .nojekyll                  ← Jekyll отключване
│   ├── reports-metadata.json      ← Метаданни
│   └── reports/                   ← Вашите отчети
│       ├── lidl_..._price_analysis.xlsx
│       ├── lidl_..._interactive_chart.html
│       ├── lidl_..._seasonal_analysis.html
│       └── lidl_..._years_comparison.html
└── ...
```

---

## ⚠️ Възможни Проблеми

| Проблем | Решение |
|---------|---------|
| Страницата не се вижда | Проверете Settings → Pages |
| Файловете не се вижат | Чакайте 2 минути, изчистете cache |
| GitHub Pages URL е различен | Проверете дали репозиторита е публичен |

---

## 🎯 Полезни Команди

```bash
# Проверете статуса на git
git status

# Добавете файлове
git add docs/reports/

# Направете commit
git commit -m "Publish new analysis"

# Качете на GitHub
git push origin main

# Проверете дали GitHub Pages е включен
git branch -vv
```

---

## 📊 Примерен Workflow

```bash
# 1. Генерирайте отчетите
python lidl_scraper_gui.py  # Анализирайте касови бележки

# 2. Качете с Python скрипта
python publish_to_github_pages.py ~/Documents/

# 3. Направете commit
cd lidl-receipt-downloader
git add docs/reports/
git commit -m "New reports: 2025-01-20"
git push origin main

# 4. Отворете в браузър
# https://YOUR_USERNAME.github.io/lidl-receipt-downloader/
```

---

## 💡 Съвети

- 🔄 GitHub Pages се обновява за 1-2 минути след push
- 📁 Копирайте файловете в `docs/reports/`, никъде другаде
- 🔐 Файловете е публични, не качвайте чувствителни данни
- 📈 За бързина, качвайте само последните отчети
- 🧹 Изтривайте стари файлове за спестяване на място

---

## 🆘 Помощ

- Прочетете [GITHUB_PAGES.md](GITHUB_PAGES.md) за подробно ръководство
- Отворете issue с описание на проблема
- Проверете [GitHub Pages документация](https://docs.github.com/en/pages)

---

**Готов сте! 🎉 Отчетите ще бъдат налични на интернет!**
