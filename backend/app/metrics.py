"""
Prometheus metrics configuration for DMARC Dashboard

Provides application metrics for monitoring:
- HTTP request latency and counts
- Database connection pool stats
- Celery task metrics
- Business metrics (reports processed, alerts triggered)
"""
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import APIRouter, Response
from functools import wraps
import time
import logging

logger = logging.getLogger(__name__)

# Create metrics router
metrics_router = APIRouter(tags=["metrics"])

# =============================================================================
# HTTP Metrics
# =============================================================================

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    ["method", "endpoint"]
)

# =============================================================================
# Database Metrics
# =============================================================================

DB_CONNECTIONS_ACTIVE = Gauge(
    "db_connections_active",
    "Number of active database connections"
)

DB_CONNECTIONS_IDLE = Gauge(
    "db_connections_idle",
    "Number of idle database connections"
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

# =============================================================================
# Business Metrics
# =============================================================================

DMARC_REPORTS_PROCESSED = Counter(
    "dmarc_reports_processed_total",
    "Total number of DMARC reports processed",
    ["status"]  # success, failed, duplicate
)

DMARC_RECORDS_INGESTED = Counter(
    "dmarc_records_ingested_total",
    "Total number of DMARC records ingested"
)

DMARC_EMAILS_FETCHED = Counter(
    "dmarc_emails_fetched_total",
    "Total number of emails fetched from IMAP",
    ["status"]  # success, failed
)

ALERTS_TRIGGERED = Counter(
    "alerts_triggered_total",
    "Total number of alerts triggered",
    ["alert_type", "severity"]
)

ALERTS_ACTIVE = Gauge(
    "alerts_active",
    "Number of currently active alerts",
    ["severity"]
)

# =============================================================================
# ML Metrics
# =============================================================================

ML_MODEL_TRAINING_DURATION = Histogram(
    "ml_model_training_duration_seconds",
    "ML model training duration in seconds",
    ["model_type"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

ML_PREDICTIONS_TOTAL = Counter(
    "ml_predictions_total",
    "Total number of ML predictions made",
    ["model_type", "is_anomaly"]
)

ANOMALIES_DETECTED = Counter(
    "anomalies_detected_total",
    "Total number of anomalies detected"
)

# =============================================================================
# Cache Metrics
# =============================================================================

CACHE_HITS = Counter(
    "cache_hits_total",
    "Total number of cache hits",
    ["cache_type"]
)

CACHE_MISSES = Counter(
    "cache_misses_total",
    "Total number of cache misses",
    ["cache_type"]
)

CACHE_SIZE = Gauge(
    "cache_size_bytes",
    "Current cache size in bytes",
    ["cache_type"]
)

# =============================================================================
# Celery Task Metrics
# =============================================================================

CELERY_TASKS_TOTAL = Counter(
    "celery_tasks_total",
    "Total number of Celery tasks",
    ["task_name", "status"]  # status: started, succeeded, failed, retried
)

CELERY_TASK_DURATION = Histogram(
    "celery_task_duration_seconds",
    "Celery task duration in seconds",
    ["task_name"],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120, 300]
)

CELERY_QUEUE_LENGTH = Gauge(
    "celery_queue_length",
    "Number of tasks in Celery queue",
    ["queue_name"]
)

# =============================================================================
# System Info
# =============================================================================

APP_INFO = Info(
    "dmarc_dashboard",
    "DMARC Dashboard application information"
)

# Set app info on module load
APP_INFO.info({
    "version": "2.0.0",
    "python_version": "3.11",
    "framework": "fastapi"
})

# =============================================================================
# Metrics Endpoint
# =============================================================================

@metrics_router.get("/metrics", include_in_schema=False)
async def metrics():
    """
    Prometheus metrics endpoint

    Returns all application metrics in Prometheus text format.
    This endpoint should be scraped by Prometheus.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# =============================================================================
# Middleware for HTTP Metrics
# =============================================================================

async def metrics_middleware(request, call_next):
    """
    Middleware to collect HTTP request metrics
    """
    method = request.method
    # Normalize endpoint path to avoid high cardinality
    path = request.url.path

    # Normalize paths with IDs to reduce cardinality
    # e.g., /api/reports/123 -> /api/reports/{id}
    path_parts = path.split("/")
    normalized_parts = []
    for part in path_parts:
        # Check if part looks like an ID (UUID or numeric)
        if part.isdigit() or (len(part) == 36 and "-" in part):
            normalized_parts.append("{id}")
        else:
            normalized_parts.append(part)
    endpoint = "/".join(normalized_parts)

    # Track in-progress requests
    HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

    start_time = time.time()

    try:
        response = await call_next(request)
        status_code = str(response.status_code)

        # Record metrics
        duration = time.time() - start_time
        HTTP_REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).observe(duration)

        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()

        return response

    except Exception as e:
        # Record error metrics
        duration = time.time() - start_time
        HTTP_REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint,
            status_code="500"
        ).observe(duration)

        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status_code="500"
        ).inc()

        raise

    finally:
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()


# =============================================================================
# Helper Functions for Business Metrics
# =============================================================================

def record_report_processed(status: str = "success"):
    """Record a DMARC report processing event"""
    DMARC_REPORTS_PROCESSED.labels(status=status).inc()


def record_records_ingested(count: int):
    """Record the number of DMARC records ingested"""
    DMARC_RECORDS_INGESTED.inc(count)


def record_email_fetch(status: str = "success"):
    """Record an email fetch event"""
    DMARC_EMAILS_FETCHED.labels(status=status).inc()


def record_alert_triggered(alert_type: str, severity: str):
    """Record an alert trigger event"""
    ALERTS_TRIGGERED.labels(alert_type=alert_type, severity=severity).inc()


def update_active_alerts(severity: str, count: int):
    """Update the gauge for active alerts"""
    ALERTS_ACTIVE.labels(severity=severity).set(count)


def record_cache_hit(cache_type: str):
    """Record a cache hit"""
    CACHE_HITS.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str):
    """Record a cache miss"""
    CACHE_MISSES.labels(cache_type=cache_type).inc()


def record_celery_task(task_name: str, status: str, duration: float = None):
    """Record a Celery task event"""
    CELERY_TASKS_TOTAL.labels(task_name=task_name, status=status).inc()
    if duration is not None:
        CELERY_TASK_DURATION.labels(task_name=task_name).observe(duration)


def record_anomaly_detected():
    """Record an anomaly detection event"""
    ANOMALIES_DETECTED.inc()


def record_ml_prediction(model_type: str, is_anomaly: bool):
    """Record an ML prediction"""
    ML_PREDICTIONS_TOTAL.labels(
        model_type=model_type,
        is_anomaly=str(is_anomaly).lower()
    ).inc()
