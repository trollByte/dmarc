from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import get_db, check_db_connection
from app.api.routes import router as api_router
from app.services.scheduler import start_scheduler, stop_scheduler
from app.logging_config import setup_logging, log_requests_middleware
from app.error_handlers import register_error_handlers
from app.middleware.rate_limit import limiter, rate_limit_handler, SlowAPIMiddleware
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],  # Configure allowed origins in production
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

# Include API router
app.include_router(api_router)


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
