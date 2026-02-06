from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import get_db, check_db_connection
from app.api.routes import router as api_router
from app.api.auth_routes import router as auth_router
from app.api.user_routes import router as user_router
from app.api.alert_routes import router as alert_router
from app.api.analytics_routes import router as analytics_router
from app.api.advisor_routes import router as advisor_router
from app.api.threat_intel_routes import router as threat_intel_router
from app.api.dashboard_routes import router as dashboard_router
from app.api.oauth_routes import router as oauth_router
from app.api.export_routes import router as export_router
from app.api.totp_routes import router as totp_router
from app.api.audit_routes import router as audit_router
from app.api.retention_routes import router as retention_router
from app.api.generator_routes import router as generator_router
from app.api.webhook_routes import router as webhook_router
from app.api.dns_monitor_routes import router as dns_monitor_router
from app.api.mta_sts_routes import router as mta_sts_router
from app.api.tls_rpt_routes import router as tls_rpt_router
from app.api.bimi_routes import router as bimi_router
from app.api.scheduled_reports_routes import router as scheduled_reports_router
from app.api.saml_routes import router as saml_router
from app.api.notification_routes import router as notification_router
from app.api.saved_view_routes import router as saved_view_router
from app.metrics import metrics_router, metrics_middleware
from app.services.scheduler import start_scheduler, stop_scheduler
from app.logging_config import setup_logging, log_requests_middleware
from app.error_handlers import register_error_handlers
from app.middleware.rate_limit import limiter, rate_limit_handler, SlowAPIMiddleware
from app.middleware.security import SecurityHeadersMiddleware, RequestSizeLimitMiddleware
from slowapi.errors import RateLimitExceeded

settings = get_settings()

# Configure production logging with rotation
setup_logging(
    log_level=settings.log_level,
    log_dir=settings.log_dir,
    app_name="dmarc-api",
    enable_json=settings.log_json
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks"""
    # Startup
    logger.info("Starting application...")

    # Validate JWT secret is configured in non-debug mode
    if not settings.debug and not settings.jwt_secret_key:
        raise RuntimeError(
            "JWT_SECRET_KEY must be set in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )

    start_scheduler()
    logger.info("Background scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    stop_scheduler()
    logger.info("Background scheduler stopped")


app = FastAPI(
    title=settings.app_name,
    description="DMARC Aggregate Report Processor API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,
)

# Add security headers middleware (added first, runs last)
if not settings.debug:
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=settings.enable_hsts,
        frame_options="DENY",
    )

# Add request size limit middleware
app.add_middleware(
    RequestSizeLimitMiddleware,
    max_content_length=settings.max_request_size
)

# Add CORS middleware
cors_origins = settings.cors_origins if settings.cors_origins else (["*"] if settings.debug else [])
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

# Register error handlers
register_error_handlers(app)

# Add request logging middleware
if settings.enable_request_logging:
    app.middleware("http")(log_requests_middleware)

# Include API routers
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(alert_router)
app.include_router(analytics_router)
app.include_router(advisor_router)
app.include_router(threat_intel_router)
app.include_router(dashboard_router)
app.include_router(oauth_router)
app.include_router(export_router)
app.include_router(totp_router)
app.include_router(audit_router)
app.include_router(retention_router)
app.include_router(generator_router)
app.include_router(webhook_router)
app.include_router(dns_monitor_router)
app.include_router(mta_sts_router)
app.include_router(tls_rpt_router)
app.include_router(bimi_router)
app.include_router(scheduled_reports_router)
app.include_router(saml_router)
app.include_router(notification_router)
app.include_router(saved_view_router)
app.include_router(metrics_router)

# Add metrics collection middleware
app.middleware("http")(metrics_middleware)


@app.get("/")
async def root():
    """Root endpoint"""
    logger.info("Root endpoint accessed")
    return {
        "message": "DMARC Report Processor API",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with database connectivity test"""
    db_connected = check_db_connection()

    logger.debug("Health check performed", extra={"db_connected": db_connected})

    return {
        "status": "healthy" if db_connected else "unhealthy",
        "service": settings.app_name,
        "database": "connected" if db_connected else "disconnected"
    }


@app.get("/db-test")
async def database_test(db: Session = Depends(get_db)):
    """Test database connection with a simple query"""
    try:
        result = db.execute(text("SELECT version()"))
        version = result.scalar()

        logger.info("Database test successful")

        return {
            "status": "success",
            "message": "Database connection successful",
            "postgres_version": version
        }
    except Exception as e:
        logger.error(f"Database test failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }
