import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def get_data_dir() -> Path:
    custom_dir = os.getenv("FOLDERRAG_DATA_DIR")

    if custom_dir:
        data_dir = Path(custom_dir)
    else:
        local_app_data = os.getenv("LOCALAPPDATA")

        if local_app_data:
            data_dir = Path(local_app_data) / "FolderRAG"
        else:
            data_dir = Path.home() / ".folderrag"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


DATA_DIR = get_data_dir()
DATABASE_PATH = DATA_DIR / "folderrag.db"

engine = create_engine(
    f"sqlite:///{DATABASE_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()