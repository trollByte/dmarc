"""add bimi tables

Revision ID: 018
Revises: 017
Create Date: 2026-01-10

Creates tables for BIMI monitoring.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create BIMI tables"""

    # BIMI domains table
    op.create_table(
        'bimi_domains',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('domain', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('has_bimi_record', sa.Boolean(), default=False, nullable=False),
        sa.Column('logo_url', sa.Text(), nullable=True),
        sa.Column('authority_url', sa.Text(), nullable=True),
        sa.Column('last_status', sa.String(20), nullable=True),
        sa.Column('dmarc_compliant', sa.Boolean(), default=False, nullable=False),
        sa.Column('logo_valid', sa.Boolean(), default=False, nullable=False),
        sa.Column('vmc_valid', sa.Boolean(), nullable=True),
        sa.Column('logo_hash', sa.String(64), nullable=True),
        sa.Column('logo_cached_at', sa.DateTime(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('last_change_at', sa.DateTime(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # BIMI change logs table
    op.create_table(
        'bimi_change_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('domain', sa.String(255), nullable=False, index=True),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('details', JSONB, nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    """Drop BIMI tables"""
    op.drop_table('bimi_change_logs')
    op.drop_table('bimi_domains')
