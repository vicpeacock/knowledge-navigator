"""Add title, description, status, and archived_at to sessions

Revision ID: a39125eacc42
Revises: 
Create Date: 2025-11-03 11:02:25.801291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a39125eacc42'
down_revision: Union[str, None] = '000_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to sessions table
    op.add_column('sessions', sa.Column('title', sa.String(length=255), nullable=True))
    op.add_column('sessions', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('sessions', sa.Column('status', sa.String(length=20), nullable=False, server_default='active'))
    op.add_column('sessions', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove columns from sessions table
    op.drop_column('sessions', 'archived_at')
    op.drop_column('sessions', 'status')
    op.drop_column('sessions', 'description')
    op.drop_column('sessions', 'title')

