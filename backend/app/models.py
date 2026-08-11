from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class RegisteredFolder(Base):
	__tablename__ = "registered_folders"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String, nullable=False)
	path: Mapped[str] = mapped_column(String, unique=True, nullable=False)

	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		default=lambda: datetime.now(timezone.utc),
		nullable=False,
	)


class Document(Base):
	__tablename__ = "documents"

	id: Mapped[int] = mapped_column(primary_key=True)

	folder_id: Mapped[int] = mapped_column(
		ForeignKey("registered_folders.id"),
		nullable=False,
		index=True,
	)

	relative_path: Mapped[str] = mapped_column(
		String,
		nullable=False,
		index=True,
	)

	absolute_path: Mapped[str] = mapped_column(
		String,
		nullable=False,
	)

	extension: Mapped[str] = mapped_column(
		String,
		nullable=False,
	)

	size_bytes: Mapped[int] = mapped_column(
		BigInteger,
		nullable=False,
	)

	modified_ns: Mapped[int] = mapped_column(
		BigInteger,
		nullable=False,
	)

	sha256: Mapped[str] = mapped_column(
		String,
		nullable=False,
	)

	status: Mapped[str] = mapped_column(
		String,
		default="pending",
		nullable=False,
	)

	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		default=lambda: datetime.now(timezone.utc),
		nullable=False,
	)