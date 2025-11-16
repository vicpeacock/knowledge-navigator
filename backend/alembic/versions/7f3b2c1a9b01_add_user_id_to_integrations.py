"""add user_id to integrations

Revision ID: 7f3b2c1a9b01
Revises: 5c0f96050fff_add_user_id_to_sessions
Create Date: 2025-11-16 02:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7f3b2c1a9b01"
down_revision: Union[str, None] = "5c0f96050fff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id column to integrations (nullable for backward compatibility)
    op.add_column(
        "integrations",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Create foreign key to users.id
    op.create_foreign_key(
        op.f("fk_integrations_user_id_users"),
        "integrations",
        "users",
        ["user_id"],
        ["id"],
    )
    # Index for fast lookups by user
    op.create_index(
        op.f("ix_integrations_user_id"),
        "integrations",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_integrations_user_id"), table_name="integrations")
    op.drop_constraint(
        op.f("fk_integrations_user_id_users"),
        "integrations",
        type_="foreignkey",
    )
    op.drop_column("integrations", "user_id")


