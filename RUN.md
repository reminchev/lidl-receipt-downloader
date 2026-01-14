# 🚀 Стартиране на приложението

Бързи скриптове за стартиране на Lidl Receipt Downloader

## Windows

### С venv (препоръчително)

Двоен клик на `run.bat` или в PowerShell:
```powershell
.\run.bat
```

### Директно (без venv)
```powershell
python lidl_scraper_gui.py
```

## Linux/macOS

### С venv (препоръчително)

```bash
chmod +x run.sh
./run.sh
```

### Директно (без venv)
```bash
python3 lidl_scraper_gui.py
```

## Conda

```bash
conda activate lidl-downloader
python lidl_scraper_gui.py
```

---

## Първо стартиране?

Ако все още не сте инсталирали приложението, изпълнете setup скрипта:

**Windows:** `.\setup.ps1`  
**Linux/macOS:** `./setup.sh`  
**Conda:** `conda env create -f environment.yml`
