from uuid import UUID

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class UsageRecord(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "usage_records"

    provider_config_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("provider_configs.id"), nullable=True
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    agent_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_runs.id"), nullable=True
    )
