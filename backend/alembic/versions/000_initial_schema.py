"""Initial database schema

Revision ID: 000_initial_schema
Revises: 
Create Date: 2025-11-23 22:50:00.000000

Creates all base tables: sessions, messages, files, integrations, memory_short, memory_medium, memory_long

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '000_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('metadata', postgresql.JSONB, default={}),
    )
    
    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('metadata', postgresql.JSONB, default={}),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], name='fk_messages_session_id'),
    )
    
    # Create files table
    op.create_table(
        'files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('filepath', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('metadata', postgresql.JSONB, default={}),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], name='fk_files_session_id'),
    )
    
    # Create integrations table
    op.create_table(
        'integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('service_type', sa.String(50), nullable=False),
        sa.Column('credentials_encrypted', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), default=True, nullable=True),
        sa.Column('metadata', postgresql.JSONB, default={}),
    )
    
    # Create memory_short table
    op.create_table(
        'memory_short',
        sa.Column('session_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('context_data', postgresql.JSONB, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], name='fk_memory_short_session_id'),
    )
    
    # Create memory_medium table
    op.create_table(
        'memory_medium',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], name='fk_memory_medium_session_id'),
    )
    
    # Create memory_long table
    op.create_table(
        'memory_long',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding_id', sa.String(255), nullable=True),
        sa.Column('learned_from_sessions', postgresql.JSONB, default=[]),
        sa.Column('importance_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Create indexes
    op.create_index('ix_messages_session_id', 'messages', ['session_id'])
    op.create_index('ix_files_session_id', 'files', ['session_id'])


def downgrade():
    op.drop_table('memory_long')
    op.drop_table('memory_medium')
    op.drop_table('memory_short')
    op.drop_table('integrations')
    op.drop_table('files')
    op.drop_table('messages')
    op.drop_table('sessions')

