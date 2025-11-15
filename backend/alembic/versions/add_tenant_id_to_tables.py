"""Add tenant_id to all existing tables for multi-tenancy

Revision ID: add_tenant_id_to_tables
Revises: add_tenants_users
Create Date: 2025-01-XX 10:00:00.000000

IMPORTANT: This migration is backward compatible.
- Step 1: Add tenant_id column (nullable) to all tables
- Step 2: Assign default tenant to all existing data
- Step 3: Make tenant_id NOT NULL
- Step 4: Add foreign keys and indexes

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_tenant_id_to_tables'
down_revision = 'add_tenants_users'
branch_labels = None
depends_on = None


def upgrade():
    # Tables that need tenant_id (regular tables)
    tables = [
        'sessions',
        'messages',
        'files',
        'memory_medium',
        'memory_long',
        'integrations',
        'notifications',
    ]
    
    # Step 1: Add tenant_id column (nullable) to all regular tables
    for table in tables:
        op.add_column(
            table,
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True)
        )
    
    # Step 1b: Handle memory_short separately (has composite primary key)
    # First, drop the existing primary key constraint
    op.drop_constraint('memory_short_pkey', 'memory_short', type_='primary')
    # Add tenant_id column (nullable for now)
    op.add_column(
        'memory_short',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Step 2 & 3: Assign default tenant to all existing data
    # Use subquery to get default tenant ID (works in both online and offline mode)
    for table in tables:
        op.execute(
            sa.text(f"""
                UPDATE {table} 
                SET tenant_id = (SELECT id FROM tenants WHERE schema_name = 'tenant_default' LIMIT 1)
                WHERE tenant_id IS NULL
            """)
        )
    # Also update memory_short
    op.execute(
        sa.text("""
            UPDATE memory_short 
            SET tenant_id = (SELECT id FROM tenants WHERE schema_name = 'tenant_default' LIMIT 1)
            WHERE tenant_id IS NULL
        """)
    )
    
    # Step 4: Make tenant_id NOT NULL
    for table in tables:
        op.alter_column(table, 'tenant_id', nullable=False)
    op.alter_column('memory_short', 'tenant_id', nullable=False)
    
    # Step 4b: Now create composite primary key for memory_short (after tenant_id is NOT NULL)
    op.create_primary_key('memory_short_pkey', 'memory_short', ['tenant_id', 'session_id'])
    
    # Step 5: Add foreign keys
    for table in tables:
        op.create_foreign_key(
            f'fk_{table}_tenant_id',
            table, 'tenants',
            ['tenant_id'], ['id']
        )
    op.create_foreign_key(
        'fk_memory_short_tenant_id',
        'memory_short', 'tenants',
        ['tenant_id'], ['id']
    )
    
    # Step 6: Add indexes for performance
    for table in tables:
        op.create_index(f'ix_{table}_tenant_id', table, ['tenant_id'])
    op.create_index('ix_memory_short_tenant_id', 'memory_short', ['tenant_id'])


def downgrade():
    # Tables that have tenant_id
    tables = [
        'sessions',
        'messages',
        'files',
        'memory_medium',
        'memory_long',
        'integrations',
        'notifications',
    ]
    
    # Remove indexes
    for table in tables:
        op.drop_index(f'ix_{table}_tenant_id', table_name=table)
    op.drop_index('ix_memory_short_tenant_id', table_name='memory_short')
    
    # Remove foreign keys
    for table in tables:
        op.drop_constraint(f'fk_{table}_tenant_id', table, type_='foreignkey')
    op.drop_constraint('fk_memory_short_tenant_id', 'memory_short', type_='foreignkey')
    
    # Remove tenant_id column
    for table in tables:
        op.drop_column(table, 'tenant_id')
    
    # Handle memory_short: drop composite primary key, remove tenant_id, recreate single primary key
    op.drop_constraint('memory_short_pkey', 'memory_short', type_='primary')
    op.drop_column('memory_short', 'tenant_id')
    op.create_primary_key('memory_short_pkey', 'memory_short', ['session_id'])

