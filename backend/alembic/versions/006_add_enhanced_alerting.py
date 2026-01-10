"""add enhanced alerting

Revision ID: 006
Revises: 005
Create Date: 2026-01-09

Creates tables for enhanced alerting with persistence:
- alert_history: Persistent alert records with lifecycle tracking
- alert_rules: Configurable alert rules with thresholds
- alert_suppressions: Time-based alert suppression rules
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create enhanced alerting tables"""

    # alert_history table - use String for enum-like columns
    op.create_table(
        'alert_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('alert_type', sa.String(50), nullable=False, index=True),
        sa.Column('severity', sa.String(20), nullable=False, index=True),
        sa.Column('fingerprint', sa.String(64), nullable=False, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('domain', sa.String(255), nullable=True, index=True),
        sa.Column('current_value', sa.Float(), nullable=True),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('alert_metadata', JSONB, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by', UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', UUID(as_uuid=True), nullable=True),
        sa.Column('acknowledgement_note', sa.Text(), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), default=False, nullable=False),
        sa.Column('notification_sent_at', sa.DateTime(), nullable=True),
        sa.Column('notification_channels', JSONB, nullable=True),
        sa.Column('cooldown_until', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['acknowledged_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL')
    )

    # alert_rules table
    op.create_table(
        'alert_rules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('alert_type', sa.String(50), nullable=False, index=True),
        sa.Column('is_enabled', sa.Boolean(), default=True, nullable=False, index=True),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('conditions', JSONB, nullable=False),
        sa.Column('domain_pattern', sa.String(255), nullable=True),
        sa.Column('cooldown_minutes', sa.Integer(), default=60, nullable=False),
        sa.Column('notify_email', sa.Boolean(), default=True, nullable=False),
        sa.Column('notify_teams', sa.Boolean(), default=True, nullable=False),
        sa.Column('notify_slack', sa.Boolean(), default=False, nullable=False),
        sa.Column('notify_webhook', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )

    # alert_suppressions table
    op.create_table(
        'alert_suppressions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False, index=True),
        sa.Column('alert_type', sa.String(50), nullable=True, index=True),
        sa.Column('severity', sa.String(20), nullable=True, index=True),
        sa.Column('domain', sa.String(255), nullable=True, index=True),
        sa.Column('starts_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('ends_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('recurrence', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )

    # Additional indexes for performance
    op.create_index('ix_alert_history_fingerprint_created', 'alert_history', ['fingerprint', 'created_at'])
    op.create_index('ix_alert_rules_type_enabled', 'alert_rules', ['alert_type', 'is_enabled'])


def downgrade() -> None:
    """Drop enhanced alerting tables"""
    # Drop indexes
    op.drop_index('ix_alert_rules_type_enabled', table_name='alert_rules')
    op.drop_index('ix_alert_history_fingerprint_created', table_name='alert_history')

    # Drop tables
    op.drop_table('alert_suppressions')
    op.drop_table('alert_rules')
    op.drop_table('alert_history')
