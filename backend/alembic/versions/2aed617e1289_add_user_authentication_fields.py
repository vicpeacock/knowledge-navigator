"""add_user_authentication_fields

Revision ID: 2aed617e1289
Revises: 0e1f99366975
Create Date: 2025-11-16 00:10:49.480149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '2aed617e1289'
down_revision: Union[str, None] = '0e1f99366975'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add authentication fields to users table
    op.add_column('users', sa.Column('password_hash', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('role', sa.String(50), nullable=False, server_default='user'))
    op.add_column('users', sa.Column('permissions', postgresql.JSONB, nullable=True, server_default='{}'))
    
    # Email verification
    op.add_column('users', sa.Column('email_verified', sa.Boolean, nullable=False, server_default='false'))
    op.add_column('users', sa.Column('email_verification_token', sa.String(255), nullable=True))
    
    # Password reset
    op.add_column('users', sa.Column('password_reset_token', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('password_reset_expires', sa.DateTime(timezone=True), nullable=True))
    
    # Session tracking
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('last_login_ip', sa.String(45), nullable=True))
    
    # Create indexes for performance (only if they don't exist)
    # Check if index exists before creating
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('users')]
    
    if 'ix_users_email' not in existing_indexes:
        op.create_index('ix_users_email', 'users', ['email'])
    
    # ix_users_tenant_id should already exist from previous migration
    if 'ix_users_tenant_id' not in existing_indexes:
        op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_users_email', table_name='users')
    try:
        op.drop_index('ix_users_tenant_id', table_name='users')
    except:
        pass
    
    # Remove columns
    op.drop_column('users', 'last_login_ip')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'password_reset_expires')
    op.drop_column('users', 'password_reset_token')
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'email_verified')
    op.drop_column('users', 'permissions')
    op.drop_column('users', 'role')
    op.drop_column('users', 'password_hash')

