import ast
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from statistics import median

import pymupdf


SAME_ROW_TOLERANCE = 2.0
MIN_LARGE_GAP = 5.0
GAP_MULTIPLIER = 2.5
INDENT_TOLERANCE = 8.0

BULLET_PREFIXES = (
    "•",
    "●",
    "◦",
    "▪",
    "‣",
    "-",
    "–",
    "—",
)


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


@dataclass
class PdfLine:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class PdfLayoutUnit:
    lines: list[PdfLine]


def read_text_file(
    path: Path,
) -> str:
    try:
        return path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:
        return path.read_text(
            encoding="utf-8",
            errors="replace",
        )


def extract_plain_text(
    path: Path,
) -> ExtractedDocument:
    text = read_text_file(path)
    lines = text.splitlines()

    sections: list[ExtractedSection] = []

    if text.strip():
        sections.append(
            ExtractedSection(
                text=text,
                start_line=1,
                end_line=max(
                    1,
                    len(lines),
                ),
                section_type="text",
            )
        )

    return ExtractedDocument(
        path=path,
        extension=path.suffix.lower(),
        sections=sections,
    )


def extract_markdown(
    path: Path,
) -> ExtractedDocument:
    text = read_text_file(path)
    lines = text.splitlines()

    sections: list[ExtractedSection] = []

    current_heading: str | None = None
    current_start = 1
    current_lines: list[str] = []

    def flush_section(
        end_line: int,
    ):
        nonlocal current_lines

        section_text = "\n".join(
            current_lines
        ).strip()

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

    for line_number, line in enumerate(
        lines,
        start=1,
    ):
        stripped = line.strip()

        if stripped.startswith("#"):
            heading_text = (
                stripped
                .lstrip("#")
                .strip()
            )

            if heading_text:
                flush_section(
                    line_number - 1
                )

                current_heading = (
                    heading_text
                )

                current_start = (
                    line_number
                )

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
                end_line=max(
                    1,
                    len(lines),
                ),
                section_type="markdown",
            )
        )

    return ExtractedDocument(
        path=path,
        extension=".md",
        sections=sections,
    )


