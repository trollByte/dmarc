"""
FastAPI dependencies for authentication and authorization.

Provides dependency injection functions for:
- JWT token validation
- API key validation
- Role-based access control (RBAC)
- User retrieval from request
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.services.auth_service import AuthService

# HTTP Bearer security scheme for JWT
bearer_scheme = HTTPBearer(auto_error=False)


class AuthDependencies:
    """Authentication and authorization dependencies for FastAPI"""

    @staticmethod
    async def get_current_user(
        credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        db: Session = Depends(get_db)
    ) -> User:
        """
        Get current user from JWT token or API key.

        Supports two authentication methods:
        1. JWT Bearer token: Authorization: Bearer <token>
        2. API Key: X-API-Key: <api_key>

        Args:
            credentials: HTTP Bearer token from Authorization header
            x_api_key: API key from X-API-Key header
            db: Database session

        Returns:
            Authenticated User object

        Raises:
            HTTPException: 401 if authentication fails
        """
        # Try JWT authentication first
        if credentials:
            token = credentials.credentials
            try:
                payload = AuthService.decode_token(token)

                # Validate token type
                if payload.get("type") != "access":
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token type"
                    )

                # Get user from database
                user_id = payload.get("sub")
                if not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token payload"
                    )

                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User not found"
                    )

                # Check user status
                if not user.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User account is inactive"
                    )

                if user.is_locked:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User account is locked"
                    )

                return user

            except JWTError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Could not validate credentials: {str(e)}"
                )

        # Try API key authentication
        elif x_api_key:
            user = AuthService.validate_api_key(db, x_api_key)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired API key"
                )
            return user

        # No authentication provided
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No authentication credentials provided",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @staticmethod
    async def get_current_user_optional(
        credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        db: Session = Depends(get_db)
    ) -> Optional[User]:
        """
        Get current user if authenticated, otherwise return None.

        Useful for endpoints that have different behavior for authenticated users
        but don't require authentication.

        Args:
            credentials: HTTP Bearer token
            x_api_key: API key
            db: Database session

        Returns:
            User if authenticated, None otherwise
        """
        try:
            return await AuthDependencies.get_current_user(credentials, x_api_key, db)
        except HTTPException:
            return None

    @staticmethod
    def require_role(*allowed_roles: UserRole):
        """
        Create dependency that requires user to have one of the specified roles.

        Usage:
            @router.get("/admin-only")
            async def admin_endpoint(user: User = Depends(require_role(UserRole.ADMIN))):
                ...

        Args:
            *allowed_roles: One or more UserRole values

        Returns:
            Dependency function that validates user role
        """
        async def role_checker(
            user: User = Depends(AuthDependencies.get_current_user)
        ) -> User:
            if user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied. Required role: {', '.join(r.value for r in allowed_roles)}"
                )
            return user

        return role_checker

    @staticmethod
    def require_admin():
        """
        Require user to have admin role.

        Usage:
            @router.post("/users")
            async def create_user(user: User = Depends(require_admin())):
                ...

        Returns:
            Dependency function that requires admin role
        """
        return AuthDependencies.require_role(UserRole.ADMIN)

    @staticmethod
    def require_analyst_or_admin():
        """
        Require user to have analyst or admin role.

        Usage:
            @router.post("/reports")
            async def process_report(user: User = Depends(require_analyst_or_admin())):
                ...

        Returns:
            Dependency function that requires analyst or admin role
        """
        return AuthDependencies.require_role(UserRole.ANALYST, UserRole.ADMIN)


# Convenience exports for simpler imports
get_current_user = AuthDependencies.get_current_user
get_current_user_optional = AuthDependencies.get_current_user_optional
require_admin = AuthDependencies.require_admin
require_analyst_or_admin = AuthDependencies.require_analyst_or_admin
require_role = AuthDependencies.require_role
