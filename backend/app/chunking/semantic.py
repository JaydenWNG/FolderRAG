from dataclasses import dataclass
from functools import lru_cache
import re

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from ..extractors import ExtractedDocument, ExtractedSection
from .models import Chunk


MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Chunk size preferences.
#
# MIN is deliberately soft. A strong semantic topic change is allowed
# to create a smaller chunk rather than forcing unrelated content together.
MIN_CHUNK_TOKENS = 80
TARGET_CHUNK_TOKENS = 220
MAX_CHUNK_TOKENS = 380

ORPHAN_CHUNK_TOKENS = 30

# Paragraphs below this size remain whole semantic units.
# Larger paragraphs are split into sentence groups.
MAX_UNIT_TOKENS = 160

# An adjacent similarity below this value is considered a strong
# topic boundary regardless of the current chunk size.
STRONG_BREAK_SIMILARITY = 0.55

# Relative boundary detection helps adapt to documents whose overall
# similarity distribution is unusually high or low.
SEMANTIC_BREAK_PERCENTILE = 25.0

EMBEDDING_BATCH_SIZE = 64


@dataclass
class SemanticUnit:
	text: str

	start_offset: int
	end_offset: int

	token_count: int

	# Units belonging to the same paragraph are joined with spaces.
	# Different paragraphs are joined with blank lines.
	paragraph_index: int


