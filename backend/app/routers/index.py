from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..chunking import get_semantic_chunker
from ..database import get_db
from ..extractors import extract_document
from ..models import Document, RegisteredFolder
from ..scanner import discover_files, sha256_file


router = APIRouter(
	prefix="/api/index",
	tags=["index"],
)


@router.post("/scan/{folder_id}")
def scan_folder(
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
			detail="Registered folder not found.",
		)

	root = Path(folder.path)

	if not root.exists() or not root.is_dir():
		return {
			"status": "unavailable",
			"folder_id": folder_id,
			"discovered": 0,
			"new": 0,
			"changed": 0,
			"unchanged": 0,
			"deleted": 0,
		}

	files = discover_files(root)

	existing_documents = db.scalars(
		select(Document).where(
			Document.folder_id == folder_id
		)
	).all()

	existing_by_path = {
		document.relative_path: document
		for document in existing_documents
	}

	seen_paths: set[str] = set()

	new_count = 0
	changed_count = 0
	unchanged_count = 0

	for path in files:
		relative_path = str(
			path.relative_to(root)
		)

		seen_paths.add(relative_path)

		stat = path.stat()

		existing = existing_by_path.get(
			relative_path
		)

		if (
			existing
			and existing.status != "deleted"
			and existing.size_bytes
			== stat.st_size
			and existing.modified_ns
			== stat.st_mtime_ns
		):
			unchanged_count += 1
			continue

		file_hash = sha256_file(path)

		if existing:
			if existing.sha256 == file_hash:
				existing.size_bytes = (
					stat.st_size
				)

				existing.modified_ns = (
					stat.st_mtime_ns
				)

				existing.absolute_path = str(
					path
				)

				existing.updated_at = (
					datetime.now(
						timezone.utc
					)
				)

				if existing.status == "deleted":
					existing.status = "pending"
					changed_count += 1
				else:
					unchanged_count += 1

				continue

			existing.size_bytes = stat.st_size
			existing.modified_ns = (
				stat.st_mtime_ns
			)

			existing.sha256 = file_hash
			existing.absolute_path = str(path)
			existing.extension = (
				path.suffix.lower()
			)

			existing.status = "pending"

			existing.updated_at = (
				datetime.now(
					timezone.utc
				)
			)

			changed_count += 1

		else:
			document = Document(
				folder_id=folder_id,
				relative_path=relative_path,
				absolute_path=str(path),
				extension=path.suffix.lower(),
				size_bytes=stat.st_size,
				modified_ns=stat.st_mtime_ns,
				sha256=file_hash,
				status="pending",
			)

			db.add(document)

			new_count += 1

	deleted_count = 0

	for document in existing_documents:
		if (
			document.relative_path
			not in seen_paths
		):
			if document.status != "deleted":
				document.status = "deleted"

				document.updated_at = (
					datetime.now(
						timezone.utc
					)
				)

				deleted_count += 1

	db.commit()

	return {
		"status": "complete",
		"folder_id": folder_id,
		"discovered": len(files),
		"new": new_count,
		"changed": changed_count,
		"unchanged": unchanged_count,
		"deleted": deleted_count,
	}


def get_available_document(
	document_id: int,
	db: Session,
) -> Document:
	document = db.get(
		Document,
		document_id,
	)

	if document is None:
		raise HTTPException(
			status_code=404,
			detail="Document not found.",
		)

	if document.status == "deleted":
		raise HTTPException(
			status_code=410,
			detail="Document has been deleted.",
		)

	path = Path(
		document.absolute_path
	)

	if not path.exists():
		raise HTTPException(
			status_code=404,
			detail=(
				"Document file is unavailable."
			),
		)

	return document


def extract_available_document(
	document: Document,
):
	path = Path(
		document.absolute_path
	)

	try:
		return extract_document(path)

	except ValueError as error:
		raise HTTPException(
			status_code=400,
			detail=str(error),
		) from error


@router.get("/extract/{document_id}")
def extract_indexed_document(
	document_id: int,
	db: Session = Depends(get_db),
):
	document = get_available_document(
		document_id,
		db,
	)

	extracted = extract_available_document(
		document
	)

	return {
		"document_id": document.id,
		"path": document.relative_path,
		"extension": extracted.extension,
		"sections": [
			{
				"text": section.text,
				"start_line": (
					section.start_line
				),
				"end_line": section.end_line,
				"start_page": (
					section.start_page
				),
				"end_page": section.end_page,
				"heading": section.heading,
				"symbol": section.symbol,
				"section_type": (
					section.section_type
				),
			}
			for section in extracted.sections
		],
	}


@router.get("/chunks/{document_id}")
def preview_document_chunks(
	document_id: int,
	db: Session = Depends(get_db),
):
	document = get_available_document(
		document_id,
		db,
	)

	extracted = extract_available_document(
		document
	)

	chunker = get_semantic_chunker()

	chunks = chunker.chunk_document(
		extracted
	)

	return {
		"document_id": document.id,
		"path": document.relative_path,
		"chunk_count": len(chunks),
		"chunker": {
			"strategy": "semantic",
			"boundary_model": (
				chunker.model_name
			),
			"device": chunker.device,
		},
		"chunks": [
			{
				"chunk_index": (
					chunk.chunk_index
				),
				"section_index": (
					chunk.section_index
				),
				"text": chunk.text,
				"token_count": (
					chunk.token_count
				),
				"strategy": chunk.strategy,
				"start_line": (
					chunk.start_line
				),
				"end_line": chunk.end_line,
				"start_page": (
					chunk.start_page
				),
				"end_page": chunk.end_page,
				"heading": chunk.heading,
				"symbol": chunk.symbol,
				"section_type": (
					chunk.section_type
				),
			}
			for chunk in chunks
		],
	}