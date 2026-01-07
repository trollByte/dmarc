"""
API Key Authentication Middleware

Provides API key-based authentication for FastAPI endpoints.
Uses X-API-Key header for authentication.
"""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.config import get_settings

# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Validate API key from request header

    Args:
        api_key: API key from X-API-Key header

    Returns:
        str: The validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    settings = get_settings()

    # If API key requirement is disabled, allow all requests
    if not settings.require_api_key:
        return "api-key-not-required"

    # Check if API key is provided
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Get valid API keys from settings
    valid_keys = [key.strip() for key in settings.api_keys.split(",") if key.strip()]

    # Check if provided key is valid
    if api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key
