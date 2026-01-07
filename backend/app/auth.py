"""
API Authentication

Simple API key authentication for protecting endpoints.
In production, API keys should be stored securely (environment variables, secrets manager).
"""
import logging
from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.config import get_settings

logger = logging.getLogger(__name__)

# API Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Verify API key from request header

    Args:
        api_key: API key from X-API-Key header

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    settings = get_settings()

    # If authentication is disabled (development mode), allow all requests
    if not settings.require_api_key:
        return "development"

    # Check if API key is provided
    if not api_key:
        logger.warning("API request without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # Validate API key
    valid_keys = settings.api_keys

    if not valid_keys:
        logger.error("No API keys configured but authentication is required")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication not properly configured"
        )

    if api_key not in valid_keys:
        logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    logger.debug("API key validated successfully")
    return api_key


# Optional authentication dependency
# Use this for endpoints that should be authenticated in production
def require_auth():
    """
    Dependency for endpoints that require authentication

    Usage:
        @router.get("/protected", dependencies=[Depends(require_auth())])
        async def protected_endpoint():
            ...
    """
    from fastapi import Depends
    return Depends(verify_api_key)
