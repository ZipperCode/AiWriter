from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class TruthFile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "truth_files"
    __table_args__ = (UniqueConstraint("project_id", "file_type"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # story_bible/volume_outline/book_rules/current_state/particle_ledger
    # pending_hooks/chapter_summaries/subplot_board/emotional_arcs/character_matrix
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )

    project = relationship("Project", back_populates="truth_files")
    history = relationship(
        "TruthFileHistory", back_populates="truth_file", cascade="all, delete-orphan"
    )


class TruthFileHistory(Base, UUIDMixin):
    """History table — no TimestampMixin (immutable records don't need updated_at)."""

    __tablename__ = "truth_file_history"

    truth_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("truth_files.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    changed_by_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    truth_file = relationship("TruthFile", back_populates="history")
