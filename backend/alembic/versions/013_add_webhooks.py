"""add webhooks

Revision ID: 013
Revises: 012
Create Date: 2026-01-10

Creates tables for webhook management:
- webhook_endpoints: Configured webhook URLs
- webhook_deliveries: Delivery history and retry tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create webhook tables"""

    # webhook_endpoints table
    op.create_table(
        'webhook_endpoints',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('secret', sa.String(64), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), default=True, nullable=False, index=True),
        sa.Column('events', JSONB, nullable=False),
        sa.Column('max_retries', sa.Integer(), default=3, nullable=False),
        sa.Column('retry_interval_seconds', sa.Integer(), default=60, nullable=False),
        sa.Column('last_triggered_at', sa.DateTime(), nullable=True),
        sa.Column('success_count', sa.Integer(), default=0, nullable=False),
        sa.Column('failure_count', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )

    # webhook_deliveries table
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('endpoint_id', UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('payload', JSONB, nullable=False),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('attempt_number', sa.Integer(), default=1, nullable=False),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['endpoint_id'], ['webhook_endpoints.id'], ondelete='CASCADE')
    )

    # Index for pending retries
    op.create_index(
        'ix_webhook_deliveries_retry',
        'webhook_deliveries',
        ['next_retry_at'],
        postgresql_where=sa.text('next_retry_at IS NOT NULL AND success IS NULL')
    )


def downgrade() -> None:
    """Drop webhook tables"""
    op.drop_index('ix_webhook_deliveries_retry', table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')
    op.drop_table('webhook_endpoints')
