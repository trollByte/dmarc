"""
Celery tasks for ML model training and analytics.

Tasks:
- train_anomaly_model: Train Isolation Forest model (weekly)
- detect_anomalies_task: Run anomaly detection (daily)
- purge_geolocation_cache: Clean expired geolocation cache (weekly)
"""

import logging
from celery import Task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.ml_analytics import MLAnalyticsService
from app.services.geolocation import GeoLocationService

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management"""
    _db = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


# ==================== ML Model Training ====================

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=1,
    soft_time_limit=3600,  # 1 hour
    time_limit=7200,  # 2 hours
    name="app.tasks.ml_tasks.train_anomaly_model"
)
def train_anomaly_model_task(self, days: int = 90, contamination: float = 0.05):
    """
    Train Isolation Forest anomaly detection model.

    **Schedule:** Weekly (Sunday 2 AM)

    Args:
        days: Number of days of historical data (default: 90)
        contamination: Expected anomaly proportion (default: 0.05 = 5%)

    Returns:
        Dictionary with training results
    """
    logger.info(f"Starting anomaly model training (days={days}, contamination={contamination})")

    try:
        ml_service = MLAnalyticsService(self.db)

        # Train model
        model, metrics = ml_service.train_anomaly_model(
            days=days,
            contamination=contamination,
            user_id=None  # Automated training
        )

        # Auto-deploy if first model or if better than current
        deployed_model = ml_service.get_deployed_model()
        if not deployed_model:
            ml_service.deploy_model(str(model.id))
            logger.info(f"Auto-deployed first model: {model.model_name}")
        else:
            # Compare metrics - deploy if new model has more samples
            if model.training_samples > deployed_model.training_samples:
                ml_service.deploy_model(str(model.id))
                logger.info(f"Auto-deployed better model: {model.model_name}")

        result = {
            "status": "success",
            "model_id": str(model.id),
            "model_name": model.model_name,
            "training_samples": model.training_samples,
            "anomalies_detected": metrics["n_anomalies_detected"],
            "anomaly_percentage": metrics["anomaly_percentage"],
        }

        logger.info(f"Anomaly model training completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Anomaly model training failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=3600)  # Retry in 1 hour


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=2,
    soft_time_limit=1800,  # 30 minutes
    time_limit=3600,  # 1 hour
    name="app.tasks.ml_tasks.detect_anomalies_task"
)
def detect_anomalies_task(self, days: int = 7, threshold: float = -0.5):
    """
    Run anomaly detection on recent data.

    **Schedule:** Daily (3 AM)

    Args:
        days: Number of recent days to analyze (default: 7)
        threshold: Anomaly score threshold (default: -0.5)

    Returns:
        Dictionary with detection results
    """
    logger.info(f"Starting anomaly detection (days={days}, threshold={threshold})")

    try:
        ml_service = MLAnalyticsService(self.db)

        # Check if model is deployed
        deployed_model = ml_service.get_deployed_model()
        if not deployed_model:
            logger.warning("No deployed model available for anomaly detection")
            return {
                "status": "skipped",
                "reason": "no_model_deployed",
                "anomalies_detected": 0
            }

        # Detect anomalies
        anomalies = ml_service.detect_anomalies(
            model_id=None,  # Use deployed model
            days=days,
            threshold=threshold
        )

        # TODO: Create alerts for high-severity anomalies
        # This can be enhanced to trigger alerts via EnhancedAlertService

        result = {
            "status": "success",
            "model_id": str(deployed_model.id),
            "model_name": deployed_model.model_name,
            "anomalies_detected": len(anomalies),
            "top_anomalies": anomalies[:10]  # Top 10 most anomalous
        }

        logger.info(f"Anomaly detection completed: {len(anomalies)} anomalies found")
        return result

    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=1800)  # Retry in 30 minutes


# ==================== Geolocation Cache Management ====================

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=1,
    soft_time_limit=600,  # 10 minutes
    time_limit=1200,  # 20 minutes
    name="app.tasks.ml_tasks.purge_geolocation_cache"
)
def purge_geolocation_cache_task(self):
    """
    Purge expired geolocation cache entries.

    **Schedule:** Weekly (Monday 1 AM)

    Returns:
        Dictionary with purge results
    """
    logger.info("Starting geolocation cache purge")

    try:
        geo_service = GeoLocationService(self.db)

        # Purge expired entries
        purged_count = geo_service.purge_expired_cache()

        # Get cache stats
        stats = geo_service.get_cache_stats()

        result = {
            "status": "success",
            "purged_entries": purged_count,
            "cache_stats": stats
        }

        logger.info(f"Geolocation cache purge completed: {purged_count} entries purged")
        return result

    except Exception as e:
        logger.error(f"Geolocation cache purge failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=3600)  # Retry in 1 hour


# ==================== Manual Trigger Tasks ====================

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=0,
    soft_time_limit=1800,
    time_limit=3600,
    name="app.tasks.ml_tasks.bulk_geolocate_ips"
)
def bulk_geolocate_ips_task(self, ip_addresses: list):
    """
    Bulk geolocate IP addresses and cache results.

    Used for initial cache population or manual updates.

    Args:
        ip_addresses: List of IP addresses to geolocate

    Returns:
        Dictionary with geolocation results
    """
    logger.info(f"Starting bulk geolocation for {len(ip_addresses)} IPs")

    try:
        geo_service = GeoLocationService(self.db)

        # Bulk lookup (will cache results)
        results = geo_service.lookup_ips_bulk(ip_addresses, use_cache=True)

        # Count successful lookups
        successful = sum(1 for r in results.values() if r is not None)
        failed = len(results) - successful

        result = {
            "status": "success",
            "total_ips": len(ip_addresses),
            "successful_lookups": successful,
            "failed_lookups": failed,
            "cache_enabled": True
        }

        logger.info(f"Bulk geolocation completed: {successful}/{len(ip_addresses)} successful")
        return result

    except Exception as e:
        logger.error(f"Bulk geolocation failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


# ==================== Statistics Tasks ====================

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=1,
    soft_time_limit=300,
    time_limit=600,
    name="app.tasks.ml_tasks.generate_analytics_cache"
)
def generate_analytics_cache_task(self, days: int = 30):
    """
    Generate and cache analytics data (country heatmaps, etc.).

    **Schedule:** Daily (4 AM)

    Args:
        days: Number of days to analyze (default: 30)

    Returns:
        Dictionary with cache generation results
    """
    logger.info(f"Starting analytics cache generation (days={days})")

    try:
        from app.models import DmarcRecord, AnalyticsCache
        from datetime import datetime, timedelta

        # Get unique IPs from last N days
        since = datetime.utcnow() - timedelta(days=days)
        ip_addresses = self.db.query(DmarcRecord.source_ip).filter(
            DmarcRecord.created_at >= since
        ).distinct().all()

        ip_list = [ip[0] for ip in ip_addresses]

        logger.info(f"Found {len(ip_list)} unique IPs to analyze")

        # Generate country heatmap
        geo_service = GeoLocationService(self.db)
        heatmap_data = geo_service.generate_country_heatmap(ip_list, use_cache=True)

        # Cache the heatmap data
        cache_key = f"country_heatmap_{days}d"
        expires_at = datetime.utcnow() + timedelta(hours=24)

        # Delete old cache
        self.db.query(AnalyticsCache).filter(
            AnalyticsCache.cache_key == cache_key
        ).delete()

        # Create new cache
        cache_entry = AnalyticsCache(
            cache_key=cache_key,
            cache_type="country_heatmap",
            data=heatmap_data,
            expires_at=expires_at,
            cache_params={"days": days}
        )

        self.db.add(cache_entry)
        self.db.commit()

        result = {
            "status": "success",
            "cache_key": cache_key,
            "total_ips": len(ip_list),
            "countries_mapped": len(heatmap_data.get("countries", {})),
            "expires_at": expires_at.isoformat()
        }

        logger.info(f"Analytics cache generation completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Analytics cache generation failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=1800)
