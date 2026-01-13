"""add celery task tracking tables

Revision ID: 004
Revises: 003
Create Date: 2026-01-09

Creates tables for Celery task result backend (PostgreSQL).
These tables store task state, results, and metadata for distributed task execution.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BYTEA


# revision identifiers, used by Alembic
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists in the database"""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name)"
    ), {"table_name": table_name})
    return result.scalar()


def index_exists(index_name):
    """Check if an index exists in the database"""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM pg_indexes WHERE indexname = :index_name)"
    ), {"index_name": index_name})
    return result.scalar()


def upgrade() -> None:
    """Create Celery task tracking tables"""

    # celery_taskmeta - stores task results and status
    # Skip if already created by Celery
    if not table_exists('celery_taskmeta'):
        op.create_table(
            'celery_taskmeta',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('task_id', sa.String(155), unique=True, nullable=False, index=True),
            sa.Column('status', sa.String(50), nullable=True),
            sa.Column('result', BYTEA, nullable=True),  # Pickled result
            sa.Column('date_done', sa.DateTime(), nullable=True),
            sa.Column('traceback', sa.Text(), nullable=True),
            sa.Column('name', sa.String(155), nullable=True),
            sa.Column('args', BYTEA, nullable=True),
            sa.Column('kwargs', BYTEA, nullable=True),
            sa.Column('worker', sa.String(155), nullable=True),
            sa.Column('retries', sa.Integer(), nullable=True, default=0),
            sa.Column('queue', sa.String(155), nullable=True)
        )

    # celery_tasksetmeta - stores task group results
    if not table_exists('celery_tasksetmeta'):
        op.create_table(
            'celery_tasksetmeta',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('taskset_id', sa.String(155), unique=True, nullable=False, index=True),
            sa.Column('result', BYTEA, nullable=True),
            sa.Column('date_done', sa.DateTime(), nullable=True)
        )

    # Indexes for performance (skip if already exist)
    if not index_exists('ix_celery_taskmeta_date_done'):
        op.create_index('ix_celery_taskmeta_date_done', 'celery_taskmeta', ['date_done'])
    if not index_exists('ix_celery_taskmeta_status'):
        op.create_index('ix_celery_taskmeta_status', 'celery_taskmeta', ['status'])
    if not index_exists('ix_celery_taskmeta_name'):
        op.create_index('ix_celery_taskmeta_name', 'celery_taskmeta', ['name'])
    if not index_exists('ix_celery_tasksetmeta_date_done'):
        op.create_index('ix_celery_tasksetmeta_date_done', 'celery_tasksetmeta', ['date_done'])


def downgrade() -> None:
    """Drop Celery task tracking tables"""
    op.drop_index('ix_celery_tasksetmeta_date_done', table_name='celery_tasksetmeta')
    op.drop_index('ix_celery_taskmeta_name', table_name='celery_taskmeta')
    op.drop_index('ix_celery_taskmeta_status', table_name='celery_taskmeta')
    op.drop_index('ix_celery_taskmeta_date_done', table_name='celery_taskmeta')
    op.drop_table('celery_tasksetmeta')
    op.drop_table('celery_taskmeta')
