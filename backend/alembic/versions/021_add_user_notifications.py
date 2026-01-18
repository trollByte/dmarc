"""add user notifications table

Revision ID: 021
Revises: 020
Create Date: 2026-01-17

Creates table for user notifications in the notification center.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic
revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user notifications table"""

    # Create notification type enum
    op.execute("""
        CREATE TYPE notification_type AS ENUM (
            'info', 'success', 'warning', 'error', 'alert'
        )
    """)

    # Create notification category enum
    op.execute("""
        CREATE TYPE notification_category AS ENUM (
            'system', 'report', 'alert', 'security', 'policy'
        )
    """)

    # User notifications table
    op.create_table(
        'user_notifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('notification_type', sa.Enum('info', 'success', 'warning', 'error', 'alert', name='notification_type'), default='info', nullable=False),
        sa.Column('category', sa.Enum('system', 'report', 'alert', 'security', 'policy', name='notification_category'), default='system', nullable=False),
        sa.Column('link', sa.String(500), nullable=True),
        sa.Column('link_text', sa.String(100), nullable=True),
        sa.Column('is_read', sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
    )

    # Create compound index for efficient queries
    op.create_index(
        'ix_user_notifications_user_unread',
        'user_notifications',
        ['user_id', 'is_read', 'created_at']
    )


def downgrade() -> None:
    """Drop user notifications table"""
    op.drop_index('ix_user_notifications_user_unread', table_name='user_notifications')
    op.drop_table('user_notifications')
    op.execute("DROP TYPE notification_category")
    op.execute("DROP TYPE notification_type")
