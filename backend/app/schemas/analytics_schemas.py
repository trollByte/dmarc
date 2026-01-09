"""
Pydantic schemas for analytics endpoints.
"""

from pydantic import BaseModel, Field, UUID4
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ==================== Geolocation Schemas ====================

class GeoLocationResponse(BaseModel):
    """Single IP geolocation response"""
    ip_address: str
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    city_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    continent_code: Optional[str] = None
    continent_name: Optional[str] = None
    asn: Optional[int] = None
    asn_organization: Optional[str] = None
    isp: Optional[str] = None

    class Config:
        from_attributes = True


class GeoLocationBulkRequest(BaseModel):
    """Bulk IP lookup request"""
    ip_addresses: List[str] = Field(..., min_items=1, max_items=1000)
    use_cache: bool = True


class CountryHeatmapResponse(BaseModel):
    """Country heatmap data for visualization"""
    countries: Dict[str, Dict[str, Any]] = Field(
        description="Country code -> {count, name}"
    )
    max_count: int
    total_ips: int
    mapped_ips: int
    unmapped_ips: int


# ==================== ML Model Schemas ====================

class MLModelType(str, Enum):
    """ML model types"""
    ISOLATION_FOREST = "isolation_forest"
    LSTM_FORECAST = "lstm_forecast"


class MLModelSummary(BaseModel):
    """ML model summary (list view)"""
    id: UUID4
    model_type: str
    model_name: str
    version: int
    is_deployed: bool
    is_active: bool
    training_samples: int
    created_at: datetime
    trained_by: Optional[UUID4] = None

    class Config:
        from_attributes = True


class MLModelDetail(BaseModel):
    """ML model detailed view"""
    id: UUID4
    model_type: str
    model_name: str
    version: int
    is_deployed: bool
    is_active: bool
    training_params: Dict[str, Any]
    training_metrics: Dict[str, Any]
    feature_names: List[str]
    training_samples: int
    training_date_start: Optional[datetime] = None
    training_date_end: Optional[datetime] = None
    created_at: datetime
    trained_by: Optional[UUID4] = None

    class Config:
        from_attributes = True


class TrainModelRequest(BaseModel):
    """Request to train ML model"""
    model_type: MLModelType = MLModelType.ISOLATION_FOREST
    days: int = Field(default=90, ge=30, le=365, description="Days of historical data")
    contamination: float = Field(
        default=0.05, ge=0.01, le=0.5, description="Expected anomaly proportion (0.05 = 5%)"
    )


class TrainModelResponse(BaseModel):
    """Response from model training"""
    status: str
    model_id: UUID4
    model_name: str
    training_samples: int
    anomalies_detected: int
    anomaly_percentage: float
    task_id: Optional[str] = None


class DeployModelRequest(BaseModel):
    """Request to deploy trained model"""
    model_id: UUID4


class DeployModelResponse(BaseModel):
    """Response from model deployment"""
    status: str
    model_id: UUID4
    model_name: str
    message: str


# ==================== Anomaly Detection Schemas ====================

class AnomalyFeatures(BaseModel):
    """Features extracted for anomaly"""
    volume: int
    failure_rate: float
    unique_domains: int


class AnomalyDetection(BaseModel):
    """Single anomaly detection result"""
    ip_address: str
    anomaly_score: float
    is_anomaly: bool
    features: AnomalyFeatures
    first_seen: datetime
    last_seen: datetime


class AnomaliesResponse(BaseModel):
    """Anomaly detection results"""
    status: str
    model_id: Optional[UUID4] = None
    model_name: Optional[str] = None
    anomalies_detected: int
    anomalies: List[AnomalyDetection]


class DetectAnomaliesRequest(BaseModel):
    """Request to detect anomalies"""
    model_id: Optional[UUID4] = None
    days: int = Field(default=7, ge=1, le=90, description="Days of recent data to analyze")
    threshold: float = Field(
        default=-0.5, ge=-1.0, le=0.0, description="Anomaly score threshold (lower = more anomalous)"
    )


# ==================== ML Prediction Schemas ====================

class MLPredictionResponse(BaseModel):
    """ML prediction record"""
    id: UUID4
    model_id: UUID4
    model_type: str
    target_type: str
    target_value: str
    prediction_type: str
    prediction_value: float
    prediction_label: str
    features: Dict[str, Any]
    predicted_at: datetime

    class Config:
        from_attributes = True


# ==================== Statistics Schemas ====================

class ModelStatsResponse(BaseModel):
    """Statistics for ML model"""
    model_id: UUID4
    model_name: str
    model_type: str
    version: int
    is_deployed: bool
    training_samples: int
    training_metrics: Dict[str, Any]
    predictions_made: int
    anomalies_detected: int
    created_at: datetime
    trained_by: Optional[UUID4] = None


class CacheStatsResponse(BaseModel):
    """Geolocation cache statistics"""
    total_entries: int
    expired_entries: int
    active_entries: int
    database_loaded: bool
    database_path: str
