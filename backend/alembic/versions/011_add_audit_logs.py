"""add audit logs

Revision ID: 011
Revises: 010
Create Date: 2026-01-10

Creates audit_logs table for tracking user actions:
- Authentication events (login, logout, password changes)
- User management (create, update, delete)
- Data access (reports, exports)
- Configuration changes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create audit_logs table"""

    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('action', sa.String(50), nullable=False, index=True),
        sa.Column('category', sa.String(30), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('username', sa.String(50), nullable=True, index=True),
        sa.Column('ip_address', sa.String(45), nullable=True, index=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('target_type', sa.String(50), nullable=True, index=True),
        sa.Column('target_id', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('old_value', JSONB, nullable=True),
        sa.Column('new_value', JSONB, nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('request_method', sa.String(10), nullable=True),
        sa.Column('request_path', sa.String(500), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )

    # Composite indexes for common queries
    op.create_index(
        'ix_audit_logs_user_created',
        'audit_logs',
        ['user_id', 'created_at']
    )
    op.create_index(
        'ix_audit_logs_action_created',
        'audit_logs',
        ['action', 'created_at']
    )
    op.create_index(
        'ix_audit_logs_category_created',
        'audit_logs',
        ['category', 'created_at']
    )


def downgrade() -> None:
    """Drop audit_logs table"""
    op.drop_index('ix_audit_logs_category_created', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action_created', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_created', table_name='audit_logs')
    op.drop_table('audit_logs')
