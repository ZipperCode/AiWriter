from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db.base import Base, TimestampMixin, UUIDMixin


class Entity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "entities"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # character/location/faction/item/concept/power_system
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    locked_attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    knowledge_boundary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(settings.embedding_dim), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    # manual / auto_extracted

    project = relationship("Project", back_populates="entities")
