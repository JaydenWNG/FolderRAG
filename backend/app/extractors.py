import ast
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class ExtractedSection:
	text: str
	start_line: int | None = None
	end_line: int | None = None
	start_page: int | None = None
	end_page: int | None = None
	heading: str | None = None
	symbol: str | None = None
	section_type: str = "text"


@dataclass
class ExtractedDocument:
	path: Path
	extension: str
	sections: list[ExtractedSection]


def read_text_file(path: Path) -> str:
	try:
		return path.read_text(encoding="utf-8")
	except UnicodeDecodeError:
		return path.read_text(
			encoding="utf-8",
			errors="replace",
		)


def extract_plain_text(path: Path) -> ExtractedDocument:
	text = read_text_file(path)
	lines = text.splitlines()

	sections: list[ExtractedSection] = []

	if text.strip():
		sections.append(
			ExtractedSection(
				text=text,
				start_line=1,
				end_line=max(1, len(lines)),
				section_type="text",
			)
		)

	return ExtractedDocument(
		path=path,
		extension=path.suffix.lower(),
		sections=sections,
	)


def extract_markdown(path: Path) -> ExtractedDocument:
	text = read_text_file(path)
	lines = text.splitlines()

	sections: list[ExtractedSection] = []

	current_heading: str | None = None
	current_start = 1
	current_lines: list[str] = []

	def flush_section(end_line: int):
		nonlocal current_lines

		section_text = "\n".join(current_lines).strip()

		if section_text:
			sections.append(
				ExtractedSection(
					text=section_text,
					start_line=current_start,
					end_line=end_line,
					heading=current_heading,
					section_type="markdown",
				)
			)

		current_lines = []

	for line_number, line in enumerate(lines, start=1):
		stripped = line.strip()

		if stripped.startswith("#"):
			heading_text = stripped.lstrip("#").strip()

			if heading_text:
				flush_section(line_number - 1)

				current_heading = heading_text
				current_start = line_number
				current_lines = [line]
				continue

		if not current_lines:
			current_start = line_number

		current_lines.append(line)

	flush_section(len(lines))

	if not sections and text.strip():
		sections.append(
			ExtractedSection(
				text=text,
				start_line=1,
				end_line=max(1, len(lines)),
				section_type="markdown",
			)
		)

	return ExtractedDocument(
		path=path,
		extension=".md",
		sections=sections,
	)


def extract_python(path: Path) -> ExtractedDocument:
	text = read_text_file(path)
	lines = text.splitlines()

	try:
		tree = ast.parse(text)
	except SyntaxError:
		return extract_plain_text(path)

	sections: list[ExtractedSection] = []

	def source_for_node(node: ast.AST) -> str:
		start = getattr(node, "lineno", 1)
		end = getattr(node, "end_lineno", start)

		return "\n".join(
			lines[start - 1:end]
		).strip()

	for node in tree.body:
		if isinstance(
			node,
			(ast.FunctionDef, ast.AsyncFunctionDef),
		):
			sections.append(
				ExtractedSection(
					text=source_for_node(node),
					start_line=node.lineno,
					end_line=node.end_lineno or node.lineno,
					heading=node.name,
					symbol=node.name,
					section_type="function",
				)
			)

		elif isinstance(node, ast.ClassDef):
			for child in node.body:
				if isinstance(
					child,
					(ast.FunctionDef, ast.AsyncFunctionDef),
				):
					sections.append(
						ExtractedSection(
							text=source_for_node(child),
							start_line=child.lineno,
							end_line=child.end_lineno or child.lineno,
							heading=node.name,
							symbol=f"{node.name}.{child.name}",
							section_type="method",
						)
					)

	if not sections and text.strip():
		return extract_plain_text(path)

	return ExtractedDocument(
		path=path,
		extension=".py",
		sections=sections,
	)


def extract_pdf(path: Path) -> ExtractedDocument:
	reader = PdfReader(str(path))

	sections: list[ExtractedSection] = []

	for page_number, page in enumerate(
		reader.pages,
		start=1,
	):
		text = page.extract_text() or ""
		text = text.strip()

		if not text:
			continue

		sections.append(
			ExtractedSection(
				text=text,
				start_page=page_number,
				end_page=page_number,
				section_type="pdf_page",
			)
		)

	if not sections:
		raise ValueError(
			"PDF contains no extractable text. OCR is not supported yet."
		)

	return ExtractedDocument(
		path=path,
		extension=".pdf",
		sections=sections,
	)


def extract_document(path: Path) -> ExtractedDocument:
	extension = path.suffix.lower()

	if extension == ".pdf":
		return extract_pdf(path)

	if extension == ".md":
		return extract_markdown(path)

	if extension == ".py":
		return extract_python(path)

	if extension == ".txt":
		return extract_plain_text(path)

	raise ValueError(
		f"Unsupported extraction format: {extension}"
	)