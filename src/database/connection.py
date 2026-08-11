import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = os.path.join("data", "cs2_performance_lab.db")
os.makedirs("data", exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: expire_on_commit=False предотвращает ошибку DetachedInstanceError
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    expire_on_commit=False
)

Base = declarative_base()

def init_db():
    from src.domain.models import Base as ModelsBase
    ModelsBase.metadata.create_all(bind=engine)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()