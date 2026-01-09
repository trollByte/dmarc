"""add ml analytics and geolocation

Revision ID: 007
Revises: 006
Create Date: 2026-01-09

Creates tables for ML analytics and geolocation:
- geolocation_cache: IP geolocation cache (90-day expiry)
- ml_models: Trained ML models with serialized data
- ml_predictions: ML prediction results
- analytics_cache: Cached analytics data (heatmaps, etc.)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create ML analytics and geolocation tables"""

    # geolocation_cache table
    op.create_table(
        'geolocation_cache',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('ip_address', sa.String(45), unique=True, nullable=False, index=True),
        sa.Column('country_code', sa.String(2), nullable=True, index=True),
        sa.Column('country_name', sa.String(255), nullable=True),
        sa.Column('city_name', sa.String(255), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('timezone', sa.String(100), nullable=True),
        sa.Column('continent_code', sa.String(2), nullable=True),
        sa.Column('continent_name', sa.String(100), nullable=True),
        sa.Column('asn', sa.Integer(), nullable=True),
        sa.Column('asn_organization', sa.String(255), nullable=True),
        sa.Column('isp', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False, index=True),
    )

    # ml_models table
    op.create_table(
        'ml_models',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('model_type', sa.String(50), nullable=False, index=True),
        sa.Column('model_name', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
        sa.Column('model_data', sa.LargeBinary(), nullable=False),
        sa.Column('training_params', JSONB, nullable=True),
        sa.Column('training_metrics', JSONB, nullable=True),
        sa.Column('feature_names', JSONB, nullable=True),
        sa.Column('training_samples', sa.Integer(), default=0, nullable=False),
        sa.Column('training_date_start', sa.DateTime(), nullable=True),
        sa.Column('training_date_end', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False, index=True),
        sa.Column('is_deployed', sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('trained_by', UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['trained_by'], ['users.id'], ondelete='SET NULL')
    )

    # ml_predictions table
    op.create_table(
        'ml_predictions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('model_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('model_type', sa.String(50), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_value', sa.String(255), nullable=False, index=True),
        sa.Column('prediction_type', sa.String(50), nullable=False, index=True),
        sa.Column('prediction_value', sa.Float(), nullable=False),
        sa.Column('prediction_label', sa.String(100), nullable=True, index=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('features', JSONB, nullable=True),
        sa.Column('predicted_at', sa.DateTime(), nullable=False, index=True),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id'], ondelete='CASCADE')
    )

    # analytics_cache table
    op.create_table(
        'analytics_cache',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('cache_key', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('cache_type', sa.String(50), nullable=False, index=True),
        sa.Column('data', JSONB, nullable=False),
        sa.Column('cache_params', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False, index=True),
    )

    # Additional indexes for performance
    op.create_index('ix_geolocation_cache_ip_expires', 'geolocation_cache', ['ip_address', 'expires_at'])
    op.create_index('ix_ml_models_type_deployed', 'ml_models', ['model_type', 'is_deployed', 'is_active'])
    op.create_index('ix_ml_predictions_model_predicted', 'ml_predictions', ['model_id', 'predicted_at'])
    op.create_index('ix_ml_predictions_target_type', 'ml_predictions', ['target_value', 'prediction_type'])
    op.create_index('ix_analytics_cache_type_expires', 'analytics_cache', ['cache_type', 'expires_at'])


def downgrade() -> None:
    """Drop ML analytics and geolocation tables"""
    # Drop indexes
    op.drop_index('ix_analytics_cache_type_expires', table_name='analytics_cache')
    op.drop_index('ix_ml_predictions_target_type', table_name='ml_predictions')
    op.drop_index('ix_ml_predictions_model_predicted', table_name='ml_predictions')
    op.drop_index('ix_ml_models_type_deployed', table_name='ml_models')
    op.drop_index('ix_geolocation_cache_ip_expires', table_name='geolocation_cache')

    # Drop tables
    op.drop_table('analytics_cache')
    op.drop_table('ml_predictions')
    op.drop_table('ml_models')
    op.drop_table('geolocation_cache')
