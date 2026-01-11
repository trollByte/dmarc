"""add retention policies

Revision ID: 012
Revises: 011
Create Date: 2026-01-10

Creates tables for data retention management:
- retention_policies: Configurable retention rules
- retention_logs: Execution history
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create retention policy tables"""

    # retention_policies table
    op.create_table(
        'retention_policies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('target', sa.String(50), nullable=False, index=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('retention_days', sa.Integer(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), default=True, nullable=False),
        sa.Column('filters', JSONB, nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_run_deleted', sa.Integer(), nullable=True),
        sa.Column('total_deleted', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )

    # retention_logs table
    op.create_table(
        'retention_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('policy_id', UUID(as_uuid=True), nullable=True),
        sa.Column('policy_name', sa.String(100), nullable=False),
        sa.Column('target', sa.String(50), nullable=False),
        sa.Column('retention_days', sa.Integer(), nullable=False),
        sa.Column('records_deleted', sa.Integer(), nullable=False),
        sa.Column('cutoff_date', sa.DateTime(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['policy_id'], ['retention_policies.id'], ondelete='SET NULL')
    )

    # Index for log queries
    op.create_index(
        'ix_retention_logs_policy_executed',
        'retention_logs',
        ['policy_id', 'executed_at']
    )


def downgrade() -> None:
    """Drop retention policy tables"""
    op.drop_index('ix_retention_logs_policy_executed', table_name='retention_logs')
    op.drop_table('retention_logs')
    op.drop_table('retention_policies')
