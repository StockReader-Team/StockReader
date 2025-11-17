"""add_sync_state_table

Revision ID: 3f4e2a601607
Revises: ce268f39526d
Create Date: 2025-11-16 15:47:50.670044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3f4e2a601607'
down_revision: Union[str, None] = 'ce268f39526d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sync_states table
    op.create_table('sync_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('direction', sa.String(length=20), nullable=False),
        sa.Column('current_offset', sa.Integer(), nullable=False),
        sa.Column('total_available', sa.Integer(), nullable=True),
        sa.Column('messages_synced', sa.Integer(), nullable=False),
        sa.Column('is_running', sa.Boolean(), nullable=False),
        sa.Column('is_completed', sa.Boolean(), nullable=False),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sync_states_direction'), 'sync_states', ['direction'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # Drop sync_states table
    op.drop_index(op.f('ix_sync_states_direction'), table_name='sync_states')
    op.drop_table('sync_states')
    # ### end Alembic commands ###
