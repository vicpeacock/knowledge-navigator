"""Add notifications table

Revision ID: add_notifications
Revises: a39125eacc42
Create Date: 2025-11-07 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_notifications'
down_revision = '234e8f042523'  # Latest migration
branch_labels = None
depends_on = None


def upgrade():
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('urgency', sa.String(20), nullable=False),
        sa.Column('content', postgresql.JSONB, nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('read', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
    )
    
    # Create index on session_id for faster queries
    op.create_index('ix_notifications_session_id', 'notifications', ['session_id'])
    op.create_index('ix_notifications_read', 'notifications', ['read'])
    op.create_index('ix_notifications_urgency', 'notifications', ['urgency'])


def downgrade():
    op.drop_index('ix_notifications_urgency', table_name='notifications')
    op.drop_index('ix_notifications_read', table_name='notifications')
    op.drop_index('ix_notifications_session_id', table_name='notifications')
    op.drop_table('notifications')

