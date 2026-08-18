from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..chunking import get_semantic_chunker
from ..database import get_db
from ..extractors import extract_document
from ..models import Document, RegisteredFolder
from ..vectorstore import (
	COLLECTION_NAME,
	MODEL_NAME,
	VECTOR_SIZE,
	count_folder_points,
	delete_document_points,
	ensure_collection,
	get_embedding_model,
	upsert_document_chunks,
)


router = APIRouter(
	prefix="/api/index/vectors",
	tags=["vectors"],
)


def get_folder(
	folder_id: int,
	db: Session,
) -> RegisteredFolder:
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

	return folder


@router.post("/{folder_id}")
def index_folder_vectors(
	folder_id: int,
	db: Session = Depends(get_db),
):
	get_folder(
		folder_id,
		db,
	)

	ensure_collection()

	documents = db.scalars(
		select(Document)
		.where(
			Document.folder_id
			== folder_id
		)
		.order_by(Document.id)
	).all()

	pending_documents = [
		document
		for document in documents
		if document.status
		== "pending"
	]

	deleted_documents = [
		document
		for document in documents
		if document.status
		== "deleted"
	]

	deleted_cleaned = 0

	failures: list[dict] = []

	for document in deleted_documents:
		try:
			delete_document_points(
				document.id
			)

			deleted_cleaned += 1

		except Exception as error:
			failures.append(
				{
					"document_id": (
						document.id
					),
					"path": (
						document.relative_path
					),
					"stage": (
						"delete"
					),
					"error": str(error),
				}
			)

	if not pending_documents:
		return {
			"status": (
				"complete"
				if not failures
				else "partial"
			),
			"folder_id": folder_id,
			"pending_documents": 0,
			"indexed_documents": 0,
			"indexed_chunks": 0,
			"deleted_documents_cleaned": (
				deleted_cleaned
			),
			"failed_documents": (
				failures
			),
			"collection": (
				COLLECTION_NAME
			),
			"collection_points": (
				count_folder_points(
					folder_id
				)
			),
			"embedding": {
				"model": MODEL_NAME,
				"dimensions": (
					VECTOR_SIZE
				),
				"distance": "cosine",
			},
		}

	chunker = (
		get_semantic_chunker()
	)

	embedder = (
		get_embedding_model()
	)

	indexed_documents = 0
	indexed_chunks = 0

	for document in pending_documents:
		document_id = document.id

		relative_path = (
			document.relative_path
		)

		path = Path(
			document.absolute_path
		)

		try:
			if not path.exists():
				delete_document_points(
					document_id
				)

				document.status = (
					"deleted"
				)

				document.updated_at = (
					datetime.now(
						timezone.utc
					)
				)

				db.commit()

				deleted_cleaned += 1

				continue

			extracted = (
				extract_document(
					path
				)
			)

			chunks = (
				chunker.chunk_document(
					extracted
				)
			)

			texts = [
				chunk.text
				for chunk in chunks
			]

			vectors = (
				embedder.encode(
					texts
				)
			)

			# Replace all previous vectors
			# belonging to this document.
			delete_document_points(
				document_id
			)

			stored_count = (
				upsert_document_chunks(
					document=document,
					chunks=chunks,
					vectors=vectors,
				)
			)

			document.status = (
				"indexed"
			)

			document.updated_at = (
				datetime.now(
					timezone.utc
				)
			)

			db.commit()

			indexed_documents += 1

			indexed_chunks += (
				stored_count
			)

		except Exception as error:
			db.rollback()

			failures.append(
				{
					"document_id": (
						document_id
					),
					"path": relative_path,
					"stage": "index",
					"error": str(error),
				}
			)

	return {
		"status": (
			"complete"
			if not failures
			else "partial"
		),
		"folder_id": folder_id,
		"pending_documents": (
			len(pending_documents)
		),
		"indexed_documents": (
			indexed_documents
		),
		"indexed_chunks": (
			indexed_chunks
		),
		"deleted_documents_cleaned": (
			deleted_cleaned
		),
		"failed_documents": failures,
		"collection": (
			COLLECTION_NAME
		),
		"collection_points": (
			count_folder_points(
				folder_id
			)
		),
		"embedding": {
			"model": MODEL_NAME,
			"dimensions": VECTOR_SIZE,
			"distance": "cosine",
			"device": embedder.device,
		},
	}


@router.get("/{folder_id}")
def vector_index_status(
	folder_id: int,
	db: Session = Depends(get_db),
):
	get_folder(
		folder_id,
		db,
	)

	documents = db.scalars(
		select(Document)
		.where(
			Document.folder_id
			== folder_id
		)
		.order_by(Document.id)
	).all()

	statuses: dict[str, int] = {}

	for document in documents:
		statuses[
			document.status
		] = (
			statuses.get(
				document.status,
				0,
			)
			+ 1
		)

	return {
		"folder_id": folder_id,
		"documents": len(
			documents
		),
		"document_statuses": (
			statuses
		),
		"collection": (
			COLLECTION_NAME
		),
		"collection_points": (
			count_folder_points(
				folder_id
			)
		),
		"embedding": {
			"model": MODEL_NAME,
			"dimensions": VECTOR_SIZE,
			"distance": "cosine",
		},
	}