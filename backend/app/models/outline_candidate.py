from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class OutlineCandidate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "outline_candidates"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    # plot_blueprint / volume_outline / chapter_plan
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
