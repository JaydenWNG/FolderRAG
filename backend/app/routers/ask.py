from fastapi import (
	APIRouter,
	Depends,
	HTTPException,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..evidence import (
	evaluate_evidence,
	get_context_threshold,
)
from ..generation import (
	generate_grounded_answer,
)
from ..models import RegisteredFolder
from ..vectorstore.retrieval import (
	MAX_RESULTS,
	retrieve_chunks,
)


router = APIRouter(
	prefix="/api/ask",
	tags=["answering"],
)


class AskRequest(BaseModel):
	question: str = Field(
		min_length=1,
		max_length=4000,
	)

	limit: int = Field(
		default=MAX_RESULTS,
		ge=1,
		le=MAX_RESULTS,
	)


def build_source_label(
	result: dict,
) -> str:
	parts = [
		result.get(
			"relative_path"
		)
		or "unknown"
	]

	start_page = result.get(
		"start_page"
	)

	end_page = result.get(
		"end_page"
	)

	start_line = result.get(
		"start_line"
	)

	end_line = result.get(
		"end_line"
	)

	if start_page is not None:
		if (
			end_page is not None
			and end_page != start_page
		):
			parts.append(
				f"pages {start_page}-{end_page}"
			)
		else:
			parts.append(
				f"page {start_page}"
			)

	elif start_line is not None:
		if (
			end_line is not None
			and end_line != start_line
		):
			parts.append(
				f"lines {start_line}-{end_line}"
			)
		else:
			parts.append(
				f"line {start_line}"
			)

	return ", ".join(parts)


def build_grounded_context(
	results: list[dict],
	context_threshold: float,
) -> tuple[str, list[dict]]:
	evidence_results = [
		result
		for result in results
		if (
			result.get("score")
			is not None
			and float(
				result["score"]
			) >= context_threshold
		)
	]

	context_parts: list[str] = []
	sources: list[dict] = []

	for source_number, result in enumerate(
		evidence_results,
		start=1,
	):
		source_id = (
			f"S{source_number}"
		)

		label = build_source_label(
			result
		)

		context_parts.append(
			(
				f"[{source_id}] "
				f"{label}\n"
				f"{result['text']}"
			)
		)

		sources.append(
			{
				"source_id": (
					source_id
				),
				"document_id": (
					result.get(
						"document_id"
					)
				),
				"relative_path": (
					result.get(
						"relative_path"
					)
				),
				"chunk_index": (
					result.get(
						"chunk_index"
					)
				),
				"score": float(
					result["score"]
				),
				"start_page": (
					result.get(
						"start_page"
					)
				),
				"end_page": (
					result.get(
						"end_page"
					)
				),
				"start_line": (
					result.get(
						"start_line"
					)
				),
				"end_line": (
					result.get(
						"end_line"
					)
				),
				"heading": (
					result.get(
						"heading"
					)
				),
				"symbol": (
					result.get(
						"symbol"
					)
				),
			}
		)

	return (
		"\n\n".join(
			context_parts
		),
		sources,
	)


@router.post("/{folder_id}")
def ask_folder(
	folder_id: int,
	request: AskRequest,
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

	question = (
		request.question.strip()
	)

	if not question:
		raise HTTPException(
			status_code=400,
			detail=(
				"Question cannot "
				"be empty."
			),
		)

	results = retrieve_chunks(
		folder_id=folder_id,
		query=question,
		limit=request.limit,
	)

	evidence = evaluate_evidence(
		results
	)

	if not evidence.sufficient:
		return {
			"status": (
				"insufficient_evidence"
			),
			"folder_id": folder_id,
			"question": question,
			"answer": (
				"I couldn't find enough "
				"evidence in the indexed "
				"documents to answer that "
				"question reliably."
			),
			"generation_skipped": True,
			"evidence": {
				"sufficient": False,
				"strongest_score": (
					evidence.strongest_score
				),
				"threshold": (
					evidence.threshold
				),
				"reason": (
					evidence.reason
				),
			},
			"sources": [],
		}

	context_threshold = (
		get_context_threshold(
			strongest_score=(
				evidence.strongest_score
			),
			evidence_threshold=(
				evidence.threshold
			),
		)
	)

	(
		context,
		sources,
	) = build_grounded_context(
		results=results,
		context_threshold=(
			context_threshold
		),
	)

	if not context:
		return {
			"status": (
				"insufficient_evidence"
			),
			"folder_id": folder_id,
			"question": question,
			"answer": (
				"I couldn't find enough "
				"evidence in the indexed "
				"documents to answer that "
				"question reliably."
			),
			"generation_skipped": True,
			"evidence": {
				"sufficient": False,
				"strongest_score": (
					evidence.strongest_score
				),
				"threshold": (
					evidence.threshold
				),
				"context_threshold": (
					context_threshold
				),
				"reason": (
					"No retrieved chunks "
					"passed the context "
					"selection threshold."
				),
			},
			"sources": [],
		}

	try:
		generation = (
			generate_grounded_answer(
				question=question,
				context=context,
			)
		)

	except RuntimeError as error:
		raise HTTPException(
			status_code=502,
			detail=str(error),
		) from error

	return {
		"status": "answered",
		"folder_id": folder_id,
		"question": question,
		"answer": (
			generation["answer"]
		),
		"generation_skipped": False,
		"evidence": {
			"sufficient": True,
			"strongest_score": (
				evidence.strongest_score
			),
			"threshold": (
				evidence.threshold
			),
			"context_threshold": (
				context_threshold
			),
			"reason": (
				evidence.reason
			),
		},
		"generation": {
			"model": (
				generation["model"]
			),
			"usage": (
				generation["usage"]
			),
		},
		"sources": sources,
	}
