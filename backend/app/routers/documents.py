from pathlib import Path

from fastapi import (
	APIRouter,
	Depends,
	HTTPException,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
	Document,
	RegisteredFolder,
)


router = APIRouter(
	prefix="/api/documents",
	tags=["documents"],
)


@router.get("/folder/{folder_id}")
def list_folder_documents(
	folder_id: int,
	db: Session = Depends(get_db),
):
	folder = db.get(
		RegisteredFolder,
		folder_id,
	)

	if folder is None:
		raise HTTPException(
			status_code=404,
			detail=(
				"Registered folder "
				"not found."
			),
		)

	documents = db.scalars(
		select(Document)
		.where(
			Document.folder_id
			== folder_id
		)
		.order_by(
			Document.relative_path
		)
	).all()

	return {
		"folder_id": folder.id,
		"folder_name": folder.name,
		"folder_path": folder.path,
		"documents": [
			{
				"id": document.id,
				"relative_path": (
					document.relative_path
				),
				"extension": (
					document.extension
				),
				"size_bytes": (
					document.size_bytes
				),
				"sha256": (
					document.sha256
				),
				"status": (
					document.status
				),
				"updated_at": (
					document.updated_at
				),
				"available": (
					document.status
					!= "deleted"
					and Path(
						document.absolute_path
					).exists()
				),
			}
			for document
			in documents
		],
	}