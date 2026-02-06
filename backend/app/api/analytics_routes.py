"""
API routes for ML analytics and geolocation.

Endpoints:
- Geolocation: IP lookup, country heatmaps
- ML Models: Training, deployment, management
- Anomaly Detection: IP anomaly detection
- Statistics: Model stats, cache stats
"""

import logging
from functools import wraps
from typing import List, Optional, Callable, TypeVar
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import UUID4

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models import User, UserRole, DmarcRecord
from app.services.geolocation import GeoLocationService
from app.services.ml_analytics import MLAnalyticsService
from app.schemas.analytics_schemas import (
    GeoLocationResponse,
    GeoLocationBulkRequest,
    CountryHeatmapResponse,
    MLModelSummary,
    MLModelDetail,
    TrainModelRequest,
    TrainModelResponse,
    DeployModelRequest,
    DeployModelResponse,
    AnomaliesResponse,
    DetectAnomaliesRequest,
    DetectAnomaliesWithAlertsRequest,
    DetectAnomaliesWithAlertsResponse,
    ModelStatsResponse,
    CacheStatsResponse,
    MLPredictionResponse,
)
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def handle_service_errors(error_message: str):
    """
    Decorator to handle common service error patterns.

    Catches ValueError (400), re-raises HTTPException, and logs unexpected errors (500).
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"{error_message}: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"{error_message}: {str(e)}")
        return wrapper
    return decorator


# ==================== Geolocation Endpoints ====================

@router.get(
    "/geolocation/map",
    response_model=CountryHeatmapResponse,
    summary="Get country heatmap data"
)
@handle_service_errors("Failed to generate heatmap")
async def get_country_heatmap(
    days: int = Query(default=30, ge=1, le=365, description="Days of data to analyze"),
    use_cache: bool = Query(default=True, description="Use geolocation cache"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate country heatmap data for visualization.

    Returns IP distribution by country for the last N days.
    """
    since = datetime.utcnow() - timedelta(days=days)
    ip_addresses = db.query(DmarcRecord.source_ip).filter(
        DmarcRecord.created_at >= since
    ).distinct().all()

    ip_list = [ip[0] for ip in ip_addresses]

    if not ip_list:
        return CountryHeatmapResponse(
            countries={},
            max_count=0,
            total_ips=0,
            mapped_ips=0,
            unmapped_ips=0
        )

    geo_service = GeoLocationService(db)
    heatmap_data = geo_service.generate_country_heatmap(ip_list, use_cache=use_cache)

    return CountryHeatmapResponse(**heatmap_data)


