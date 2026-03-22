from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class ProviderConfig(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "provider_configs"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # openai_compat / anthropic / google
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # Fernet encrypted API key
    default_model: Mapped[str] = mapped_column(String(100), nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
