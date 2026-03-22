from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Chapter(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "chapters"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    volume_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("volumes.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pov_character_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("entities.id"), nullable=True
    )
    timeline_position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="planned"
    )  # planned/writing/draft_ready/audited/final/needs_revision
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    project = relationship("Project")
    volume = relationship("Volume", back_populates="chapters")
    drafts = relationship("Draft", back_populates="chapter", cascade="all, delete-orphan")
    scene_cards = relationship("SceneCard", back_populates="chapter", cascade="all, delete-orphan")
