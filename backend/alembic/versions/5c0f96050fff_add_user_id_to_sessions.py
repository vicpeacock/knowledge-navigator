"""add_user_id_to_sessions

Revision ID: 5c0f96050fff
Revises: 2aed617e1289
Create Date: 2025-11-15 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5c0f96050fff'
down_revision: Union[str, None] = '2aed617e1289'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id column to sessions table (nullable for backward compatibility)
    op.add_column('sessions', sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_sessions_user_id',
        'sessions', 'users',
        ['user_id'], ['id'],
        ondelete='SET NULL'  # If user is deleted, set user_id to NULL
    )
    
    # Create index for performance
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    
    # Note: We don't populate existing sessions with user_id
    # They will remain NULL, and the API will handle this gracefully
    # New sessions will always have user_id set


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_sessions_user_id', table_name='sessions')
    
    # Drop foreign key
    op.drop_constraint('fk_sessions_user_id', 'sessions', type_='foreignkey')
    
    # Drop column
    op.drop_column('sessions', 'user_id')
