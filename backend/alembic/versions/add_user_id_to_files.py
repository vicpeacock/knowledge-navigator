"""add user_id to files and make session_id nullable

Revision ID: add_user_id_to_files
Revises: a39125eacc42
Create Date: 2025-11-29 23:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "add_user_id_to_files"
down_revision: Union[str, None] = "3fa60a542746"  # After add_purpose_to_integrations
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id column to files (nullable initially for data migration)
    op.add_column(
        "files",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    
    # Migrate existing data: get user_id from session.user_id
    op.execute("""
        UPDATE files f
        SET user_id = s.user_id
        FROM sessions s
        WHERE f.session_id = s.id
    """)
    
    # Now make user_id NOT NULL (after data migration)
    op.alter_column("files", "user_id", nullable=False)
    
    # Create foreign key to users.id
    op.create_foreign_key(
        op.f("fk_files_user_id_users"),
        "files",
        "users",
        ["user_id"],
        ["id"],
    )
    
    # Make session_id nullable (files are now user-scoped, not session-scoped)
    op.alter_column("files", "session_id", nullable=True)
    
    # Create index for fast lookups by user
    op.create_index(
        op.f("ix_files_user_id"),
        "files",
        ["user_id"],
        unique=False,
    )
    
    # Create composite index for user + tenant lookups
    op.create_index(
        op.f("ix_files_user_tenant"),
        "files",
        ["user_id", "tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_files_user_tenant"), table_name="files")
    op.drop_index(op.f("ix_files_user_id"), table_name="files")
    op.alter_column("files", "session_id", nullable=False)
    op.drop_constraint(
        op.f("fk_files_user_id_users"),
        "files",
        type_="foreignkey",
    )
    op.drop_column("files", "user_id")

