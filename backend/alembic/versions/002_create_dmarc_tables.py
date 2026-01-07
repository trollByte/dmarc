"""create dmarc tables

Revision ID: 002
Revises: 001
Create Date: 2026-01-06 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dmarc_reports table
    op.create_table(
        'dmarc_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ingested_report_id', sa.Integer(), nullable=True),
        sa.Column('report_id', sa.String(length=500), nullable=False),
        sa.Column('org_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('extra_contact_info', sa.String(length=500), nullable=True),
        sa.Column('date_begin', sa.DateTime(), nullable=False),
        sa.Column('date_end', sa.DateTime(), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('adkim', sa.String(length=20), nullable=True),
        sa.Column('aspf', sa.String(length=20), nullable=True),
        sa.Column('p', sa.String(length=20), nullable=False),
        sa.Column('sp', sa.String(length=20), nullable=True),
        sa.Column('pct', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['ingested_report_id'], ['ingested_reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_dmarc_reports_date_begin', 'dmarc_reports', ['date_begin'], unique=False)
    op.create_index('ix_dmarc_reports_date_end', 'dmarc_reports', ['date_end'], unique=False)
    op.create_index('ix_dmarc_reports_domain', 'dmarc_reports', ['domain'], unique=False)
    op.create_index('ix_dmarc_reports_id', 'dmarc_reports', ['id'], unique=False)
    op.create_index('ix_dmarc_reports_org_name', 'dmarc_reports', ['org_name'], unique=False)
    op.create_index('ix_dmarc_reports_report_id', 'dmarc_reports', ['report_id'], unique=True)

    # Create dmarc_records table
    op.create_table(
        'dmarc_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.Integer(), nullable=False),
        sa.Column('source_ip', sa.String(length=45), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('disposition', sa.String(length=20), nullable=True),
        sa.Column('dkim', sa.String(length=20), nullable=True),
        sa.Column('spf', sa.String(length=20), nullable=True),
        sa.Column('header_from', sa.String(length=255), nullable=True),
        sa.Column('envelope_from', sa.String(length=255), nullable=True),
        sa.Column('envelope_to', sa.String(length=255), nullable=True),
        sa.Column('dkim_domain', sa.String(length=255), nullable=True),
        sa.Column('dkim_result', sa.String(length=20), nullable=True),
        sa.Column('dkim_selector', sa.String(length=255), nullable=True),
        sa.Column('spf_domain', sa.String(length=255), nullable=True),
        sa.Column('spf_result', sa.String(length=20), nullable=True),
        sa.Column('spf_scope', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['dmarc_reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_dmarc_records_id', 'dmarc_records', ['id'], unique=False)
    op.create_index('ix_dmarc_records_source_ip', 'dmarc_records', ['source_ip'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_dmarc_records_source_ip', table_name='dmarc_records')
    op.drop_index('ix_dmarc_records_id', table_name='dmarc_records')
    op.drop_table('dmarc_records')
    op.drop_index('ix_dmarc_reports_report_id', table_name='dmarc_reports')
    op.drop_index('ix_dmarc_reports_org_name', table_name='dmarc_reports')
    op.drop_index('ix_dmarc_reports_id', table_name='dmarc_reports')
    op.drop_index('ix_dmarc_reports_domain', table_name='dmarc_reports')
    op.drop_index('ix_dmarc_reports_date_end', table_name='dmarc_reports')
    op.drop_index('ix_dmarc_reports_date_begin', table_name='dmarc_reports')
    op.drop_table('dmarc_reports')
