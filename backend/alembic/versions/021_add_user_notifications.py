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

    # User notifications table
    # Use raw SQL to avoid SQLAlchemy enum creation conflicts with model metadata
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notification_type AS ENUM (
                'info', 'success', 'warning', 'error', 'alert'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notification_category AS ENUM (
                'system', 'report', 'alert', 'security', 'policy'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_notifications (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            notification_type notification_type NOT NULL DEFAULT 'info',
            category notification_category NOT NULL DEFAULT 'system',
            link VARCHAR(500),
            link_text VARCHAR(100),
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            read_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_notifications_user_id ON user_notifications(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_notifications_is_read ON user_notifications(is_read)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_notifications_created_at ON user_notifications(created_at)")

    # Create compound index for efficient queries
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_notifications_user_unread ON user_notifications(user_id, is_read, created_at)")


def downgrade() -> None:
    """Drop user notifications table"""
    op.drop_index('ix_user_notifications_user_unread', table_name='user_notifications')
    op.drop_table('user_notifications')
    op.execute("DROP TYPE notification_category")
    op.execute("DROP TYPE notification_type")
