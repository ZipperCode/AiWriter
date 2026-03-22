from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.db.base import Base, TimestampMixin, UUIDMixin


class MemoryEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "memory_entries"

    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(settings.embedding_dim), nullable=True)
