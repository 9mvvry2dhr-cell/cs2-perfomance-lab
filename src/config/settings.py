from pathlib import Path

# Корень проекта (поднимаемся на 2 уровня от src/config/settings.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Пути к основным директориям
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
STYLES_DIR = ASSETS_DIR / "styles"

# Пути к конкретным файлам
MAIN_CSS_PATH = STYLES_DIR / "main.css"
DATABASE_PATH = DATA_DIR / "cs2_performance_lab.db"

# Настройки приложения
APP_TITLE = "CS2 Performance Lab"
APP_ICON = "🎯"