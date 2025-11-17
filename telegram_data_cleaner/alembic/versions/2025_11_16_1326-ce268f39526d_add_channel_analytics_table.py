"""add_channel_analytics_table

Revision ID: ce268f39526d
Revises: 74d7c0b1a1f0
Create Date: 2025-11-16 13:26:49.968162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce268f39526d'
down_revision: Union[str, None] = '74d7c0b1a1f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create channel_analytics table
    op.create_table(
        'channel_analytics',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('channel_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=True, comment='Hour of day (0-23) for hourly aggregates, NULL for daily'),
        sa.Column('day_of_week', sa.Integer(), nullable=False, comment='Day of week (0=Monday, 6=Sunday)'),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0', comment='Total number of messages'),
        sa.Column('match_count', sa.Integer(), nullable=False, server_default='0', comment='Total number of matched messages'),
        sa.Column('top_symbols', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Top 10 symbols mentioned"),
        sa.Column('top_industries', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Top 10 industries mentioned"),
        sa.Column('top_categories', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Top 10 dictionary categories"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_id', 'date', 'hour', name='uq_channel_date_hour')
    )

    # Create indexes
    op.create_index('idx_channel_analytics_channel_date', 'channel_analytics', ['channel_id', 'date'])
    op.create_index('idx_channel_analytics_date', 'channel_analytics', ['date'])
    op.create_index(op.f('ix_channel_analytics_channel_id'), 'channel_analytics', ['channel_id'])
    op.create_index(op.f('ix_channel_analytics_date'), 'channel_analytics', ['date'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_channel_analytics_date'), table_name='channel_analytics')
    op.drop_index(op.f('ix_channel_analytics_channel_id'), table_name='channel_analytics')
    op.drop_index('idx_channel_analytics_date', table_name='channel_analytics')
    op.drop_index('idx_channel_analytics_channel_date', table_name='channel_analytics')

    # Drop table
    op.drop_table('channel_analytics')
