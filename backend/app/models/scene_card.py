from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class SceneCard(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "scene_cards"

    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pov_character_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("entities.id"), nullable=True
    )
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    time_marker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    conflict: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    characters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    chapter = relationship("Chapter", back_populates="scene_cards")
