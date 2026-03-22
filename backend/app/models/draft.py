from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db.base import Base, TimestampMixin, UUIDMixin


class Draft(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "drafts"

    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    audit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    content_embedding = mapped_column(Vector(settings.embedding_dim), nullable=True)

    chapter = relationship("Chapter", back_populates="drafts")
