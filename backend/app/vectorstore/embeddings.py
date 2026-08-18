from functools import lru_cache

import numpy as np
import torch
from sentence_transformers import SentenceTransformer


MODEL_NAME = "perplexity-ai/pplx-embed-v1-4b"
VECTOR_SIZE = 2560
EMBEDDING_BATCH_SIZE = 8


class EmbeddingModel:
	def __init__(
		self,
		model_name: str = MODEL_NAME,
	):
		self.model_name = model_name

		self.device = (
			"cuda"
			if torch.cuda.is_available()
			else "cpu"
		)

		self._model: SentenceTransformer | None = None

	@property
	def model(
		self,
	) -> SentenceTransformer:
		"""
		Lazily load the retrieval embedding model.

		Loading is deferred so FastAPI can start without immediately
		reserving GPU memory.
		"""

		if self._model is None:
			model_dtype = (
				torch.float16
				if self.device == "cuda"
				else torch.float32
			)

			self._model = SentenceTransformer(
				self.model_name,
				trust_remote_code=True,
				device=self.device,
				model_kwargs={
					"torch_dtype": model_dtype,
				},
			)

		return self._model

	def encode(
		self,
		texts: list[str],
	) -> np.ndarray:
		"""
		Embed independent text chunks.

		Qdrant handles cosine normalization, so embeddings remain
		unnormalized here.
		"""

		if not texts:
			return np.empty(
				(
					0,
					VECTOR_SIZE,
				),
				dtype=np.float32,
			)

		embeddings = self.model.encode(
			texts,
			batch_size=EMBEDDING_BATCH_SIZE,
			show_progress_bar=False,
			convert_to_numpy=True,
		)

		embeddings = np.asarray(
			embeddings,
			dtype=np.float32,
		)

		if (
			embeddings.ndim != 2
			or embeddings.shape[1]
			!= VECTOR_SIZE
		):
			raise ValueError(
				"Unexpected embedding shape: "
				f"{embeddings.shape}. "
				f"Expected (*, {VECTOR_SIZE})."
			)

		if not np.isfinite(
			embeddings
		).all():
			raise ValueError(
				"Embedding model produced "
				"non-finite values."
			)

		return embeddings


@lru_cache(maxsize=1)
def get_embedding_model(
) -> EmbeddingModel:
	return EmbeddingModel()