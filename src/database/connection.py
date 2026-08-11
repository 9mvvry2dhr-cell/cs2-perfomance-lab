from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cs2_analytics.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db():
    """Создает таблицы в базе данных, если они еще не существуют."""
    Base.metadata.create_all(bind=engine)