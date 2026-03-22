from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class BookRules(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "book_rules"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    base_guardrails: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    genre_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    custom_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
