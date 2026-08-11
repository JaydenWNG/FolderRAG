import hashlib
import os
from pathlib import Path


SUPPORTED_EXTENSIONS = {
	".pdf",
	".txt",
	".md",
	".py",
}

IGNORED_DIRECTORIES = {
	".git",
	".venv",
	"venv",
	"node_modules",
	"__pycache__",
	"dist",
	"build",
	"coverage",
}

IGNORED_FILES = {
	"package-lock.json",
	"pnpm-lock.yaml",
	"yarn.lock",
	"poetry.lock",
	"uv.lock",
	"Cargo.lock",
}


def is_hidden(path: Path) -> bool:
	return any(part.startswith(".") for part in path.parts)


def should_ignore_directory(path: Path) -> bool:
	return path.name in IGNORED_DIRECTORIES or path.name.startswith(".")


def should_index_file(path: Path) -> bool:
	if path.name.startswith("."):
		return False

	if path.name in IGNORED_FILES:
		return False

	return path.suffix.lower() in SUPPORTED_EXTENSIONS


def sha256_file(path: Path) -> str:
	hasher = hashlib.sha256()

	with path.open("rb") as file:
		while chunk := file.read(1024 * 1024):
			hasher.update(chunk)

	return hasher.hexdigest()


def discover_files(root: Path) -> list[Path]:
	discovered: list[Path] = []

	for current_dir, directories, filenames in os.walk(root):
		current_path = Path(current_dir)

		directories[:] = [
			directory
			for directory in directories
			if not should_ignore_directory(current_path / directory)
		]

		for filename in filenames:
			path = current_path / filename

			if should_index_file(path):
				discovered.append(path)

	return discovered