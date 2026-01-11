"""add mta-sts monitoring tables

Revision ID: 016
Revises: 015
Create Date: 2026-01-10

Creates tables for MTA-STS monitoring.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create MTA-STS monitoring tables"""

    # MTA-STS monitors table
    op.create_table(
        'mta_sts_monitors',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('domain', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_status', sa.String(20), nullable=True),
        sa.Column('last_mode', sa.String(20), nullable=True),
        sa.Column('last_policy_id', sa.String(100), nullable=True),
        sa.Column('last_policy_hash', sa.String(64), nullable=True),
        sa.Column('last_max_age', sa.Integer(), nullable=True),
        sa.Column('last_mx_hosts', sa.Text(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('last_change_at', sa.DateTime(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # MTA-STS change logs table
    op.create_table(
        'mta_sts_change_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('domain', sa.String(255), nullable=False, index=True),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('details', JSONB, nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    """Drop MTA-STS monitoring tables"""
    op.drop_table('mta_sts_change_logs')
    op.drop_table('mta_sts_monitors')
