"""Add last_indexed_at to sessions table for session indexing tracking

Revision ID: add_session_indexing
Revises: add_user_id_to_files
Create Date: 2025-11-30 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "add_session_indexing"
down_revision: Union[str, None] = "add_user_id_to_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_indexed_at column to sessions (nullable, for existing sessions)
    op.add_column(
        "sessions",
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Create index for efficient queries on sessions that need indexing
    op.create_index(
        op.f("ix_sessions_last_indexed_at"),
        "sessions",
        ["last_indexed_at"],
        unique=False,
    )
    
    # Create composite index for user + last_indexed_at (for finding sessions to index)
    op.create_index(
        op.f("ix_sessions_user_last_indexed"),
        "sessions",
        ["user_id", "last_indexed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sessions_user_last_indexed"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_last_indexed_at"), table_name="sessions")
    op.drop_column("sessions", "last_indexed_at")

