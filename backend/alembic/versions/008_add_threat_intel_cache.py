"""Add threat intelligence cache table

Revision ID: 008
Revises: 007
Create Date: 2026-01-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'threat_intel_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ip_address', sa.String(45), nullable=False, unique=True, index=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('threat_level', sa.String(20), nullable=False),
        sa.Column('abuse_score', sa.Integer(), default=0),
        sa.Column('total_reports', sa.Integer(), default=0),
        sa.Column('last_reported', sa.DateTime(), nullable=True),
        sa.Column('is_whitelisted', sa.Integer(), default=0),
        sa.Column('is_tor', sa.Integer(), default=0),
        sa.Column('isp', sa.String(255), nullable=True),
        sa.Column('domain', sa.String(255), nullable=True),
        sa.Column('country_code', sa.String(10), nullable=True),
        sa.Column('usage_type', sa.String(100), nullable=True),
        sa.Column('categories', postgresql.JSON(), default=list),
        sa.Column('raw_response', postgresql.JSON(), default=dict),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
    )

    # Index for expiry queries
    op.create_index(
        'ix_threat_intel_cache_expires_at',
        'threat_intel_cache',
        ['expires_at']
    )

    # Index for threat level queries
    op.create_index(
        'ix_threat_intel_cache_threat_level',
        'threat_intel_cache',
        ['threat_level']
    )


def downgrade() -> None:
    op.drop_index('ix_threat_intel_cache_threat_level')
    op.drop_index('ix_threat_intel_cache_expires_at')
    op.drop_table('threat_intel_cache')
