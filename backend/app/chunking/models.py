from dataclasses import dataclass


@dataclass
class Chunk:
	text: str
	chunk_index: int
	section_index: int
	token_count: int
	strategy: str

	start_line: int | None = None
	end_line: int | None = None

	start_page: int | None = None
	end_page: int | None = None

	heading: str | None = None
	symbol: str | None = None
	section_type: str = "text"