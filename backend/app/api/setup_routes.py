"""
Setup wizard API routes.

These endpoints are ONLY accessible when the application has not yet been
configured (i.e., no .setup_complete marker file exists). Once setup completes,
all endpoints return 404.

Endpoints:
- GET  /setup/status     - Check if setup is needed
- POST /setup/initialize - Run first-time setup (create admin, write marker)
"""

import os
import time
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models import User, UserRole
from app.services.auth_service import AuthService
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/setup", tags=["Setup"])

# Marker file location — on the mounted volume so it persists across restarts
SETUP_MARKER = os.environ.get("SETUP_MARKER_PATH", "/app/.setup_complete")


def is_configured() -> bool:
    """Check if setup has already been completed."""
    return os.path.exists(SETUP_MARKER)


def require_unconfigured():
    """Dependency that blocks access if setup is already complete."""
    if is_configured():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SetupStatusResponse(BaseModel):
    configured: bool


class SetupInitializeRequest(BaseModel):
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)
    email_host: str = ""
    email_user: str = ""
    email_password: str = ""
    maxmind_license_key: str = ""


class SetupInitializeResponse(BaseModel):
    success: bool
    message: str
    login_url: str = "/"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    response_model=SetupStatusResponse,
    summary="Check if initial setup is needed",
)
async def setup_status():
    """
    Returns whether the application has been configured.

    If configured is false, the frontend should show the setup wizard.
    This endpoint is always accessible (no auth required).
    """
    return SetupStatusResponse(configured=is_configured())


@router.post(
    "/initialize",
    response_model=SetupInitializeResponse,
    summary="Run first-time setup",
    dependencies=[Depends(require_unconfigured)],
)
@limiter.limit("5/minute")
async def setup_initialize(
    request: Request,
    body: SetupInitializeRequest,
    db: Session = Depends(get_db),
):
    """
    Perform first-time application setup:
    1. Create admin user
    2. Write setup marker file

    This endpoint is only accessible before setup completes.
    After the first successful call, it returns 404 forever.
    """
    # Check if an admin user already exists (safety check)
    existing_admin = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
    if existing_admin:
        # Admin already exists — just write the marker and return success
        _write_marker()
        return SetupInitializeResponse(
            success=True,
            message="Admin user already exists. Setup marked as complete.",
        )

    # Create admin user
    try:
        admin = User(
            email=body.admin_email,
            username=body.admin_email.split("@")[0],
            hashed_password=AuthService.hash_password(body.admin_password),
            is_active=True,
            is_superuser=True,
            role=UserRole.ADMIN.value,
        )
        db.add(admin)
        db.commit()
        logger.info("Setup wizard created admin user: %s", body.admin_email)
    except Exception as e:
        db.rollback()
        logger.error("Setup failed to create admin user: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create admin user: {str(e)}",
        )

    # Write setup marker
    _write_marker()

    return SetupInitializeResponse(
        success=True,
        message="Setup complete. You can now log in.",
    )


def _write_marker() -> None:
    """Write the .setup_complete marker file."""
    try:
        os.makedirs(os.path.dirname(SETUP_MARKER) or ".", exist_ok=True)
        with open(SETUP_MARKER, "w") as f:
            f.write(f"Setup completed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        logger.info("Setup marker written to %s", SETUP_MARKER)
    except OSError as e:
        logger.warning("Could not write setup marker: %s", e)
