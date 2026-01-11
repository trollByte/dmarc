"""add dns monitoring tables

Revision ID: 015
Revises: 014
Create Date: 2026-01-10

Creates tables for DNS change monitoring.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create DNS monitoring tables"""

    # Monitored domains table
    op.create_table(
        'monitored_domains',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('domain', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('monitor_dmarc', sa.Boolean(), default=True, nullable=False),
        sa.Column('monitor_spf', sa.Boolean(), default=True, nullable=False),
        sa.Column('monitor_dkim', sa.Boolean(), default=False, nullable=False),
        sa.Column('monitor_mx', sa.Boolean(), default=False, nullable=False),
        sa.Column('dkim_selectors', sa.String(500), nullable=True),
        sa.Column('last_dmarc_hash', sa.String(64), nullable=True),
        sa.Column('last_spf_hash', sa.String(64), nullable=True),
        sa.Column('last_dkim_hash', sa.String(64), nullable=True),
        sa.Column('last_mx_hash', sa.String(64), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # DNS change logs table
    op.create_table(
        'dns_change_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('domain', sa.String(255), nullable=False, index=True),
        sa.Column('record_type', sa.String(20), nullable=False, index=True),
        sa.Column('change_type', sa.String(20), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('alert_sent', sa.Boolean(), default=False, nullable=False),
        sa.Column('acknowledged', sa.Boolean(), default=False, nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    """Drop DNS monitoring tables"""
    op.drop_table('dns_change_logs')
    op.drop_table('monitored_domains')
