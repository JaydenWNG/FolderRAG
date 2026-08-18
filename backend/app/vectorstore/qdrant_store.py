from functools import lru_cache
from uuid import NAMESPACE_URL, uuid5

import numpy as np
from qdrant_client import QdrantClient, models

from ..chunking.models import Chunk
from ..database import DATA_DIR
from ..models import Document
from .embeddings import MODEL_NAME, VECTOR_SIZE


COLLECTION_NAME = "folderrag_chunks_v1"

QDRANT_PATH = (
	DATA_DIR
	/ "qdrant"
)

POINT_NAMESPACE = uuid5(
	NAMESPACE_URL,
	"folderrag/chunks",
)


@lru_cache(maxsize=1)
def get_qdrant_client(
) -> QdrantClient:
	QDRANT_PATH.mkdir(
		parents=True,
		exist_ok=True,
	)

	return QdrantClient(
		path=str(QDRANT_PATH)
	)


def ensure_collection(
) -> QdrantClient:
	client = get_qdrant_client()

	if not client.collection_exists(
		COLLECTION_NAME
	):
		client.create_collection(
			collection_name=(
				COLLECTION_NAME
			),
			vectors_config=(
				models.VectorParams(
					size=VECTOR_SIZE,
					distance=(
						models.Distance.COSINE
					),
				)
			),
		)

	return client


def document_filter(
	document_id: int,
) -> models.Filter:
	return models.Filter(
		must=[
			models.FieldCondition(
				key="document_id",
				match=models.MatchValue(
					value=document_id
				),
			)
		]
	)


def folder_filter(
	folder_id: int,
) -> models.Filter:
	return models.Filter(
		must=[
			models.FieldCondition(
				key="folder_id",
				match=models.MatchValue(
					value=folder_id
				),
			)
		]
	)


def delete_document_points(
	document_id: int,
) -> None:
	client = ensure_collection()

	client.delete(
		collection_name=(
			COLLECTION_NAME
		),
		points_selector=(
			models.FilterSelector(
				filter=document_filter(
					document_id
				)
			)
		),
		wait=True,
	)


def make_point_id(
	document_id: int,
	chunk_index: int,
) -> str:
	return str(
		uuid5(
			POINT_NAMESPACE,
			(
				f"{document_id}:"
				f"{chunk_index}"
			),
		)
	)


def chunk_payload(
	document: Document,
	chunk: Chunk,
) -> dict:
	return {
		"document_id": document.id,
		"folder_id": document.folder_id,
		"relative_path": (
			document.relative_path
		),
		"sha256": document.sha256,
		"embedding_model": MODEL_NAME,
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


def upsert_document_chunks(
	document: Document,
	chunks: list[Chunk],
	vectors: np.ndarray,
) -> int:
	if len(chunks) != len(vectors):
		raise ValueError(
			"Chunk/vector count mismatch: "
			f"{len(chunks)} chunks and "
			f"{len(vectors)} vectors."
		)

	if not chunks:
		return 0

	client = ensure_collection()

	points: list[
		models.PointStruct
	] = []

	for chunk, vector in zip(
		chunks,
		vectors,
	):
		points.append(
			models.PointStruct(
				id=make_point_id(
					document_id=(
						document.id
					),
					chunk_index=(
						chunk.chunk_index
					),
				),
				vector=(
					vector.astype(
						np.float32,
						copy=False,
					).tolist()
				),
				payload=chunk_payload(
					document=document,
					chunk=chunk,
				),
			)
		)

	client.upsert(
		collection_name=(
			COLLECTION_NAME
		),
		points=points,
		wait=True,
	)

	return len(points)


def count_document_points(
	document_id: int,
) -> int:
	client = ensure_collection()

	result = client.count(
		collection_name=(
			COLLECTION_NAME
		),
		count_filter=(
			document_filter(
				document_id
			)
		),
		exact=True,
	)

	return result.count


def count_folder_points(
	folder_id: int,
) -> int:
	client = ensure_collection()

	result = client.count(
		collection_name=(
			COLLECTION_NAME
		),
		count_filter=folder_filter(
			folder_id
		),
		exact=True,
	)

	return result.count