from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FolderCreate(BaseModel):
	path: str


class FolderRead(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	name: str
	path: str
	created_at: datetime