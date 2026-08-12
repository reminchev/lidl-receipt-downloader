"""Управление на конфигурацията на приложението.

Конфигурацията се съхранява извън репозиторито (~/.lidl-receipts), за да
не се попадат потребителски данни в git историята. Никакви пароли не се записват.
"""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".lidl-receipts"
CONFIG_PATH = CONFIG_DIR / "config.json"

PROJECT_ROOT = Path(__file__).resolve().parent

DEFAULTS = {
    "output_dir": str(Path.home() / "Documents"),
    "analysis_files": [],
    "db_path": str(PROJECT_ROOT / "lidl_local_prices.db"),
    "github_pages_enabled": False,
    "github_pages_dir": str(PROJECT_ROOT / "docs"),
    "auto_publish_reports": False,
}


def load_config() -> dict:
    """Зарежда конфигурацията; връща defaults при липсващ/повреден файл."""
    config = dict(DEFAULTS)
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        for key in DEFAULTS:
            if key in data:
                config[key] = data[key]
    except (OSError, json.JSONDecodeError):
        pass
    return config


def save_config(config: dict) -> None:
    """Запазва конфигурацията в потребителската директория."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass