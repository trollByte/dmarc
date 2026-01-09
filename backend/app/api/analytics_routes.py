"""
API routes for ML analytics and geolocation.

Endpoints:
- Geolocation: IP lookup, country heatmaps
- ML Models: Training, deployment, management
- Anomaly Detection: IP anomaly detection
- Statistics: Model stats, cache stats
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import UUID4

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models import User, DmarcRecord
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
    ModelStatsResponse,
    CacheStatsResponse,
    MLPredictionResponse,
)
from datetime import datetime, timedelta
from sqlalchemy import func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ==================== Geolocation Endpoints ====================

@router.get(
    "/geolocation/map",
    response_model=CountryHeatmapResponse,
    summary="Get country heatmap data"
)
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
    try:
        # Get unique IPs from last N days
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

        # Generate heatmap
        geo_service = GeoLocationService(db)
        heatmap_data = geo_service.generate_country_heatmap(ip_list, use_cache=use_cache)

        return CountryHeatmapResponse(**heatmap_data)

    except Exception as e:
        logger.error(f"Error generating country heatmap: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate heatmap: {str(e)}")


@router.get(
    "/geolocation/lookup/{ip_address}",
    response_model=GeoLocationResponse,
    summary="Lookup geolocation for single IP"
)
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
    try:
        geo_service = GeoLocationService(db)
        geo_data = geo_service.lookup_ip(ip_address, use_cache=use_cache)

        if not geo_data:
            raise HTTPException(
                status_code=404,
                detail=f"Geolocation not found for IP: {ip_address}"
            )

        return GeoLocationResponse(**geo_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error looking up IP {ip_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lookup failed: {str(e)}")


@router.post(
    "/geolocation/lookup-bulk",
    response_model=List[GeoLocationResponse],
    summary="Bulk IP geolocation lookup"
)
async def lookup_ips_bulk(
    request: GeoLocationBulkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk lookup geolocation for multiple IP addresses.

    More efficient than individual lookups. Max 1000 IPs per request.
    """
    try:
        geo_service = GeoLocationService(db)
        results = geo_service.lookup_ips_bulk(
            request.ip_addresses,
            use_cache=request.use_cache
        )

        # Convert to list of responses (include None results as empty data)
        response_list = []
        for ip, geo_data in results.items():
            if geo_data:
                response_list.append(GeoLocationResponse(**geo_data))
            else:
                # Return IP with no geolocation data
                response_list.append(GeoLocationResponse(ip_address=ip))

        return response_list

    except Exception as e:
        logger.error(f"Error in bulk IP lookup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Bulk lookup failed: {str(e)}")


@router.get(
    "/geolocation/cache-stats",
    response_model=CacheStatsResponse,
    summary="Get geolocation cache statistics"
)
async def get_cache_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get statistics about geolocation cache."""
    try:
        geo_service = GeoLocationService(db)
        stats = geo_service.get_cache_stats()
        return CacheStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


# ==================== ML Model Management ====================

@router.get(
    "/ml/models",
    response_model=List[MLModelSummary],
    summary="List trained ML models"
)
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
    try:
        ml_service = MLAnalyticsService(db)
        models = ml_service.list_models(model_type=model_type, active_only=active_only)

        return [MLModelSummary.model_validate(model) for model in models]

    except Exception as e:
        logger.error(f"Error listing models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@router.get(
    "/ml/models/{model_id}",
    response_model=MLModelDetail,
    summary="Get ML model details"
)
async def get_model_detail(
    model_id: UUID4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed information about a specific ML model."""
    try:
        from app.models import MLModel

        model = db.query(MLModel).filter(MLModel.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

        return MLModelDetail.model_validate(model)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get model: {str(e)}")


@router.post(
    "/ml/train",
    response_model=TrainModelResponse,
    summary="Train ML model (admin only)"
)
async def train_model(
    request: TrainModelRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Train a new ML model.

    **Admin only**. Training runs synchronously and may take 1-5 minutes.

    For Isolation Forest:
    - Trains on last N days of data (default: 90)
    - Contamination: expected anomaly proportion (default: 5%)
    - Auto-deploys if first model or better than current
    """
    try:
        ml_service = MLAnalyticsService(db)

        # Train model (synchronous)
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

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error training model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.post(
    "/ml/deploy",
    response_model=DeployModelResponse,
    summary="Deploy trained ML model (admin only)"
)
async def deploy_model(
    request: DeployModelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Deploy a trained ML model for production use.

    **Admin only**. Deactivates all other models of the same type.
    """
    try:
        ml_service = MLAnalyticsService(db)
        model = ml_service.deploy_model(str(request.model_id))

        return DeployModelResponse(
            status="success",
            model_id=model.id,
            model_name=model.model_name,
            message=f"Model {model.model_name} deployed successfully"
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deploying model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")


@router.get(
    "/ml/models/{model_id}/stats",
    response_model=ModelStatsResponse,
    summary="Get ML model statistics"
)
async def get_model_stats(
    model_id: UUID4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get statistics for a trained ML model."""
    try:
        ml_service = MLAnalyticsService(db)
        stats = ml_service.get_model_stats(str(model_id))

        return ModelStatsResponse(**stats)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting model stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


# ==================== Anomaly Detection ====================

@router.post(
    "/anomalies/detect",
    response_model=AnomaliesResponse,
    summary="Detect anomalous IP addresses"
)
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
    try:
        ml_service = MLAnalyticsService(db)

        # Use deployed model if no model_id specified
        model_id = str(request.model_id) if request.model_id else None

        anomalies = ml_service.detect_anomalies(
            model_id=model_id,
            days=request.days,
            threshold=request.threshold
        )

        # Get deployed model info
        deployed_model = ml_service.get_deployed_model()

        return AnomaliesResponse(
            status="success",
            model_id=deployed_model.id if deployed_model else None,
            model_name=deployed_model.model_name if deployed_model else None,
            anomalies_detected=len(anomalies),
            anomalies=anomalies
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.get(
    "/anomalies/recent",
    response_model=List[MLPredictionResponse],
    summary="Get recent anomaly predictions"
)
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
    try:
        from app.models import MLPrediction

        since = datetime.utcnow() - timedelta(days=days)

        predictions = db.query(MLPrediction).filter(
            MLPrediction.predicted_at >= since,
            MLPrediction.prediction_type == "anomaly"
        ).order_by(
            MLPrediction.predicted_at.desc()
        ).limit(limit).all()

        return [MLPredictionResponse.model_validate(p) for p in predictions]

    except Exception as e:
        logger.error(f"Error fetching recent anomalies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch anomalies: {str(e)}")
