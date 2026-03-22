"""add_hnsw_indices

Revision ID: 91b2209b40d6
Revises: b2498cf93c04
Create Date: 2026-03-22 18:02:59.008778

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91b2209b40d6'
down_revision: Union[str, Sequence[str], None] = 'b2498cf93c04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_embedding "
        "ON entities USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_entries_embedding "
        "ON memory_entries USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_drafts_content_embedding "
        "ON drafts USING hnsw (content_embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_drafts_content_embedding")
    op.execute("DROP INDEX IF EXISTS idx_memory_entries_embedding")
    op.execute("DROP INDEX IF EXISTS idx_entities_embedding")
