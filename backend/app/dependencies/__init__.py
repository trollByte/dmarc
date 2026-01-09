"""
FastAPI dependencies for the DMARC Dashboard.
"""

from app.dependencies.auth import (
    get_current_user,
    get_current_user_optional,
    require_admin,
    require_analyst_or_admin,
    require_role,
    AuthDependencies,
)

__all__ = [
    "get_current_user",
    "get_current_user_optional",
    "require_admin",
    "require_analyst_or_admin",
    "require_role",
    "AuthDependencies",
]
