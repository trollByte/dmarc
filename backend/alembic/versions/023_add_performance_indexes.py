"""Add performance indexes for common query patterns

Revision ID: 023_perf_indexes
Revises: 022
Create Date: 2024-01-18

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '023_perf_indexes'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add indexes to optimize common query patterns."""

    # Reports table indexes
    # Index for date range queries (very common for dashboard)
    op.create_index(
        'ix_reports_date_range',
        'reports',
        ['date_begin', 'date_end'],
        if_not_exists=True
    )

    # Index for filtering by domain (common filter)
    op.create_index(
        'ix_reports_header_from',
        'reports',
        ['header_from'],
        if_not_exists=True
    )

    # Composite index for common dashboard queries
    op.create_index(
        'ix_reports_org_date',
        'reports',
        ['org_name', 'date_begin'],
        if_not_exists=True
    )

    # Index for report lookup by external ID
    op.create_index(
        'ix_reports_external_id',
        'reports',
        ['report_id'],
        unique=True,
        if_not_exists=True
    )

    # Records table indexes
    # Composite index for DMARC results analysis
    op.create_index(
        'ix_records_dmarc_results',
        'records',
        ['dkim_result', 'spf_result'],
        if_not_exists=True
    )

    # Index for source IP analysis
    op.create_index(
        'ix_records_source_ip',
        'records',
        ['source_ip'],
        if_not_exists=True
    )

    # Index for policy evaluation results
    op.create_index(
        'ix_records_policy_eval',
        'records',
        ['disposition'],
        if_not_exists=True
    )

    # Composite index for report-record queries with results
    op.create_index(
        'ix_records_report_results',
        'records',
        ['report_id', 'dkim_result', 'spf_result'],
        if_not_exists=True
    )

    # User notifications indexes
    op.create_index(
        'ix_notifications_user_unread',
        'user_notifications',
        ['user_id', 'is_read'],
        if_not_exists=True
    )

    op.create_index(
        'ix_notifications_user_created',
        'user_notifications',
        ['user_id', 'created_at'],
        if_not_exists=True
    )

    # Expiration cleanup index
    op.create_index(
        'ix_notifications_expires',
        'user_notifications',
        ['expires_at'],
        if_not_exists=True,
        postgresql_where=sa.text('expires_at IS NOT NULL')
    )

    # User saved views indexes
    op.create_index(
        'ix_saved_views_user',
        'user_saved_views',
        ['user_id', 'is_default'],
        if_not_exists=True
    )

    # Audit log indexes
    op.create_index(
        'ix_audit_logs_user_time',
        'audit_logs',
        ['user_id', 'created_at'],
        if_not_exists=True
    )

    op.create_index(
        'ix_audit_logs_action',
        'audit_logs',
        ['action', 'created_at'],
        if_not_exists=True
    )

    # API keys index
    op.create_index(
        'ix_api_keys_user_active',
        'api_keys',
        ['user_id', 'is_active'],
        if_not_exists=True
    )

    # Sessions index for cleanup
    op.create_index(
        'ix_sessions_expires',
        'sessions',
        ['expires_at'],
        if_not_exists=True
    )

    op.create_index(
        'ix_sessions_user',
        'sessions',
        ['user_id', 'is_active'],
        if_not_exists=True
    )


def downgrade() -> None:
    """Remove performance indexes."""

    # Reports indexes
    op.drop_index('ix_reports_date_range', table_name='reports', if_exists=True)
    op.drop_index('ix_reports_header_from', table_name='reports', if_exists=True)
    op.drop_index('ix_reports_org_date', table_name='reports', if_exists=True)
    op.drop_index('ix_reports_external_id', table_name='reports', if_exists=True)

    # Records indexes
    op.drop_index('ix_records_dmarc_results', table_name='records', if_exists=True)
    op.drop_index('ix_records_source_ip', table_name='records', if_exists=True)
    op.drop_index('ix_records_policy_eval', table_name='records', if_exists=True)
    op.drop_index('ix_records_report_results', table_name='records', if_exists=True)

    # Notifications indexes
    op.drop_index('ix_notifications_user_unread', table_name='user_notifications', if_exists=True)
    op.drop_index('ix_notifications_user_created', table_name='user_notifications', if_exists=True)
    op.drop_index('ix_notifications_expires', table_name='user_notifications', if_exists=True)

    # Saved views index
    op.drop_index('ix_saved_views_user', table_name='user_saved_views', if_exists=True)

    # Audit logs indexes
    op.drop_index('ix_audit_logs_user_time', table_name='audit_logs', if_exists=True)
    op.drop_index('ix_audit_logs_action', table_name='audit_logs', if_exists=True)

    # API keys index
    op.drop_index('ix_api_keys_user_active', table_name='api_keys', if_exists=True)

    # Sessions indexes
    op.drop_index('ix_sessions_expires', table_name='sessions', if_exists=True)
    op.drop_index('ix_sessions_user', table_name='sessions', if_exists=True)
