from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    genre: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    target_words: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    volumes = relationship("Volume", back_populates="project", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="project", cascade="all, delete-orphan")
    truth_files = relationship("TruthFile", back_populates="project", cascade="all, delete-orphan")
    hooks = relationship("Hook", back_populates="project", cascade="all, delete-orphan")
