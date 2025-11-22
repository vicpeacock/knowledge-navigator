"""add_purpose_to_integrations

Revision ID: 3fa60a542746
Revises: add_notification_indexes
Create Date: 2025-11-22 11:43:05.749588

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3fa60a542746'
down_revision: Union[str, None] = 'add_notification_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add purpose column as nullable initially
    op.add_column(
        'integrations',
        sa.Column('purpose', sa.String(50), nullable=True)
    )
    
    # Step 2: Migrate existing data
    # For integrations with user_id = NULL: set purpose = "service_{service_type}"
    # For integrations with user_id NOT NULL: set purpose = "user_{service_type}"
    # Exception: mcp_server always has purpose = "mcp_server" (regardless of user_id)
    op.execute("""
        UPDATE integrations
        SET purpose = CASE
            WHEN service_type = 'mcp_server' THEN 'mcp_server'
            WHEN user_id IS NULL THEN 'service_' || service_type
            ELSE 'user_' || service_type
        END
        WHERE purpose IS NULL
    """)
    
    # Step 3: Make purpose NOT NULL after migration
    op.alter_column('integrations', 'purpose', nullable=False)
    
    # Step 4: Add check constraint to ensure purpose is valid
    op.execute("""
        ALTER TABLE integrations
        ADD CONSTRAINT ck_integrations_purpose_valid
        CHECK (purpose IN ('user_email', 'service_email', 'user_calendar', 'service_calendar', 'user_whatsapp', 'service_whatsapp', 'mcp_server'))
    """)
    
    # Step 5: Add index for fast lookups by purpose
    op.create_index(
        'ix_integrations_purpose',
        'integrations',
        ['purpose'],
        unique=False
    )
    
    # Step 6: Add composite index for tenant_id + purpose + enabled (common query pattern)
    op.create_index(
        'ix_integrations_tenant_purpose_enabled',
        'integrations',
        ['tenant_id', 'purpose', 'enabled'],
        unique=False
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_integrations_tenant_purpose_enabled', table_name='integrations')
    op.drop_index('ix_integrations_purpose', table_name='integrations')
    
    # Drop check constraint
    op.execute("ALTER TABLE integrations DROP CONSTRAINT IF EXISTS ck_integrations_purpose_valid")
    
    # Drop purpose column
    op.drop_column('integrations', 'purpose')

