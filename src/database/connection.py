from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Укажи правильный путь к базе данных
DATABASE_URL = "sqlite:///data/cs2_performance_lab.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Инициализирует таблицы в базе данных."""
    from src.domain.models import Base
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """Контекстный менеджер для безопасного управления сессией SQLAlchemy."""
    session: Session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()