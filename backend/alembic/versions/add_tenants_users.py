"""Add tenants and users tables for multi-tenancy

Revision ID: add_tenants_users
Revises: add_notifications
Create Date: 2025-01-XX 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = 'add_tenants_users'
down_revision = 'add_notifications'
branch_labels = None
depends_on = None


def upgrade():
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('schema_name', sa.String(63), nullable=False),
        sa.Column('active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('metadata', postgresql.JSONB, default={}),
    )
    op.create_unique_constraint('uq_tenants_name', 'tenants', ['name'])
    op.create_unique_constraint('uq_tenants_schema', 'tenants', ['schema_name'])
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('metadata', postgresql.JSONB, default={}),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_users_tenant_id'),
    )
    op.create_unique_constraint('uq_user_tenant_email', 'users', ['tenant_id', 'email'])
    
    # Create indexes for performance
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('ix_users_email', 'users', ['email'])
    
    # Create default tenant for backward compatibility
    default_tenant_id = str(uuid.uuid4())
    op.execute(
        sa.text(f"""
            INSERT INTO tenants (id, name, schema_name, active, metadata)
            VALUES ('{default_tenant_id}', 'Default Tenant', 'tenant_default', true, '{{}}')
        """)
    )


def downgrade():
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_tenant_id', table_name='users')
    op.drop_constraint('uq_user_tenant_email', 'users', type_='unique')
    op.drop_table('users')
    op.drop_constraint('uq_tenants_schema', 'tenants', type_='unique')
    op.drop_constraint('uq_tenants_name', 'tenants', type_='unique')
    op.drop_table('tenants')

