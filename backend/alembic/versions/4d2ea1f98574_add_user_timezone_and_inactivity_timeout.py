"""add_user_timezone_and_inactivity_timeout

Revision ID: 4d2ea1f98574
Revises: 7f3b2c1a9b01
Create Date: 2025-11-18 22:41:25.155284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d2ea1f98574'
down_revision: Union[str, None] = '7f3b2c1a9b01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user preferences fields
    op.add_column('users', sa.Column('timezone', sa.String(50), nullable=True, server_default='UTC'))
    op.add_column('users', sa.Column('inactivity_timeout_minutes', sa.Integer(), nullable=True, server_default='30'))


def downgrade() -> None:
    # Remove user preferences fields
    op.drop_column('users', 'inactivity_timeout_minutes')
    op.drop_column('users', 'timezone')

