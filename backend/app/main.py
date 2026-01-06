from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db
from app.api.routes import router as api_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="DMARC Aggregate Report Processor API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.app_name
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DMARC Report Processor API",
        "docs": "/docs"
    }
