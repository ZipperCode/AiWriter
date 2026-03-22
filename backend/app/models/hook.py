from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Hook(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "hooks"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    hook_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # foreshadow / cliffhanger / chekhov_gun
    description: Mapped[str] = mapped_column(Text, nullable=False)
    planted_chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id"), nullable=False
    )
    expected_resolve_chapter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolved_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    # open / resolved / abandoned

    project = relationship("Project", back_populates="hooks")
