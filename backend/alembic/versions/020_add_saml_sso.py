"""add saml sso tables

Revision ID: 020
Revises: 019
Create Date: 2026-01-10

Creates tables for SAML SSO authentication.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create SAML SSO tables"""

    # SAML providers table
    op.create_table(
        'saml_providers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('entity_id', sa.String(500), unique=True, nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('sso_url', sa.Text(), nullable=False),
        sa.Column('slo_url', sa.Text(), nullable=True),
        sa.Column('x509_cert', sa.Text(), nullable=False),
        sa.Column('attribute_mapping', JSONB, default={}, nullable=False),
        sa.Column('name_id_format', sa.String(100), nullable=False),
        sa.Column('sign_requests', sa.Boolean(), default=False, nullable=False),
        sa.Column('want_assertions_signed', sa.Boolean(), default=True, nullable=False),
        sa.Column('allow_idp_initiated', sa.Boolean(), default=False, nullable=False),
        sa.Column('auto_provision_users', sa.Boolean(), default=True, nullable=False),
        sa.Column('default_role', sa.String(50), default='viewer', nullable=False),
        sa.Column('admin_groups', JSONB, default=[], nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # SAML sessions table
    op.create_table(
        'saml_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('request_id', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('provider_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('relay_state', sa.String(500), nullable=True),
        sa.Column('redirect_url', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('name_id', sa.String(255), nullable=True),
        sa.Column('session_index', sa.String(255), nullable=True),
        sa.Column('attributes', JSONB, nullable=True),
        sa.Column('error_code', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
    )

    # Add SSO fields to users table if not exists
    op.add_column('users', sa.Column('sso_provider', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('sso_provider_id', sa.String(255), nullable=True))


def downgrade() -> None:
    """Drop SAML SSO tables"""
    op.drop_column('users', 'sso_provider_id')
    op.drop_column('users', 'sso_provider')
    op.drop_table('saml_sessions')
    op.drop_table('saml_providers')
