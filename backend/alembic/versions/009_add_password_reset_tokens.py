"""add password reset tokens

Revision ID: 009
Revises: 008
Create Date: 2026-01-10

Creates table for self-service password reset:
- password_reset_tokens: Secure token storage for password recovery
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create password reset tokens table"""

    op.create_table(
        'password_reset_tokens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('used', sa.Boolean(), default=False, nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('request_ip', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )

    # Index for cleanup queries
    op.create_index(
        'ix_password_reset_tokens_user_expires',
        'password_reset_tokens',
        ['user_id', 'expires_at']
    )


def downgrade() -> None:
    """Drop password reset tokens table"""
    op.drop_index('ix_password_reset_tokens_user_expires', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
