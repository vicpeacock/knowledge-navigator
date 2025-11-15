"""Add API keys table for tenant authentication

Revision ID: 0e1f99366975
Revises: add_tenant_id_to_tables
Create Date: 2025-01-XX 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0e1f99366975'
down_revision = 'add_tenant_id_to_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_api_keys_tenant_id'),
    )
    op.create_unique_constraint('uq_api_keys_key_hash', 'api_keys', ['key_hash'])
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])
    op.create_index('ix_api_keys_tenant_id', 'api_keys', ['tenant_id'])


def downgrade():
    op.drop_index('ix_api_keys_tenant_id', table_name='api_keys')
    op.drop_index('ix_api_keys_key_hash', table_name='api_keys')
    op.drop_constraint('uq_api_keys_key_hash', 'api_keys', type_='unique')
    op.drop_constraint('fk_api_keys_tenant_id', 'api_keys', type_='foreignkey')
    op.drop_table('api_keys')
