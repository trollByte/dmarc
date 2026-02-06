"""
Analytics and ML models.

Implements:
- GeoLocation cache (MaxMind results, 90-day cache)
- ML model storage (trained Isolation Forest models)
- ML predictions (anomaly scores, forecasts)

SECURITY NOTE: ML models use pickle for serialization (standard for scikit-learn).
This is SAFE because we only store self-trained models, never external/untrusted models.
"""

from sqlalchemy import Column, String, DateTime, Float, Integer, Text, Boolean, LargeBinary
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
from app.database import Base


class GeoLocationCache(Base):
    """
    Cache for IP geolocation lookups (MaxMind GeoLite2).

    Caches results for 90 days to minimize database queries.
    """
    __tablename__ = "geolocation_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)  # IPv4 or IPv6

    # Geolocation data
    country_code = Column(String(2), nullable=True, index=True)  # ISO 3166-1 alpha-2
    country_name = Column(String(100), nullable=True)
    city_name = Column(String(100), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    timezone = Column(String(50), nullable=True)
    continent_code = Column(String(2), nullable=True)
    continent_name = Column(String(50), nullable=True)

    # ISP/Organization info (if available)
    asn = Column(Integer, nullable=True)
    asn_organization = Column(String(255), nullable=True)
    isp = Column(String(255), nullable=True)

    # Cache metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)  # 90 days from created_at

    def __repr__(self):
        return f"<GeoLocationCache(ip={self.ip_address}, country={self.country_code}, city={self.city_name})>"

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return datetime.utcnow() > self.expires_at


class MLModel(Base):
    """
    Trained ML model storage.

    Stores serialized scikit-learn models (Isolation Forest, etc.)
    using pickle format (standard for scikit-learn).

    SECURITY: Only self-trained models are stored. Never load external models.
    """
    __tablename__ = "ml_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Model identification
    model_type = Column(String(50), nullable=False, index=True)  # 'isolation_forest', 'holt_winters_forecast'
    model_name = Column(String(255), nullable=False, index=True)  # 'anomaly_detection_v1'
    version = Column(Integer, nullable=False, default=1)

    # Model binary (pickled scikit-learn model)
    model_data = Column(LargeBinary, nullable=False)

    # Model metadata
    training_params = Column(JSONB, nullable=True)  # Hyperparameters used
    training_metrics = Column(JSONB, nullable=True)  # Accuracy, precision, etc.
    feature_names = Column(JSONB, nullable=True)  # Features used for training

    # Training data info
    training_samples = Column(Integer, nullable=True)
    training_date_start = Column(DateTime, nullable=True)
    training_date_end = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_deployed = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    trained_by = Column(UUID(as_uuid=True), nullable=True)  # User ID who triggered training

    def __repr__(self):
        return f"<MLModel(type={self.model_type}, name={self.model_name}, version={self.version})>"


class MLPrediction(Base):
    """
    ML predictions and anomaly scores.

    Stores predictions made by ML models for auditing and analysis.
    """
    __tablename__ = "ml_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Model reference
    model_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    model_type = Column(String(50), nullable=False, index=True)

    # Prediction target
    target_type = Column(String(50), nullable=False, index=True)  # 'ip_address', 'domain', 'time_series'
    target_value = Column(String(255), nullable=False, index=True)  # IP, domain, or date

    # Prediction results
    prediction_type = Column(String(50), nullable=False, index=True)  # 'anomaly', 'forecast', 'classification'
    prediction_value = Column(Float, nullable=True)  # Anomaly score, predicted value, etc.
    prediction_label = Column(String(50), nullable=True)  # 'anomaly', 'normal', 'high_risk', etc.
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0

    # Additional context
    features = Column(JSONB, nullable=True)  # Features used for prediction
    prediction_metadata = Column(JSONB, nullable=True)  # Additional context

    # Timestamps
    predicted_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    prediction_date = Column(DateTime, nullable=True, index=True)  # Date the prediction is for (forecasting)

    def __repr__(self):
        return f"<MLPrediction(type={self.prediction_type}, target={self.target_value}, score={self.prediction_value})>"


class AnalyticsCache(Base):
    """
    General analytics cache for expensive computations.

    Stores pre-computed analytics results (e.g., country heatmaps, trend data).
    """
    __tablename__ = "analytics_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Cache key (unique identifier for cached data)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    cache_type = Column(String(50), nullable=False, index=True)  # 'country_heatmap', 'trend_data'

    # Cached data (JSON)
    data = Column(JSONB, nullable=False)

    # Cache metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    cache_params = Column(JSONB, nullable=True)  # Parameters used to generate cache

    def __repr__(self):
        return f"<AnalyticsCache(key={self.cache_key}, type={self.cache_type})>"

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return datetime.utcnow() > self.expires_at
