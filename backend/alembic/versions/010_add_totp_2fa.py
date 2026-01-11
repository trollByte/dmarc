"""add totp 2fa

Revision ID: 010
Revises: 009
Create Date: 2026-01-10

Adds Two-Factor Authentication (TOTP) columns to users table:
- totp_secret: Encrypted TOTP secret key
- totp_enabled: Whether 2FA is enabled
- totp_backup_codes: JSON array of hashed backup codes
- totp_verified_at: When 2FA was verified/enabled
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add TOTP 2FA columns to users table"""

    op.add_column('users', sa.Column('totp_secret', sa.String(32), nullable=True))
    op.add_column('users', sa.Column('totp_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('totp_backup_codes', JSONB, nullable=True))
    op.add_column('users', sa.Column('totp_verified_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove TOTP 2FA columns from users table"""

    op.drop_column('users', 'totp_verified_at')
    op.drop_column('users', 'totp_backup_codes')
    op.drop_column('users', 'totp_enabled')
    op.drop_column('users', 'totp_secret')
