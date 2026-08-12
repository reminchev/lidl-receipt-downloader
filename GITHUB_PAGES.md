# GitHub Pages - Настройка за Автоматично Качване на Отчетите

## 🚀 Как да настроим GitHub Pages?

Това ръководство показва как да подготвите вашето приложение да качва автоматично генерираните отчети на GitHub Pages.

---

## 📋 Предварителни Условия

- ✅ GitHub репозиторий (публичен или приватен)
- ✅ Администраторски достъп до репозиторита
- ✅ Приложението генерира HTML и XLSX файлове

---

## ⚙️ Стъпки за Настройка

### 1. Активирайте GitHub Pages

1. Отворете вашия репозиторий на GitHub
2. Отидете на **Settings** → **Pages**
3. Под **Build and deployment**, изберете:
   - **Source**: `Deploy from a branch`
   - **Branch**: `main`
   - **Folder**: `/ (root)` или `/docs`

4. Натиснете **Save**

> ✨ GitHub Pages е активиран! Страницата ще е налична на:
> `https://YOUR_USERNAME.github.io/lidl-receipt-downloader/`

---

## 📂 Структура на Директориите

Генерираните файлове се организират по следния начин:

```
docs/
├── index.html                          # Главна страница (лендинг)
├── .nojekyll                           # Инструкция да се пропуска Jekyll обработката
├── reports/                            # Папка с генерирани отчети
│   ├── demo_2025-01-20_interactive_chart.html
│   ├── demo_2025-01-20_price_analysis.xlsx
│   ├── demo_2025-01-20_seasonal_analysis.html
│   ├── demo_2025-01-20_years_comparison.html
│   └── demo_2025-01-20_index.html
└── css/ (опционално)
    └── styles.css                      # Преизползвани стилове
```

---

## 🔄 Автоматично Качване (GitHub Actions)

### Как Работи?

GitHub Actions автоматично качва файловете на GitHub Pages, когато:

1. ✅ Се направи `push` към `main` браншa
2. ✅ Има нови файлове в папката `reports/`
3. ✅ Се модифицира файла `.github/workflows/deploy-reports.yml`

### Проверете Статуса

1. Отворете репозиторита
2. Отидете на **Actions** таб
3. Вижте работата на **Deploy Reports to GitHub Pages**

---

## 🎯 Как да Генерирате и Качите Отчетите?

### Вариант 1: Ръчно Качване (Manual Upload)

1. Генерирайте отчетите с приложението
2. Копирайте генерираните файлове в папката `docs/reports/`
3. Направете `git add`, `git commit` и `git push`
4. GitHub Actions автоматично ще ги качи на GitHub Pages

```bash
# Копирайте отчетите
cp ~/Documents/lidl_receipts_*.html docs/reports/
cp ~/Documents/lidl_receipts_*.xlsx docs/reports/

# Направете commit и push
git add docs/reports/
git commit -m "Add new analysis reports"
git push origin main
```

### Вариант 2: Автоматично Качване (Script)

Създайте скрипт, който автоматично:
1. Генерира отчетите
2. Копира их в `docs/reports/`
3. Направи commit и push

```powershell
# PowerShell скрипт: auto-publish.ps1
python lidl_scraper_gui.py

$outputDir = "$env:USERPROFILE\Documents"
$docsDir = "docs/reports"

Copy-Item "$outputDir\lidl_receipts_*.html" -Destination $docsDir
Copy-Item "$outputDir\lidl_receipts_*.xlsx" -Destination $docsDir

git add $docsDir
git commit -m "Auto-publish reports: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git push origin main
```

---

## 🔒 Сигурност

- ✅ Папката `docs/reports/` съдържа **только** публични анализни файлове
- ✅ **Не** съдържа пароли или лични данни
- ✅ Файловете са статични HTML и XLSX
- ✅ Без сървърна логика или бази данни

---

## 🐛 Възможни Проблеми

### GitHub Pages не се обновява

**Решение:**
- Проверете дали файловете са в правилната папка (`docs/`)
- Проверете GitHub Actions работата под **Actions** таб
- Изчистете браузърния cache (Ctrl+Shift+Delete)
- Чакайте 1-2 минути за обновяване

### Файловете не се вижат на GitHub Pages

**Решение:**
- Проверете дали репозиторито е публичен
- Проверете дали GitHub Pages е активиран в Settings
- Проверете дали `.nojekyll` файлът е в папката `docs/`

### Линкове не работят правилно

**Решение:**
- Използвайте относителни пътища вместо абсолютни
- Проверете дали имената на файловете съответстват на линковете

---

## 📊 Примери

### Основна Структура на Reports

Когато генерирате отчети, те получават следното име:

```
lidl_receipts_ГГГГММДД_ЧЧММСС_price_analysis.xlsx
lidl_receipts_ГГГГММДД_ЧЧММСС_interactive_chart.html
lidl_receipts_ГГГГММДД_ЧЧММСС_seasonal_analysis.html
lidl_receipts_ГГГГММДД_ЧЧММСС_years_comparison.html
```

Копирайте тези файлове в `docs/reports/` и те ще бъдат налични на:
- `https://YOUR_USERNAME.github.io/lidl-receipt-downloader/reports/lidl_receipts_*.html`

---

## 🎨 Персонализиране на GitHub Pages

Можете да персонализирате главната страница, като редактирате `docs/index.html`:

1. Отворете `docs/index.html` в текстов редактор
2. Модифицирайте HTML содържанието
3. Направете commit и push
4. Изменията ще бъдат видими след 1-2 минути

---

## 📞 Поддръжка

Ако имате проблеми:

1. Проверете [GitHub Pages документацията](https://docs.github.com/en/pages)
2. Отворете Issue в репозиторита с описание на проблема
3. Проверете GitHub Actions логовете за грешки

---

## ✨ Полезни Команди

```bash
# Проверете статуса на Git
git status

# Добавете нови файлове
git add docs/reports/*

# Направете commit със съобщение
git commit -m "Publish new price analysis reports"

# Качете на GitHub
git push origin main

# Проверете дали GitHub Pages е активиран
git config --get pages.build.deploy
```

---

**Готов сте! 🎉 Отчетите сега ще бъдат автоматично качени на GitHub Pages при всеки push към main.**
