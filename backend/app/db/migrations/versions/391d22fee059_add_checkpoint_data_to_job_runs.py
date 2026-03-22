"""add checkpoint_data to job_runs

Revision ID: 391d22fee059
Revises: 91b2209b40d6
Create Date: 2026-03-22 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '391d22fee059'
down_revision: Union[str, Sequence[str], None] = '91b2209b40d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add checkpoint_data column to job_runs table
    op.add_column('job_runs', sa.Column('checkpoint_data', JSONB(), nullable=False, server_default='{}'))


def downgrade() -> None:
    # Remove checkpoint_data column from job_runs table
    op.drop_column('job_runs', 'checkpoint_data')
