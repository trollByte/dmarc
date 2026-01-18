"""add saved views table

Revision ID: 022
Revises: 021
Create Date: 2026-01-17

Creates table for user saved views/filter combinations.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create saved views table"""

    op.create_table(
        'saved_views',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('filters', JSONB, nullable=False, server_default='{}'),
        sa.Column('display_settings', JSONB, nullable=True, server_default='{}'),
        sa.Column('is_shared', sa.Boolean(), default=False, nullable=False),
        sa.Column('is_default', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
    )

    # Index for finding shared views
    op.create_index(
        'ix_saved_views_shared',
        'saved_views',
        ['is_shared']
    )

    # Index for finding user's default view
    op.create_index(
        'ix_saved_views_user_default',
        'saved_views',
        ['user_id', 'is_default']
    )


def downgrade() -> None:
    """Drop saved views table"""
    op.drop_index('ix_saved_views_user_default', table_name='saved_views')
    op.drop_index('ix_saved_views_shared', table_name='saved_views')
    op.drop_table('saved_views')
