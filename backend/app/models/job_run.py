from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class JobRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "job_runs"

    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # pipeline_init/pipeline_plan/pipeline_write/audit/settle
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending/running/completed/failed/cancelled
    agent_chain: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    checkpoint_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
