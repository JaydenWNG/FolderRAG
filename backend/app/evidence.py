import os
from dataclasses import dataclass


DEFAULT_MIN_SCORE = 0.20
DEFAULT_CONTEXT_SCORE_MARGIN = 0.15


def get_min_score() -> float:
	raw_value = os.getenv(
		"FOLDERRAG_EVIDENCE_MIN_SCORE"
	)

	if raw_value is None:
		return DEFAULT_MIN_SCORE

	try:
		value = float(raw_value)
	except ValueError:
		return DEFAULT_MIN_SCORE

	return max(
		-1.0,
		min(
			value,
			1.0,
		),
	)


def get_context_score_margin() -> float:
	raw_value = os.getenv(
		"FOLDERRAG_CONTEXT_SCORE_MARGIN"
	)

	if raw_value is None:
		return DEFAULT_CONTEXT_SCORE_MARGIN

	try:
		value = float(raw_value)
	except ValueError:
		return DEFAULT_CONTEXT_SCORE_MARGIN

	return max(
		0.0,
		min(
			value,
			2.0,
		),
	)


def get_context_threshold(
	strongest_score: float,
	evidence_threshold: float,
) -> float:
	return max(
		evidence_threshold,
		strongest_score
		- get_context_score_margin(),
	)


@dataclass
class EvidenceDecision:
	sufficient: bool
	strongest_score: float | None
	threshold: float
	reason: str


def evaluate_evidence(
	results: list[dict],
) -> EvidenceDecision:
	threshold = get_min_score()

	if not results:
		return EvidenceDecision(
			sufficient=False,
			strongest_score=None,
			threshold=threshold,
			reason=(
				"No relevant chunks "
				"were retrieved."
			),
		)

	scores = [
		float(result["score"])
		for result in results
		if result.get("score")
		is not None
	]

	if not scores:
		return EvidenceDecision(
			sufficient=False,
			strongest_score=None,
			threshold=threshold,
			reason=(
				"Retrieved chunks did "
				"not contain similarity "
				"scores."
			),
		)

	strongest_score = max(scores)

	if strongest_score < threshold:
		return EvidenceDecision(
			sufficient=False,
			strongest_score=(
				strongest_score
			),
			threshold=threshold,
			reason=(
				"Retrieved evidence is "
				"below the minimum "
				"similarity threshold."
			),
		)

	return EvidenceDecision(
		sufficient=True,
		strongest_score=(
			strongest_score
		),
		threshold=threshold,
		reason=(
			"Retrieved evidence passes "
			"the similarity threshold."
		),
	)
