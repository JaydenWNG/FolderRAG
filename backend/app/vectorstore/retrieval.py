from qdrant_client import models

from .embeddings import get_embedding_model
from .qdrant_store import (
	COLLECTION_NAME,
	ensure_collection,
	folder_filter,
)


TOP_CANDIDATES = 20
MAX_RESULTS = 8
MMR_DIVERSITY = 0.30


def retrieve_chunks(
	folder_id: int,
	query: str,
	limit: int = MAX_RESULTS,
) -> list[dict]:
	clean_query = query.strip()

	if not clean_query:
		raise ValueError(
			"Retrieval query cannot be empty."
		)

	result_limit = min(
		max(limit, 1),
		MAX_RESULTS,
	)

	embedder = get_embedding_model()

	query_vector = (
		embedder
		.encode([clean_query])[0]
		.tolist()
	)

	client = ensure_collection()

	response = client.query_points(
		collection_name=COLLECTION_NAME,
		query=models.NearestQuery(
			nearest=query_vector,
			mmr=models.Mmr(
				diversity=MMR_DIVERSITY,
				candidates_limit=max(
					TOP_CANDIDATES,
					result_limit,
				),
			),
		),
		query_filter=folder_filter(
			folder_id
		),
		limit=result_limit,
		with_payload=True,
		with_vectors=False,
	)

	results: list[dict] = []

	for rank, point in enumerate(
		response.points,
		start=1,
	):
		payload = point.payload or {}

		results.append(
			{
				"rank": rank,
				"point_id": str(
					point.id
				),
				"score": float(
					point.score
				),
				"document_id": (
					payload.get(
						"document_id"
					)
				),
				"folder_id": (
					payload.get(
						"folder_id"
					)
				),
				"relative_path": (
					payload.get(
						"relative_path"
					)
				),
				"chunk_index": (
					payload.get(
						"chunk_index"
					)
				),
				"section_index": (
					payload.get(
						"section_index"
					)
				),
				"text": payload.get(
					"text"
				),
				"token_count": (
					payload.get(
						"token_count"
					)
				),
				"start_line": (
					payload.get(
						"start_line"
					)
				),
				"end_line": (
					payload.get(
						"end_line"
					)
				),
				"start_page": (
					payload.get(
						"start_page"
					)
				),
				"end_page": (
					payload.get(
						"end_page"
					)
				),
				"heading": payload.get(
					"heading"
				),
				"symbol": payload.get(
					"symbol"
				),
				"section_type": (
					payload.get(
						"section_type"
					)
				),
			}
		)

	return results