class SemanticChunker:
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
	def model(self) -> SentenceTransformer:
		"""
		Lazily load BGE.

		FastAPI can start without loading the embedding model.
		BGE is loaded only when semantic chunking is first requested.
		"""

		if self._model is None:
			self._model = SentenceTransformer(
				self.model_name,
				device=self.device,
			)

		return self._model

	@property
	def tokenizer(self):
		return self.model.tokenizer

	def count_tokens(
		self,
		text: str,
	) -> int:
		if not text.strip():
			return 0

		token_ids = self.tokenizer.encode(
			text,
			add_special_tokens=False,
			truncation=False,
		)

		return len(token_ids)

	def _line_for_offset(
		self,
		section: ExtractedSection,
		offset: int,
	) -> int | None:
		if section.start_line is None:
			return None

		return (
			section.start_line
			+ section.text[:offset].count("\n")
		)

	def _trim_span(
		self,
		text: str,
		start: int,
		end: int,
	) -> tuple[str, int, int] | None:
		while (
			start < end
			and text[start].isspace()
		):
			start += 1

		while (
			end > start
			and text[end - 1].isspace()
		):
			end -= 1

		if start >= end:
			return None

		return (
			text[start:end],
			start,
			end,
		)

	def _paragraph_spans(
		self,
		text: str,
	) -> list[tuple[int, int]]:
		"""
		Find paragraphs separated by one or more blank lines.

		Character offsets are preserved so line provenance can still
		be calculated later.
		"""

		spans: list[tuple[int, int]] = []

		pattern = re.compile(
			r"\S[\s\S]*?(?=\n[ \t]*\n|\Z)"
		)

		for match in pattern.finditer(text):
			trimmed = self._trim_span(
				text,
				match.start(),
				match.end(),
			)

			if trimmed is None:
				continue

			_, start, end = trimmed

			spans.append(
				(start, end)
			)

		if not spans and text.strip():
			trimmed = self._trim_span(
				text,
				0,
				len(text),
			)

			if trimmed is not None:
				_, start, end = trimmed
				spans.append(
					(start, end)
				)

		return spans

	def _sentence_spans(
		self,
		text: str,
	) -> list[tuple[int, int]]:
		"""
		Create sentence-like spans for oversized paragraphs.

		This intentionally runs only on long paragraphs. Normal
		paragraphs remain intact.
		"""

		spans: list[tuple[int, int]] = []

		pattern = re.compile(
			r".+?"
			r"(?:"
			r"[.!?](?:[\"')\]]*)"
			r"(?=\s+|$)"
			r"|$"
			r")",
			re.DOTALL,
		)

		for match in pattern.finditer(text):
			trimmed = self._trim_span(
				text,
				match.start(),
				match.end(),
			)

			if trimmed is None:
				continue

			_, start, end = trimmed

			spans.append(
				(start, end)
			)

		if not spans and text.strip():
			spans.append(
				(0, len(text))
			)

		return spans

	def _split_oversized_text(
		self,
		text: str,
		base_offset: int,
		paragraph_index: int,
	) -> list[SemanticUnit]:
		"""
		Last-resort tokenizer-based splitting.

		This is used only when even a single sentence is larger than
		MAX_UNIT_TOKENS.
		"""

		encoded = self.tokenizer(
			text,
			add_special_tokens=False,
			truncation=False,
			return_offsets_mapping=True,
		)

		offsets = encoded[
			"offset_mapping"
		]

		if not offsets:
			return []

		units: list[SemanticUnit] = []

		for token_start in range(
			0,
			len(offsets),
			MAX_UNIT_TOKENS,
		):
			token_end = min(
				token_start + MAX_UNIT_TOKENS,
				len(offsets),
			)

			selected_offsets = offsets[
				token_start:token_end
			]

			char_start = (
				selected_offsets[0][0]
			)

			char_end = (
				selected_offsets[-1][1]
			)

			trimmed = self._trim_span(
				text,
				char_start,
				char_end,
			)

			if trimmed is None:
				continue

			segment, start, end = trimmed

			units.append(
				SemanticUnit(
					text=segment,
					start_offset=(
						base_offset + start
					),
					end_offset=(
						base_offset + end
					),
					token_count=self.count_tokens(
						segment
					),
					paragraph_index=(
						paragraph_index
					),
				)
			)

		return units

	def _split_long_paragraph(
		self,
		paragraph: str,
		paragraph_start: int,
		paragraph_index: int,
	) -> list[SemanticUnit]:
		"""
		Split a long paragraph into sentence groups.

		Several neighbouring sentences are packed together until the
		semantic-unit token budget is reached.
		"""

		sentence_spans = self._sentence_spans(
			paragraph
		)

		units: list[SemanticUnit] = []

		current_parts: list[str] = []

		current_start: int | None = None
		current_end: int | None = None

		current_tokens = 0

		def flush():
			nonlocal current_parts
			nonlocal current_start
			nonlocal current_end
			nonlocal current_tokens

			if (
				not current_parts
				or current_start is None
				or current_end is None
			):
				return

			combined = " ".join(
				part.strip()
				for part in current_parts
				if part.strip()
			)

			if combined:
				units.append(
					SemanticUnit(
						text=combined,
						start_offset=(
							paragraph_start
							+ current_start
						),
						end_offset=(
							paragraph_start
							+ current_end
						),
						token_count=self.count_tokens(
							combined
						),
						paragraph_index=(
							paragraph_index
						),
					)
				)

			current_parts = []
			current_start = None
			current_end = None
			current_tokens = 0

		for start, end in sentence_spans:
			sentence = paragraph[
				start:end
			].strip()

			if not sentence:
				continue

			sentence_tokens = (
				self.count_tokens(
					sentence
				)
			)

			if (
				sentence_tokens
				> MAX_UNIT_TOKENS
			):
				flush()

				units.extend(
					self._split_oversized_text(
						text=sentence,
						base_offset=(
							paragraph_start
							+ start
						),
						paragraph_index=(
							paragraph_index
						),
					)
				)

				continue

			if (
				current_parts
				and (
					current_tokens
					+ sentence_tokens
					> MAX_UNIT_TOKENS
				)
			):
				flush()

			if current_start is None:
				current_start = start

			current_end = end

			current_parts.append(
				sentence
			)

			current_tokens += (
				sentence_tokens
			)

		flush()

		return units

	def _semantic_units(
		self,
		section: ExtractedSection,
	) -> list[SemanticUnit]:
		"""
		Paragraph-first semantic units.

		Short/normal paragraphs remain whole. Only long paragraphs
		are broken into sentence groups.
		"""

		units: list[SemanticUnit] = []

		paragraph_spans = (
			self._paragraph_spans(
				section.text
			)
		)

		for paragraph_index, (
			start,
			end,
		) in enumerate(paragraph_spans):
			paragraph = section.text[
				start:end
			].strip()

			if not paragraph:
				continue

			token_count = (
				self.count_tokens(
					paragraph
				)
			)

			if (
				token_count
				<= MAX_UNIT_TOKENS
			):
				units.append(
					SemanticUnit(
						text=paragraph,
						start_offset=start,
						end_offset=end,
						token_count=(
							token_count
						),
						paragraph_index=(
							paragraph_index
						),
					)
				)

			else:
				units.extend(
					self._split_long_paragraph(
						paragraph=paragraph,
						paragraph_start=start,
						paragraph_index=(
							paragraph_index
						),
					)
				)

		return units

	def _adjacent_similarities(
		self,
		units: list[SemanticUnit],
	) -> np.ndarray:
		if len(units) <= 1:
			return np.array(
				[],
				dtype=np.float32,
			)

		texts = [
			unit.text
			for unit in units
		]

		embeddings = self.model.encode(
			texts,
			batch_size=EMBEDDING_BATCH_SIZE,
			show_progress_bar=False,
			convert_to_numpy=True,
			normalize_embeddings=True,
		)

		similarities = np.sum(
			embeddings[:-1]
			* embeddings[1:],
			axis=1,
		)

		return similarities

	def _join_units(
		self,
		units: list[SemanticUnit],
	) -> str:
		"""
		Reconstruct chunk text without relying on fragile character
		slicing across whitespace boundaries.
		"""

		if not units:
			return ""

		parts: list[str] = [
			units[0].text.strip()
		]

		previous = units[0]

		for unit in units[1:]:
			if (
				unit.paragraph_index
				== previous.paragraph_index
			):
				separator = " "
			else:
				separator = "\n\n"

			parts.append(
				separator
				+ unit.text.strip()
			)

			previous = unit

		return "".join(parts).strip()

	def _build_chunk(
		self,
		section: ExtractedSection,
		section_index: int,
		chunk_index: int,
		units: list[SemanticUnit],
	) -> Chunk:
		text = self._join_units(
			units
		)

		start_offset = (
			units[0].start_offset
		)

		end_offset = (
			units[-1].end_offset
		)

		start_line = (
			self._line_for_offset(
				section,
				start_offset,
			)
		)

		end_line_offset = max(
			start_offset,
			end_offset - 1,
		)

		end_line = (
			self._line_for_offset(
				section,
				end_line_offset,
			)
		)

		return Chunk(
			text=text,
			chunk_index=chunk_index,
			section_index=section_index,
			token_count=self.count_tokens(
				text
			),
			strategy="semantic",
			start_line=start_line,
			end_line=end_line,
			start_page=section.start_page,
			end_page=section.end_page,
			heading=section.heading,
			symbol=section.symbol,
			section_type=(
				section.section_type
			),
		)

	def _chunk_structured_section(
		self,
		section: ExtractedSection,
		section_index: int,
		chunk_index: int,
	) -> list[Chunk]:
		"""
		Keep Python functions and methods whole.

		Oversized symbols are flagged rather than silently split.
		"""

		text = section.text.strip()

		if not text:
			return []

		token_count = (
			self.count_tokens(text)
		)

		strategy = "python_symbol"

		if (
			token_count
			> MAX_CHUNK_TOKENS
		):
			strategy = (
				"python_symbol_oversize"
			)

		return [
			Chunk(
				text=text,
				chunk_index=chunk_index,
				section_index=section_index,
				token_count=token_count,
				strategy=strategy,
				start_line=(
					section.start_line
				),
				end_line=section.end_line,
				start_page=(
					section.start_page
				),
				end_page=section.end_page,
				heading=section.heading,
				symbol=section.symbol,
				section_type=(
					section.section_type
				),
			)
		]

	def _semantic_groups(
		self,
		units: list[SemanticUnit],
	) -> list[list[SemanticUnit]]:
		if not units:
			return []

		if len(units) == 1:
			return [
				units
			]

		similarities = (
			self._adjacent_similarities(
				units
			)
		)

		percentile_threshold = float(
			np.percentile(
				similarities,
				SEMANTIC_BREAK_PERCENTILE,
			)
		)

		median_similarity = float(
			np.median(
				similarities
			)
		)

		groups: list[
			list[SemanticUnit]
		] = []

		current: list[
			SemanticUnit
		] = [
			units[0]
		]

		current_tokens = (
			units[0].token_count
		)

		for boundary_index in range(
			len(units) - 1
		):
			similarity = float(
				similarities[
					boundary_index
				]
			)

			next_unit = units[
				boundary_index + 1
			]

			strong_semantic_break = (
				similarity
				< STRONG_BREAK_SIMILARITY
			)

			relative_semantic_break = (
				current_tokens
				>= MIN_CHUNK_TOKENS
				and similarity
				<= percentile_threshold
			)

			target_semantic_break = (
				current_tokens
				>= TARGET_CHUNK_TOKENS
				and similarity
				< median_similarity
			)

			size_break = (
				current_tokens
				+ next_unit.token_count
				> MAX_CHUNK_TOKENS
			)

			should_break = (
				strong_semantic_break
				or relative_semantic_break
				or target_semantic_break
				or size_break
			)

			if should_break:
				groups.append(
					current
				)

				current = [
					next_unit
				]

				current_tokens = (
					next_unit.token_count
				)

			else:
				current.append(
					next_unit
				)

				current_tokens += (
					next_unit.token_count
				)

		if current:
			groups.append(
				current
			)

		return self.merge_orphan_groups(
			groups=groups, 
			similarities=similarities
		)
	
	def merge_orphan_groups(
				self,
				groups: list[list[SemanticUnit]],
				similarities,
		) -> list[list[SemanticUnit]]:
				"""
				Repair extremely small semantic chunks.

				A strong semantic boundary may occasionally isolate a
				tiny fragment. Chunks below ORPHAN_CHUNK_TOKENS are
				merged into the more semantically similar immediate
				neighbour when the merged result remains within the
				maximum chunk size.

				Existing adjacent-unit similarities are reused, so
				this does not require another embedding pass.
				"""

				if len(groups) <= 1:
						return groups

				merged = [
						list(group)
						for group in groups
				]

				index = 0

				while index < len(merged):
						current = merged[index]

						current_tokens = sum(
								unit.token_count
								for unit in current
						)

						if (
								current_tokens
								>= ORPHAN_CHUNK_TOKENS
						):
								index += 1
								continue

						if len(merged) <= 1:
								break

						left_allowed = False
						right_allowed = False

						if index > 0:
								left_tokens = sum(
										unit.token_count
										for unit
										in merged[index - 1]
								)

								left_allowed = (
										left_tokens
										+ current_tokens
										<= MAX_CHUNK_TOKENS
								)

						if index + 1 < len(merged):
								right_tokens = sum(
										unit.token_count
										for unit
										in merged[index + 1]
								)

								right_allowed = (
										current_tokens
										+ right_tokens
										<= MAX_CHUNK_TOKENS
								)

						if (
								not left_allowed
								and not right_allowed
						):
								index += 1
								continue

						unit_start_index = sum(
								len(group)
								for group
								in merged[:index]
						)

						unit_end_index = (
								unit_start_index
								+ len(current)
						)

						left_similarity = (
								float("-inf")
						)

						right_similarity = (
								float("-inf")
						)

						if left_allowed:
								left_similarity = float(
										similarities[
												unit_start_index
												- 1
										]
								)

						if right_allowed:
								right_similarity = float(
										similarities[
												unit_end_index
												- 1
										]
								)

						if (
								left_allowed
								and (
										not right_allowed
										or left_similarity
										>= right_similarity
								)
						):
								merged[
										index - 1
								].extend(
										current
								)

								del merged[index]

								index = max(
										0,
										index - 1,
								)

						else:
								merged[index] = (
										current
										+ merged[index + 1]
								)

								del merged[
										index + 1
								]

				return merged

	def _chunk_semantic_section(
		self,
		section: ExtractedSection,
		section_index: int,
		starting_chunk_index: int,
	) -> list[Chunk]:
		units = self._semantic_units(
			section
		)

		if not units:
			return []

		groups = self._semantic_groups(
			units
		)

		chunks: list[Chunk] = []

		for local_index, group in enumerate(
			groups
		):
			chunks.append(
				self._build_chunk(
					section=section,
					section_index=(
						section_index
					),
					chunk_index=(
						starting_chunk_index
						+ local_index
					),
					units=group,
				)
			)

		return chunks

	def chunk_document(
		self,
		document: ExtractedDocument,
	) -> list[Chunk]:
		chunks: list[Chunk] = []

		next_chunk_index = 0

		for section_index, section in enumerate(
			document.sections
		):
			if section.section_type in {
				"function",
				"method",
			}:
				section_chunks = (
					self._chunk_structured_section(
						section=section,
						section_index=(
							section_index
						),
						chunk_index=(
							next_chunk_index
						),
					)
				)

			else:
				section_chunks = (
					self._chunk_semantic_section(
						section=section,
						section_index=(
							section_index
						),
						starting_chunk_index=(
							next_chunk_index
						),
					)
				)

			chunks.extend(
				section_chunks
			)

			next_chunk_index += len(
				section_chunks
			)

		return chunks


@lru_cache(maxsize=1)
def get_semantic_chunker() -> SemanticChunker:
	return SemanticChunker()