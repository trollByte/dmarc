"""add virustotal cache

Revision ID: 014
Revises: 013
Create Date: 2026-01-10

Creates cache table for VirusTotal lookups.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create VirusTotal cache table"""

    op.create_table(
        'virustotal_cache',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('lookup_type', sa.String(20), nullable=False, index=True),
        sa.Column('lookup_value', sa.String(255), nullable=False, index=True),
        sa.Column('lookup_hash', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('malicious_count', sa.Integer(), default=0, nullable=False),
        sa.Column('suspicious_count', sa.Integer(), default=0, nullable=False),
        sa.Column('reputation_score', sa.Integer(), nullable=True),
        sa.Column('result_data', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    """Drop VirusTotal cache table"""
    op.drop_table('virustotal_cache')
