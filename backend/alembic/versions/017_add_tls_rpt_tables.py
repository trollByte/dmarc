"""add tls-rpt tables

Revision ID: 017
Revises: 016
Create Date: 2026-01-10

Creates tables for TLS-RPT report storage.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create TLS-RPT tables"""

    # TLS reports table
    op.create_table(
        'tls_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('report_id', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('report_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('organization_name', sa.String(255), nullable=False),
        sa.Column('contact_info', sa.String(255), nullable=True),
        sa.Column('date_range_begin', sa.DateTime(), nullable=False, index=True),
        sa.Column('date_range_end', sa.DateTime(), nullable=False),
        sa.Column('policy_domain', sa.String(255), nullable=False, index=True),
        sa.Column('policy_type', sa.String(20), nullable=False),
        sa.Column('successful_session_count', sa.Integer(), default=0, nullable=False),
        sa.Column('failed_session_count', sa.Integer(), default=0, nullable=False),
        sa.Column('raw_report', JSONB, nullable=False),
        sa.Column('policies', JSONB, nullable=True),
        sa.Column('failure_details', JSONB, nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('source_ip', sa.String(45), nullable=True),
        sa.Column('filename', sa.String(255), nullable=True),
    )

    # TLS failure summaries table
    op.create_table(
        'tls_failure_summaries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('policy_domain', sa.String(255), nullable=False, index=True),
        sa.Column('result_type', sa.String(50), nullable=False, index=True),
        sa.Column('receiving_mx_hostname', sa.String(255), nullable=True),
        sa.Column('sending_mta_ip', sa.String(45), nullable=True),
        sa.Column('failure_count', sa.Integer(), default=0, nullable=False),
        sa.Column('report_count', sa.Integer(), default=0, nullable=False),
        sa.Column('first_seen', sa.DateTime(), nullable=False),
        sa.Column('last_seen', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    """Drop TLS-RPT tables"""
    op.drop_table('tls_failure_summaries')
    op.drop_table('tls_reports')
