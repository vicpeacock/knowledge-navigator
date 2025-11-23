"""add_mcp_server_service_type

Revision ID: 234e8f042523
Revises: a39125eacc42
Create Date: 2025-11-03 11:28:09.797437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '234e8f042523'
down_revision: Union[str, None] = 'a39125eacc42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration was incorrectly auto-generated and tried to drop all tables
    # Instead, we just ensure the service_type column exists in integrations table
    # The service_type column should already exist, but we add it if it doesn't
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check if service_type column exists
    if 'integrations' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('integrations')]
        if 'service_type' not in columns:
            op.add_column('integrations', sa.Column('service_type', sa.String(50), nullable=True))
            # Set default value for existing rows
            op.execute(sa.text("UPDATE integrations SET service_type = 'email' WHERE service_type IS NULL"))
            # Make it NOT NULL after setting defaults
            op.alter_column('integrations', 'service_type', nullable=False)
    # No other changes needed - tables should remain intact


def downgrade() -> None:
    # Remove service_type column if it exists
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    if 'integrations' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('integrations')]
        if 'service_type' in columns:
            op.drop_column('integrations', 'service_type')
    # No other changes needed
