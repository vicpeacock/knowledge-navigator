"""Add indexes for notifications table

Revision ID: add_notification_indexes
Revises: 4d2ea1f98574
Create Date: 2025-11-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_notification_indexes'
down_revision = '4d2ea1f98574'  # Latest migration (add_user_timezone_and_inactivity_timeout)
branch_labels = None
depends_on = None


def upgrade():
    # Add composite index for tenant_id + read + created_at (most common query pattern)
    op.create_index(
        'ix_notifications_tenant_read_created',
        'notifications',
        ['tenant_id', 'read', 'created_at'],
        postgresql_ops={'created_at': 'DESC'}
    )
    
    # Add index for tenant_id + type (for filtering by type)
    op.create_index(
        'ix_notifications_tenant_type',
        'notifications',
        ['tenant_id', 'type']
    )
    
    # Add index for tenant_id + urgency (for filtering by urgency)
    op.create_index(
        'ix_notifications_tenant_urgency',
        'notifications',
        ['tenant_id', 'urgency']
    )
    
    # Add index for session_id (already exists but ensure it's there)
    # This is for filtering notifications by session
    if not op.get_bind().execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_notifications_session_id'")
    ).scalar():
        op.create_index('ix_notifications_session_id', 'notifications', ['session_id'])
    
    # Add GIN index for content JSONB field (for efficient JSON queries)
    op.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_notifications_content_gin ON notifications USING GIN (content)")
    )
    
    # Add index for tenant_id + read (for counting unread notifications)
    op.create_index(
        'ix_notifications_tenant_read',
        'notifications',
        ['tenant_id', 'read']
    )


def downgrade():
    op.drop_index('ix_notifications_tenant_read', table_name='notifications')
    op.execute(sa.text("DROP INDEX IF EXISTS ix_notifications_content_gin"))
    op.drop_index('ix_notifications_tenant_urgency', table_name='notifications')
    op.drop_index('ix_notifications_tenant_type', table_name='notifications')
    op.drop_index('ix_notifications_tenant_read_created', table_name='notifications')

