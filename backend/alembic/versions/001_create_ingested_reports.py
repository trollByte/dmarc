"""create ingested reports table

Revision ID: 001
Revises:
Create Date: 2026-01-06 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ingested_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.String(length=500), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('storage_path', sa.String(length=1000), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('parse_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ingested_reports_content_hash', 'ingested_reports', ['content_hash'], unique=True)
    op.create_index('ix_ingested_reports_message_id', 'ingested_reports', ['message_id'], unique=False)
    op.create_index('ix_ingested_reports_status', 'ingested_reports', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ingested_reports_status', table_name='ingested_reports')
    op.drop_index('ix_ingested_reports_message_id', table_name='ingested_reports')
    op.drop_index('ix_ingested_reports_content_hash', table_name='ingested_reports')
    op.drop_table('ingested_reports')
