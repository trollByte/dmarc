"""Add performance indexes for common query patterns

Revision ID: 023_perf_indexes
Revises: 022
Create Date: 2024-01-18

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '023_perf_indexes'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add indexes to optimize common query patterns."""

    # dmarc_reports: composite date range index
    op.execute("CREATE INDEX IF NOT EXISTS ix_reports_date_range ON dmarc_reports (date_begin, date_end)")
    # dmarc_reports: org + date composite for dashboard queries
    op.execute("CREATE INDEX IF NOT EXISTS ix_reports_org_date ON dmarc_reports (org_name, date_begin)")

    # dmarc_records: composite DMARC results for analysis
    op.execute("CREATE INDEX IF NOT EXISTS ix_records_dmarc_results ON dmarc_records (dkim_result, spf_result)")
    # dmarc_records: policy evaluation results
    op.execute("CREATE INDEX IF NOT EXISTS ix_records_policy_eval ON dmarc_records (disposition)")
    # dmarc_records: header_from for domain filtering
    op.execute("CREATE INDEX IF NOT EXISTS ix_records_header_from ON dmarc_records (header_from)")
    # dmarc_records: composite for report-record queries with results
    op.execute("CREATE INDEX IF NOT EXISTS ix_records_report_results ON dmarc_records (report_id, dkim_result, spf_result)")

    # User notifications
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_unread ON user_notifications (user_id, is_read)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_created ON user_notifications (user_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_expires ON user_notifications (expires_at) WHERE expires_at IS NOT NULL")

    # Saved views
    op.execute("CREATE INDEX IF NOT EXISTS ix_saved_views_user ON saved_views (user_id, is_default)")

    # Audit logs
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_time ON audit_logs (user_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action, created_at)")

    # API keys
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_user_active ON user_api_keys (user_id, is_active)")


def downgrade() -> None:
    """Remove performance indexes."""
    op.execute("DROP INDEX IF EXISTS ix_reports_date_range")
    op.execute("DROP INDEX IF EXISTS ix_reports_org_date")
    op.execute("DROP INDEX IF EXISTS ix_records_dmarc_results")
    op.execute("DROP INDEX IF EXISTS ix_records_policy_eval")
    op.execute("DROP INDEX IF EXISTS ix_records_header_from")
    op.execute("DROP INDEX IF EXISTS ix_records_report_results")
    op.execute("DROP INDEX IF EXISTS ix_notifications_user_unread")
    op.execute("DROP INDEX IF EXISTS ix_notifications_user_created")
    op.execute("DROP INDEX IF EXISTS ix_notifications_expires")
    op.execute("DROP INDEX IF EXISTS ix_saved_views_user")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_user_time")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_action")
    op.execute("DROP INDEX IF EXISTS ix_api_keys_user_active")
