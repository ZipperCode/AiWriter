from uuid import UUID

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PacingMeta(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pacing_meta"

    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    quest_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    fire_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    constellation_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    highlight_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    highlight_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tension_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    strand_tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
