"""add user authentication

Revision ID: 005
Revises: 004
Create Date: 2026-01-09

Creates tables for JWT-based user authentication with RBAC:
- users: User accounts with roles (admin, analyst, viewer)
- user_api_keys: API keys for programmatic access
- refresh_tokens: JWT refresh tokens for session management
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user authentication tables"""

    # Create UserRole enum type
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'analyst', 'viewer')")

    # users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'analyst', 'viewer', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_locked', sa.Boolean(), default=False, nullable=False),
        sa.Column('failed_login_attempts', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True)
    )

    # user_api_keys table
    op.create_table(
        'user_api_keys',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('key_name', sa.String(100), nullable=False),
        sa.Column('key_prefix', sa.String(10), nullable=False, index=True),
        sa.Column('key_hash', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_used', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )

    # refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('revoked', sa.Boolean(), default=False, nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )

    # Additional indexes for performance
    op.create_index('ix_users_role', 'users', ['role'])
    op.create_index('ix_users_is_active', 'users', ['is_active'])
    op.create_index('ix_user_api_keys_user_id', 'user_api_keys', ['user_id'])
    op.create_index('ix_user_api_keys_expires_at', 'user_api_keys', ['expires_at'])
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('ix_refresh_tokens_revoked', 'refresh_tokens', ['revoked'])


def downgrade() -> None:
    """Drop user authentication tables"""
    # Drop indexes
    op.drop_index('ix_refresh_tokens_revoked', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_index('ix_user_api_keys_expires_at', table_name='user_api_keys')
    op.drop_index('ix_user_api_keys_user_id', table_name='user_api_keys')
    op.drop_index('ix_users_is_active', table_name='users')
    op.drop_index('ix_users_role', table_name='users')

    # Drop tables
    op.drop_table('refresh_tokens')
    op.drop_table('user_api_keys')
    op.drop_table('users')

    # Drop enum type
    op.execute("DROP TYPE userrole")
