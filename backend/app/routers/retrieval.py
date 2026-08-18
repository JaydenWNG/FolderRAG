from fastapi import (
	APIRouter,
	Depends,
	HTTPException,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..evidence import evaluate_evidence
from ..models import RegisteredFolder
from ..vectorstore import (
	COLLECTION_NAME,
	MODEL_NAME,
	VECTOR_SIZE,
	count_folder_points,
)
from ..vectorstore.retrieval import (
	MAX_RESULTS,
	MMR_DIVERSITY,
	TOP_CANDIDATES,
	retrieve_chunks,
)


router = APIRouter(
	prefix="/api/retrieve",
	tags=["retrieval"],
)


class RetrievalRequest(BaseModel):
	query: str = Field(
		min_length=1,
		max_length=4000,
	)

	limit: int = Field(
		default=MAX_RESULTS,
		ge=1,
		le=MAX_RESULTS,
	)


@router.post("/{folder_id}")
def retrieve(
	folder_id: int,
	request: RetrievalRequest,
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

	query = request.query.strip()

	if not query:
		raise HTTPException(
			status_code=400,
			detail=(
				"Retrieval query "
				"cannot be empty."
			),
		)

	point_count = (
		count_folder_points(
			folder_id
		)
	)

	if point_count == 0:
		return {
			"folder_id": folder_id,
			"query": query,
			"retrieved_count": 0,
			"results": [],
			"retrieval": {
				"embedding_model": (
					MODEL_NAME
				),
				"dimensions": (
					VECTOR_SIZE
				),
				"distance": "cosine",
				"candidate_limit": (
					TOP_CANDIDATES
				),
				"result_limit": (
					request.limit
				),
				"mmr_diversity": (
					MMR_DIVERSITY
				),
				"collection": (
					COLLECTION_NAME
				),
			},
		}

	try:
		results = retrieve_chunks(
			folder_id=folder_id,
			query=query,
			limit=request.limit,
		)

	except ValueError as error:
		raise HTTPException(
			status_code=400,
			detail=str(error),
		) from error

	return {
		"folder_id": folder_id,
		"query": query,
		"retrieved_count": len(
			results
		),
		"results": results,
		"retrieval": {
			"embedding_model": (
				MODEL_NAME
			),
			"dimensions": VECTOR_SIZE,
			"distance": "cosine",
			"candidate_limit": (
				TOP_CANDIDATES
			),
			"result_limit": (
				request.limit
			),
			"mmr_diversity": (
				MMR_DIVERSITY
			),
			"collection": (
				COLLECTION_NAME
			),
		},
	}

@router.post(
    "/{folder_id}/evidence"
)
def retrieve_with_evidence(
    folder_id: int,
    request: RetrievalRequest,
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

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail=(
                "Retrieval query "
                "cannot be empty."
            ),
        )

    results = retrieve_chunks(
        folder_id=folder_id,
        query=query,
        limit=request.limit,
    )

    decision = evaluate_evidence(
        results
    )

    return {
        "folder_id": folder_id,
        "query": query,
        "retrieved_count": len(
            results
        ),
        "evidence": {
            "sufficient": (
                decision.sufficient
            ),
            "strongest_score": (
                decision.strongest_score
            ),
            "threshold": (
                decision.threshold
            ),
            "reason": (
                decision.reason
            ),
        },
        "results": results,
    }