import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import RegisteredFolder
from ..schemas import FolderCreate, FolderRead


router = APIRouter(
    prefix="/api/folders",
    tags=["folders"],
)


def normalize_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def paths_overlap(first: Path, second: Path) -> bool:
    first_normalized = normalize_path(first)
    second_normalized = normalize_path(second)

    try:
        common = os.path.normcase(
            os.path.commonpath([first_normalized, second_normalized])
        )
    except ValueError:
        return False

    return common in {first_normalized, second_normalized}


@router.get("", response_model=list[FolderRead])
def list_folders(db: Session = Depends(get_db)):
    statement = select(RegisteredFolder).order_by(RegisteredFolder.name)
    return db.scalars(statement).all()


@router.post(
    "",
    response_model=FolderRead,
    status_code=status.HTTP_201_CREATED,
)
def register_folder(
    payload: FolderCreate,
    db: Session = Depends(get_db),
):
    folder = Path(payload.path).expanduser()

    if not folder.exists():
        raise HTTPException(
            status_code=400,
            detail="Folder does not exist.",
        )

    if not folder.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Path is not a folder.",
        )

    folder = folder.resolve()
    normalized = normalize_path(folder)

    existing_folders = db.scalars(select(RegisteredFolder)).all()

    for existing in existing_folders:
        existing_path = Path(existing.path)

        if normalize_path(existing_path) == normalized:
            raise HTTPException(
                status_code=409,
                detail="Folder is already registered.",
            )

        if paths_overlap(folder, existing_path):
            raise HTTPException(
                status_code=409,
                detail="Registered folders cannot overlap.",
            )

    registered = RegisteredFolder(
        name=folder.name or str(folder),
        path=str(folder),
    )

    db.add(registered)
    db.commit()
    db.refresh(registered)

    return registered