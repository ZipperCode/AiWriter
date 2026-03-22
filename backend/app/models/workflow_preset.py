from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class WorkflowPreset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_presets"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dag_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    human_loop_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
