"""add scheduled reports tables

Revision ID: 019
Revises: 018
Create Date: 2026-01-10

Creates tables for scheduled report generation.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


# revision identifiers, used by Alembic
revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create scheduled reports tables"""

    # Scheduled reports configuration
    op.create_table(
        'scheduled_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('frequency', sa.String(20), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=True),
        sa.Column('day_of_month', sa.Integer(), nullable=True),
        sa.Column('hour', sa.Integer(), default=8, nullable=False),
        sa.Column('timezone', sa.String(50), default='UTC', nullable=False),
        sa.Column('report_type', sa.String(30), nullable=False),
        sa.Column('domains', ARRAY(sa.String), nullable=True),
        sa.Column('date_range_days', sa.Integer(), default=7, nullable=False),
        sa.Column('include_charts', sa.Boolean(), default=True, nullable=False),
        sa.Column('include_recommendations', sa.Boolean(), default=True, nullable=False),
        sa.Column('report_format', sa.String(10), default='pdf', nullable=False),
        sa.Column('recipients', ARRAY(sa.String), nullable=False),
        sa.Column('email_subject', sa.String(255), nullable=True),
        sa.Column('email_body', sa.Text(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('run_count', sa.Integer(), default=0, nullable=False),
        sa.Column('failure_count', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # Report delivery logs
    op.create_table(
        'report_delivery_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('scheduled_report_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('report_type', sa.String(30), nullable=False),
        sa.Column('date_range_start', sa.DateTime(), nullable=False),
        sa.Column('date_range_end', sa.DateTime(), nullable=False),
        sa.Column('domains_included', ARRAY(sa.String), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('generation_time_ms', sa.Integer(), nullable=True),
        sa.Column('recipients', ARRAY(sa.String), nullable=False),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )

    # Index for finding due schedules
    op.create_index(
        'ix_scheduled_reports_next_run',
        'scheduled_reports',
        ['next_run_at'],
        postgresql_where=sa.text('is_active = true')
    )


def downgrade() -> None:
    """Drop scheduled reports tables"""
    op.drop_index('ix_scheduled_reports_next_run', table_name='scheduled_reports')
    op.drop_table('report_delivery_logs')
    op.drop_table('scheduled_reports')
