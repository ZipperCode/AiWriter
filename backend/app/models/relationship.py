from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Relationship(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "relationships"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    target_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # ally/enemy/parent/lover/mentor/subordinate...
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    valid_from_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )
    valid_to_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )

    source_entity = relationship("Entity", foreign_keys=[source_entity_id])
    target_entity = relationship("Entity", foreign_keys=[target_entity_id])