@router.get(
    "/geolocation/lookup/{ip_address}",
    response_model=GeoLocationResponse,
    summary="Lookup geolocation for single IP"
)
@handle_service_errors("Lookup failed")
async def lookup_ip_geolocation(
    ip_address: str,
    use_cache: bool = Query(default=True, description="Use geolocation cache"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lookup geolocation data for a single IP address.

    Uses MaxMind GeoLite2 database with 90-day caching.
    """
    geo_service = GeoLocationService(db)
    geo_data = geo_service.lookup_ip(ip_address, use_cache=use_cache)

    if not geo_data:
        raise HTTPException(
            status_code=404,
            detail=f"Geolocation not found for IP: {ip_address}"
        )

    return GeoLocationResponse(**geo_data)


@router.post(
    "/geolocation/lookup-bulk",
    response_model=List[GeoLocationResponse],
    summary="Bulk IP geolocation lookup"
)
@handle_service_errors("Bulk lookup failed")
async def lookup_ips_bulk(
    request: GeoLocationBulkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk lookup geolocation for multiple IP addresses.

    More efficient than individual lookups. Max 1000 IPs per request.
    """
    geo_service = GeoLocationService(db)
    results = geo_service.lookup_ips_bulk(
        request.ip_addresses,
        use_cache=request.use_cache
    )

    return [
        GeoLocationResponse(**geo_data) if geo_data else GeoLocationResponse(ip_address=ip)
        for ip, geo_data in results.items()
    ]


@router.get(
    "/geolocation/cache-stats",
    response_model=CacheStatsResponse,
    summary="Get geolocation cache statistics"
)
@handle_service_errors("Failed to get stats")
async def get_cache_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get statistics about geolocation cache."""
    geo_service = GeoLocationService(db)
    stats = geo_service.get_cache_stats()
    return CacheStatsResponse(**stats)


# ==================== ML Model Management ====================

@router.get(
    "/ml/models",
    response_model=List[MLModelSummary],
    summary="List trained ML models"
)
@handle_service_errors("Failed to list models")
async def list_models(
    model_type: Optional[str] = Query(default="isolation_forest", description="Model type"),
    active_only: bool = Query(default=False, description="Show only active models"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all trained ML models.

    Sorted by creation date (newest first).
    """
    ml_service = MLAnalyticsService(db)
    models = ml_service.list_models(model_type=model_type, active_only=active_only)

    return [MLModelSummary.model_validate(model) for model in models]


@router.get(
    "/ml/models/{model_id}",
    response_model=MLModelDetail,
    summary="Get ML model details"
)
@handle_service_errors("Failed to get model")
async def get_model_detail(
    model_id: UUID4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed information about a specific ML model."""
    from app.models import MLModel

    model = db.query(MLModel).filter(MLModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    return MLModelDetail.model_validate(model)


@router.post(
    "/ml/train",
    response_model=TrainModelResponse,
    summary="Train ML model (admin only)"
)
@handle_service_errors("Training failed")
async def train_model(
    request: TrainModelRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Train a new ML model.

    **Admin only**. Training runs synchronously and may take 1-5 minutes.

    For Isolation Forest:
    - Trains on last N days of data (default: 90)
    - Contamination: expected anomaly proportion (default: 5%)
    - Auto-deploys if first model or better than current
    """
    ml_service = MLAnalyticsService(db)

    model, metrics = ml_service.train_anomaly_model(
        days=request.days,
        contamination=request.contamination,
        user_id=str(current_user.id)
    )

    # Auto-deploy if first model
    deployed_model = ml_service.get_deployed_model()
    if not deployed_model:
        ml_service.deploy_model(str(model.id))
        logger.info(f"Auto-deployed first model: {model.model_name}")

    return TrainModelResponse(
        status="success",
        model_id=model.id,
        model_name=model.model_name,
        training_samples=model.training_samples,
        anomalies_detected=metrics["n_anomalies_detected"],
        anomaly_percentage=metrics["anomaly_percentage"],
    )


@router.post(
    "/ml/deploy",
    response_model=DeployModelResponse,
    summary="Deploy trained ML model (admin only)"
)
@handle_service_errors("Deployment failed")
async def deploy_model(
    request: DeployModelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Deploy a trained ML model for production use.

    **Admin only**. Deactivates all other models of the same type.
    """
    ml_service = MLAnalyticsService(db)
    model = ml_service.deploy_model(str(request.model_id))

    return DeployModelResponse(
        status="success",
        model_id=model.id,
        model_name=model.model_name,
        message=f"Model {model.model_name} deployed successfully"
    )


@router.get(
    "/ml/models/{model_id}/stats",
    response_model=ModelStatsResponse,
    summary="Get ML model statistics"
)
@handle_service_errors("Failed to get stats")
async def get_model_stats(
    model_id: UUID4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get statistics for a trained ML model."""
    ml_service = MLAnalyticsService(db)
    stats = ml_service.get_model_stats(str(model_id))

    return ModelStatsResponse(**stats)


# ==================== Anomaly Detection ====================

@router.post(
    "/anomalies/detect",
    response_model=AnomaliesResponse,
    summary="Detect anomalous IP addresses"
)
@handle_service_errors("Detection failed")
async def detect_anomalies(
    request: DetectAnomaliesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run anomaly detection on recent DMARC data.

    Uses deployed Isolation Forest model to detect anomalous IP behavior.

    Returns IPs sorted by anomaly score (most anomalous first).
    """
    ml_service = MLAnalyticsService(db)

    model_id = str(request.model_id) if request.model_id else None

    anomalies = ml_service.detect_anomalies(
        model_id=model_id,
        days=request.days,
        threshold=request.threshold
    )

    deployed_model = ml_service.get_deployed_model()

    return AnomaliesResponse(
        status="success",
        model_id=deployed_model.id if deployed_model else None,
        model_name=deployed_model.model_name if deployed_model else None,
        anomalies_detected=len(anomalies),
        anomalies=anomalies
    )


@router.post(
    "/anomalies/detect-with-alerts",
    response_model=DetectAnomaliesWithAlertsResponse,
    summary="Detect anomalies and create alerts (analyst+)"
)
@handle_service_errors("Detection with alerts failed")
async def detect_anomalies_with_alerts(
    request: DetectAnomaliesWithAlertsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ANALYST)),
):
    """
    Run anomaly detection and automatically create alerts for detected anomalies.

    **Analyst or Admin only.**

    - Detects anomalous IPs using deployed ML model
    - Creates WARNING alerts for scores below threshold
    - Creates CRITICAL alerts for scores below critical_threshold
    - Enriches alerts with geolocation data
    - Sends notifications via configured channels (Teams, Email, Slack)

    This is the same logic that runs daily at 3 AM via Celery beat.
    """
    from app.services.alerting_v2 import EnhancedAlertService
    from app.models import AlertType, AlertSeverity

    ml_service = MLAnalyticsService(db)
    geo_service = GeoLocationService(db)
    alert_service = EnhancedAlertService(db)

    # Check if model is deployed
    deployed_model = ml_service.get_deployed_model()
    if not deployed_model:
        raise HTTPException(
            status_code=400,
            detail="No deployed ML model available. Train and deploy a model first."
        )

    # Detect anomalies
    anomalies = ml_service.detect_anomalies(
        model_id=None,
        days=request.days,
        threshold=request.threshold
    )

    # Sort by anomaly score (most anomalous first)
    sorted_anomalies = sorted(anomalies, key=lambda x: x["anomaly_score"])
    alerts_created = 0

    for anomaly in sorted_anomalies[:request.max_alerts]:
        score = anomaly["anomaly_score"]
        ip = anomaly["ip_address"]
        features = anomaly["features"]

        # Determine severity
        if score < request.critical_threshold:
            severity = AlertSeverity.CRITICAL
        else:
            severity = AlertSeverity.WARNING

        # Enrich with geolocation
        geo_data = geo_service.lookup_ip(ip)
        location_str = "Unknown location"
        if geo_data:
            parts = []
            if geo_data.get("city"):
                parts.append(geo_data["city"])
            if geo_data.get("country"):
                parts.append(geo_data["country"])
            if parts:
                location_str = ", ".join(parts)
            if geo_data.get("org"):
                location_str += f" ({geo_data['org']})"

        # Build alert
        title = f"Anomalous IP detected: {ip}"
        message = (
            f"ML model detected anomalous behavior from IP {ip}.\n\n"
            f"Location: {location_str}\n"
            f"Anomaly Score: {score:.3f}\n"
            f"Email Volume: {features['volume']:,}\n"
            f"Failure Rate: {features['failure_rate']:.1f}%\n"
            f"Unique Domains: {features['unique_domains']}"
        )

        alert = alert_service.create_alert(
            alert_type=AlertType.ANOMALY,
            severity=severity,
            title=title,
            message=message,
            domain=None,
            current_value=score,
            threshold_value=request.critical_threshold if severity == AlertSeverity.CRITICAL else request.threshold,
            metadata={
                "ip_address": ip,
                "anomaly_score": score,
                "features": features,
                "geolocation": geo_data,
                "model_id": str(deployed_model.id),
                "triggered_by": str(current_user.id),
            }
        )

        if alert:
            alerts_created += 1

    return DetectAnomaliesWithAlertsResponse(
        status="success",
        model_id=deployed_model.id,
        model_name=deployed_model.model_name,
        anomalies_detected=len(anomalies),
        alerts_created=alerts_created,
        top_anomalies=sorted_anomalies[:10]
    )


@router.get(
    "/anomalies/recent",
    response_model=List[MLPredictionResponse],
    summary="Get recent anomaly predictions"
)
@handle_service_errors("Failed to fetch anomalies")
async def get_recent_anomalies(
    days: int = Query(default=7, ge=1, le=90, description="Days of predictions to fetch"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max predictions to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent anomaly predictions from database.

    Returns stored predictions from the last N days.
    """
    from app.models import MLPrediction

    since = datetime.utcnow() - timedelta(days=days)

    predictions = db.query(MLPrediction).filter(
        MLPrediction.predicted_at >= since,
        MLPrediction.prediction_type == "anomaly"
    ).order_by(
        MLPrediction.predicted_at.desc()
    ).limit(limit).all()

    return [MLPredictionResponse.model_validate(p) for p in predictions]


# ==================== Time-series Forecasting ====================

@router.get(
    "/forecast/volume",
    summary="Forecast email volume"
)
@handle_service_errors("Forecasting failed")
async def forecast_volume(
    forecast_days: int = Query(default=14, ge=1, le=30, description="Days to forecast"),
    history_days: int = Query(default=90, ge=14, le=365, description="Days of history to use"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Forecast future email volumes using exponential smoothing.

    **Features:**
    - Holt-Winters exponential smoothing
    - Weekly seasonality detection
    - Trend analysis
    - 95% confidence intervals

    **Returns:**
    - Daily volume predictions
    - Trend direction and strength
    - Weekly pattern (if seasonal)
    - Model accuracy (MAPE)
    """
    from app.services.forecasting import ForecastingService

    forecast_service = ForecastingService(db)
    result = forecast_service.get_anomaly_forecast(
        forecast_days=forecast_days,
        history_days=history_days
    )

    return result


@router.get(
    "/forecast/domain/{domain}",
    summary="Forecast volume for specific domain"
)
@handle_service_errors("Domain forecasting failed")
async def forecast_domain_volume(
    domain: str,
    forecast_days: int = Query(default=14, ge=1, le=30, description="Days to forecast"),
    history_days: int = Query(default=60, ge=7, le=180, description="Days of history"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Forecast future email volumes for a specific domain.

    Uses simple exponential smoothing for domain-level forecasting.
    """
    from app.services.forecasting import ForecastingService

    forecast_service = ForecastingService(db)
    result = forecast_service.get_domain_forecast(
        domain=domain,
        forecast_days=forecast_days,
        history_days=history_days
    )

    return result


@router.get(
    "/forecast/summary",
    summary="Get forecast summary for dashboard"
)
@handle_service_errors("Forecast summary failed")
async def get_forecast_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a summary of volume forecasts for dashboard display.

    Returns:
    - Next 7 day predictions
    - Trend summary
    - Expected vs. typical volume comparison
    """
    from app.services.forecasting import ForecastingService

    forecast_service = ForecastingService(db)

    try:
        result = forecast_service.forecast_volume(
            forecast_days=7,
            history_days=60
        )

        # Calculate summary stats
        predicted_volumes = [f.predicted_volume for f in result.forecasts]
        avg_predicted = sum(predicted_volumes) / len(predicted_volumes) if predicted_volumes else 0

        # Compare to historical
        volume_change = ((avg_predicted - result.historical_avg) / result.historical_avg * 100) if result.historical_avg > 0 else 0

        return {
            "forecast_period": "7 days",
            "predictions": [
                {
                    "date": f.date.isoformat(),
                    "volume": f.predicted_volume,
                    "is_weekend": f.is_weekend,
                }
                for f in result.forecasts
            ],
            "summary": {
                "avg_predicted_volume": round(avg_predicted),
                "historical_avg_volume": round(result.historical_avg),
                "volume_change_percent": round(volume_change, 1),
                "trend": result.trend_direction.value,
                "trend_strength": round(result.trend_strength, 2),
            },
            "model_accuracy_mape": round(result.model_accuracy, 1),
        }

    except ValueError as e:
        # Not enough data for forecast
        return {
            "forecast_period": "7 days",
            "predictions": [],
            "summary": {
                "error": str(e),
                "avg_predicted_volume": None,
                "historical_avg_volume": None,
                "volume_change_percent": None,
                "trend": "unknown",
                "trend_strength": 0,
            },
            "model_accuracy_mape": None,
        }
