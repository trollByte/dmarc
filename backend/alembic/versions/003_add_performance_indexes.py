"""add performance indexes

Revision ID: 003
Revises: 002
Create Date: 2026-01-06 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for filtering reports by domain and date range
    op.create_index(
        'ix_dmarc_reports_domain_dates',
        'dmarc_reports',
        ['domain', 'date_begin', 'date_end'],
        unique=False
    )

    # Composite index for grouping records by source_ip with pass/fail
    op.create_index(
        'ix_dmarc_records_source_dkim_spf',
        'dmarc_records',
        ['source_ip', 'dkim_result', 'spf_result'],
        unique=False
    )

    # Index for aggregating by report_id and count
    op.create_index(
        'ix_dmarc_records_report_count',
        'dmarc_records',
        ['report_id', 'count'],
        unique=False
    )

    # Index for filtering by disposition
    op.create_index(
        'ix_dmarc_records_disposition',
        'dmarc_records',
        ['disposition'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_dmarc_records_disposition', table_name='dmarc_records')
    op.drop_index('ix_dmarc_records_report_count', table_name='dmarc_records')
    op.drop_index('ix_dmarc_records_source_dkim_spf', table_name='dmarc_records')
    op.drop_index('ix_dmarc_reports_domain_dates', table_name='dmarc_reports')
