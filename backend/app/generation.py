import httpx

from .settings import get_settings


DEFAULT_TIMEOUT_SECONDS = 300.0


def build_headers(
) -> dict[str, str]:
	settings = get_settings()

	headers = {
		"Content-Type": "application/json",
	}

	if settings.lm_studio_api_key:
		headers[
			"Authorization"
		] = (
			"Bearer "
			f"{settings.lm_studio_api_key}"
		)

	return headers


def generate_grounded_answer(
	question: str,
	context: str,
) -> dict:
	settings = get_settings()

	system_prompt = """
You are the answer-generation component of FolderRAG.

Answer the user's question using ONLY the supplied sources.

Rules:
1. Do not use outside knowledge.
2. Do not invent information that is absent from the sources.
3. Every factual claim supported by a source must cite that source using
its exact source label, for example [S1] or [S2].
4. You may cite multiple sources together, for example [S1][S3].
5. Do not create source labels that were not supplied.
6. If the supplied sources do not contain enough information to answer
the question, explicitly say that the available documents do not
provide enough information.
7. Give a direct, concise answer before optional explanation.
""".strip()

	user_prompt = f"""
QUESTION:
{question}

SOURCES:
{context}
""".strip()

	payload = {
		"model": (
			settings.lm_studio_model
		),
		"input": user_prompt,
		"system_prompt": system_prompt,
		"temperature": 0.1,
		"max_output_tokens": 800,
		"reasoning": (
			settings.lm_studio_reasoning
		),
		"stream": False,
	}

	url = (
		settings
		.lm_studio_base_url
		.rstrip("/")
		+ "/api/v1/chat"
	)

	try:
		with httpx.Client(
			timeout=(
				DEFAULT_TIMEOUT_SECONDS
			)
		) as client:
			response = client.post(
				url,
				headers=build_headers(),
				json=payload,
			)

			response.raise_for_status()

	except httpx.ConnectError as error:
		raise RuntimeError(
			"Could not connect to "
			"LM Studio at "
			f"{settings.lm_studio_base_url}."
		) from error

	except httpx.TimeoutException as error:
		raise RuntimeError(
			"LM Studio generation "
			"timed out."
		) from error

	except httpx.HTTPStatusError as error:
		raise RuntimeError(
			"LM Studio returned HTTP "
			f"{error.response.status_code}: "
			f"{error.response.text}"
		) from error

	data = response.json()

	output = data.get(
		"output",
		[],
	)

	message_parts = [
		item.get(
			"content",
			"",
		).strip()
		for item in output
		if (
			item.get("type")
			== "message"
			and item.get("content")
		)
	]

	answer = "\n".join(
		part
		for part in message_parts
		if part
	).strip()

	if not answer:
		raise RuntimeError(
			"LM Studio returned "
			"no final message."
		)

	stats = data.get(
		"stats",
		{},
	)

	return {
		"answer": answer,
		"model": data.get(
			"model_instance_id",
			settings.lm_studio_model,
		),
		"usage": {
			"prompt_tokens": (
				stats.get(
					"input_tokens"
				)
			),
			"completion_tokens": (
				stats.get(
					"total_output_tokens"
				)
			),
			"reasoning_tokens": (
				stats.get(
					"reasoning_output_tokens"
				)
			),
			"tokens_per_second": (
				stats.get(
					"tokens_per_second"
				)
			),
		},
	}