def extract_python(
    path: Path,
) -> ExtractedDocument:
    text = read_text_file(path)
    lines = text.splitlines()

    try:
        tree = ast.parse(text)

    except SyntaxError:
        return extract_plain_text(path)

    sections: list[ExtractedSection] = []

    def source_for_node(
        node: ast.AST,
    ) -> str:
        start = getattr(
            node,
            "lineno",
            1,
        )

        end = getattr(
            node,
            "end_lineno",
            start,
        )

        return "\n".join(
            lines[start - 1:end]
        ).strip()

    for node in tree.body:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            sections.append(
                ExtractedSection(
                    text=source_for_node(
                        node
                    ),
                    start_line=node.lineno,
                    end_line=(
                        node.end_lineno
                        or node.lineno
                    ),
                    heading=node.name,
                    symbol=node.name,
                    section_type="function",
                )
            )

        elif isinstance(
            node,
            ast.ClassDef,
        ):
            for child in node.body:
                if isinstance(
                    child,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                ):
                    sections.append(
                        ExtractedSection(
                            text=source_for_node(
                                child
                            ),
                            start_line=(
                                child.lineno
                            ),
                            end_line=(
                                child.end_lineno
                                or child.lineno
                            ),
                            heading=node.name,
                            symbol=(
                                f"{node.name}."
                                f"{child.name}"
                            ),
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


def clean_pdf_text(
    text: str,
) -> str:
    """
    Remove invisible PDF formatting characters and collapse
    unnecessary horizontal whitespace.
    """

    text = "".join(
        character
        for character in text
        if unicodedata.category(
            character
        ) != "Cf"
    )

    text = text.replace(
        "\xa0",
        " ",
    )

    return re.sub(
        r"[ \t]+",
        " ",
        text,
    ).strip()


def starts_with_bullet(
    text: str,
) -> bool:
    stripped = text.lstrip()

    return stripped.startswith(
        BULLET_PREFIXES
    )


def extract_pdf_line_fragments(
    page,
) -> list[PdfLine]:
    """
    Extract text lines with their geometric position.

    A PDF may represent text on the same visual row as several
    independent spans or lines, so these are merged later.
    """

    data = page.get_text(
        "dict",
        sort=True,
    )

    fragments: list[PdfLine] = []

    for block in data["blocks"]:
        if "lines" not in block:
            continue

        for line in block["lines"]:
            pieces: list[
                tuple[float, str]
            ] = []

            for span in line["spans"]:
                text = clean_pdf_text(
                    span["text"]
                )

                if not text:
                    continue

                pieces.append(
                    (
                        float(
                            span["bbox"][0]
                        ),
                        text,
                    )
                )

            if not pieces:
                continue

            pieces.sort(
                key=lambda item: item[0]
            )

            text = clean_pdf_text(
                " ".join(
                    piece[1]
                    for piece in pieces
                )
            )

            if not text:
                continue

            x0, y0, x1, y1 = (
                line["bbox"]
            )

            fragments.append(
                PdfLine(
                    text=text,
                    x0=float(x0),
                    y0=float(y0),
                    x1=float(x1),
                    y1=float(y1),
                )
            )

    return fragments


def merge_same_visual_rows(
    lines: list[PdfLine],
) -> list[PdfLine]:
    """
    Merge PDF fragments that occur on the same rendered row.

    This fixes layouts where, for example, a company name appears on
    the left and its date appears on the right as separate PDF objects.
    """

    if not lines:
        return []

    ordered = sorted(
        lines,
        key=lambda line: (
            line.y0,
            line.x0,
        ),
    )

    groups: list[
        list[PdfLine]
    ] = []

    current = [
        ordered[0]
    ]

    for line in ordered[1:]:
        reference_y = median(
            item.y0
            for item in current
        )

        if (
            abs(
                line.y0
                - reference_y
            )
            <= SAME_ROW_TOLERANCE
        ):
            current.append(line)

        else:
            groups.append(
                current
            )

            current = [
                line
            ]

    groups.append(current)

    merged: list[PdfLine] = []

    for group in groups:
        group.sort(
            key=lambda line: (
                line.x0
            )
        )

        text = clean_pdf_text(
            " ".join(
                line.text
                for line in group
            )
        )

        if not text:
            continue

        merged.append(
            PdfLine(
                text=text,
                x0=min(
                    line.x0
                    for line in group
                ),
                y0=min(
                    line.y0
                    for line in group
                ),
                x1=max(
                    line.x1
                    for line in group
                ),
                y1=max(
                    line.y1
                    for line in group
                ),
            )
        )

    return merged


def calculate_normal_gap(
    lines: list[PdfLine],
) -> float:
    """
    Estimate ordinary line spacing from the current page.

    This keeps layout decisions document-relative instead of relying
    on one fixed PDF template.
    """

    gaps: list[float] = []

    for previous, current in zip(
        lines,
        lines[1:],
    ):
        gap = (
            current.y0
            - previous.y1
        )

        if (
            0
            <= gap
            <= 10
        ):
            gaps.append(gap)

    if not gaps:
        return 2.0

    return max(
        0.5,
        median(gaps),
    )


def build_pdf_layout_units(
    lines: list[PdfLine],
) -> list[PdfLayoutUnit]:
    """
    Group visually related PDF rows.

    Units are based only on geometry and generic document structure:
    - unusually large vertical gaps
    - bullet starts
    - indentation / wrapped-line behaviour

    There are no resume-specific heading names or content rules here.
    """

    if not lines:
        return []

    normal_gap = (
        calculate_normal_gap(
            lines
        )
    )

    large_gap_threshold = max(
        MIN_LARGE_GAP,
        normal_gap
        * GAP_MULTIPLIER,
    )

    units: list[
        PdfLayoutUnit
    ] = []

    current = PdfLayoutUnit(
        lines=[
            lines[0]
        ]
    )

    for previous, line in zip(
        lines,
        lines[1:],
    ):
        gap = (
            line.y0
            - previous.y1
        )

        bullet = (
            starts_with_bullet(
                line.text
            )
        )

        indented_continuation = (
            line.x0
            > previous.x0
            + INDENT_TOLERANCE
            and gap
            < large_gap_threshold
        )

        large_visual_gap = (
            gap
            >= large_gap_threshold
        )

        should_start_new_unit = (
            large_visual_gap
            or (
                bullet
                and not
                indented_continuation
            )
        )

        if should_start_new_unit:
            units.append(
                current
            )

            current = (
                PdfLayoutUnit(
                    lines=[
                        line
                    ]
                )
            )

        else:
            current.lines.append(
                line
            )

    units.append(current)

    return units


def pdf_unit_text(
    unit: PdfLayoutUnit,
) -> str:
    """
    Reconstruct one logical layout unit.

    Wrapped lines are joined with spaces. Different logical units
    are separated by blank lines later so the semantic chunker sees
    them as paragraph-like boundaries.
    """

    return clean_pdf_text(
        " ".join(
            line.text
            for line in unit.lines
        )
    )


def extract_pdf(
    path: Path,
) -> ExtractedDocument:
    document = pymupdf.open(
        path
    )

    sections: list[
        ExtractedSection
    ] = []

    try:
        for page_number, page in enumerate(
            document,
            start=1,
        ):
            fragments = (
                extract_pdf_line_fragments(
                    page
                )
            )

            lines = (
                merge_same_visual_rows(
                    fragments
                )
            )

            units = (
                build_pdf_layout_units(
                    lines
                )
            )

            unit_texts = [
                pdf_unit_text(unit)
                for unit in units
            ]

            unit_texts = [
                text
                for text in unit_texts
                if text
            ]

            if not unit_texts:
                continue

            page_text = "\n\n".join(
                unit_texts
            )

            sections.append(
                ExtractedSection(
                    text=page_text,
                    start_page=page_number,
                    end_page=page_number,
                    section_type=(
                        "pdf_layout"
                    ),
                )
            )

    finally:
        document.close()

    if not sections:
        raise ValueError(
            "PDF contains no extractable "
            "text. OCR is not supported yet."
        )

    return ExtractedDocument(
        path=path,
        extension=".pdf",
        sections=sections,
    )


def extract_document(
    path: Path,
) -> ExtractedDocument:
    extension = (
        path.suffix.lower()
    )

    if extension == ".pdf":
        return extract_pdf(path)

    if extension == ".md":
        return extract_markdown(path)

    if extension == ".py":
        return extract_python(path)

    if extension == ".txt":
        return extract_plain_text(path)

    raise ValueError(
        f"Unsupported extraction format: "
        f"{extension}"
    )