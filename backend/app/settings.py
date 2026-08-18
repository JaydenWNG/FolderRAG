from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import (
	BaseSettings,
	SettingsConfigDict,
)


PROJECT_ROOT = (
	Path(__file__)
	.resolve()
	.parents[2]
)

ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
	lm_studio_base_url: str = (
		"http://127.0.0.1:1234"
	)

	lm_studio_model: str = (
		"qwen3.5-9b"
	)

	lm_studio_api_key: (
		str | None
	) = None

	lm_studio_reasoning: Literal[
		"off",
		"low",
		"medium",
		"high",
		"on",
	] = "off"

	model_config = SettingsConfigDict(
		env_file=ENV_FILE,
		env_file_encoding="utf-8",
		env_prefix="FOLDERRAG_",
		extra="ignore",
	)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
	return Settings()