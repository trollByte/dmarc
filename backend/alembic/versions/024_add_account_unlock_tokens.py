"""Add account unlock tokens table

Revision ID: 024_unlock_tokens
Revises: 023_perf_indexes
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '024_unlock_tokens'
down_revision = '023_perf_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add account_unlock_tokens table for self-service account recovery."""

    op.create_table(
        'account_unlock_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), default=False, nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('request_ip', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Add indexes for performance
    op.create_index('ix_account_unlock_tokens_token_hash', 'account_unlock_tokens', ['token_hash'])
    op.create_index('ix_account_unlock_tokens_expires_at', 'account_unlock_tokens', ['expires_at'])
    op.create_index('ix_account_unlock_tokens_user_id', 'account_unlock_tokens', ['user_id'])


def downgrade() -> None:
    """Remove account_unlock_tokens table."""

    op.drop_index('ix_account_unlock_tokens_user_id', table_name='account_unlock_tokens')
    op.drop_index('ix_account_unlock_tokens_expires_at', table_name='account_unlock_tokens')
    op.drop_index('ix_account_unlock_tokens_token_hash', table_name='account_unlock_tokens')
    op.drop_table('account_unlock_tokens')
