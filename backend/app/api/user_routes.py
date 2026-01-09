"""
User management API routes (admin only).

Endpoints:
- POST /users - Create new user (admin only)
- GET /users - List all users (admin only)
- GET /users/{user_id} - Get user by ID
- PATCH /users/{user_id} - Update user (admin or self)
- DELETE /users/{user_id} - Delete user (admin only)
- POST /users/{user_id}/unlock - Unlock locked account (admin only)
- POST /users/me/change-password - Change own password
- POST /users/me/api-keys - Create API key
- GET /users/me/api-keys - List own API keys
- DELETE /users/me/api-keys/{key_id} - Delete API key
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID

from app.database import get_db
from app.models import User, UserAPIKey, UserRole
from app.services.auth_service import AuthService, PasswordValidationError
from app.dependencies.auth import get_current_user, require_admin
from app.schemas.auth_schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    UserChangePassword,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyInfo,
    UnlockAccountRequest,
)

router = APIRouter(prefix="/users", tags=["User Management"])


# ==================== User CRUD ====================

@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user (admin only)"
)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """
    Create a new user account (admin only - no self-registration).

    **Permissions:** Admin only

    **Password Policy:**
    - Minimum 12 characters
    - Must contain uppercase, lowercase, digit, and special character

    **Usage:**
    ```
    POST /users
    Authorization: Bearer <admin_token>
    {
        "username": "analyst1",
        "email": "analyst@example.com",
        "password": "SecurePass123!",
        "role": "analyst"
    }
    ```

    **Errors:**
    - 400: Username/email already exists or password policy violation
    - 403: Not admin
    """
    # Check if username exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )

    # Validate password policy
    try:
        AuthService.validate_password_policy(user_data.password)
    except PasswordValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Hash password
    hashed_password = AuthService.hash_password(user_data.password)

    # Create user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.get(
    "",
    response_model=UserListResponse,
    summary="List all users (admin only)"
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """
    List all users with pagination and filtering (admin only).

    **Permissions:** Admin only

    **Usage:**
    ```
    GET /users?page=1&page_size=50&role=analyst&is_active=true
    Authorization: Bearer <admin_token>
    ```
    """
    query = db.query(User)

    # Apply filters
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    # Get total count
    total = query.count()

    # Paginate
    offset = (page - 1) * page_size
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    return UserListResponse(
        users=users,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID"
)
async def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get user information by ID.

    **Permissions:**
    - User can view own profile
    - Admin can view any profile
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check permissions (self or admin)
    if current_user.id != user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user"
        )

    return user


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user"
)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update user information.

    **Permissions:**
    - User can update own email
    - Admin can update email, role, and is_active for any user

    **Usage:**
    ```
    PATCH /users/{user_id}
    Authorization: Bearer <token>
    {
        "email": "newemail@example.com",
        "role": "admin"  // admin only
    }
    ```
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check permissions
    is_self = current_user.id == user.id
    is_admin = current_user.role == UserRole.ADMIN

    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user"
        )

    # Update email (self or admin)
    if user_data.email is not None:
        # Check if email already exists
        existing = db.query(User).filter(
            User.email == user_data.email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
        user.email = user_data.email

    # Update role (admin only)
    if user_data.role is not None:
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change user roles"
            )
        user.role = user_data.role

    # Update is_active (admin only)
    if user_data.is_active is not None:
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change account status"
            )
        user.is_active = user_data.is_active

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete user (admin only)"
)
async def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """
    Delete user account (admin only).

    **Permissions:** Admin only

    **Note:** Cannot delete own account

    **Usage:**
    ```
    DELETE /users/{user_id}
    Authorization: Bearer <admin_token>
    ```
    """
    # Prevent self-deletion
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete own account"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()

    return {"message": f"User {user.username} deleted successfully"}


@router.post(
    "/{user_id}/unlock",
    response_model=UserResponse,
    summary="Unlock locked account (admin only)"
)
async def unlock_account(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin())
):
    """
    Unlock a locked user account (admin only).

    **Permissions:** Admin only

    **When to use:** Account locked due to too many failed login attempts

    **Usage:**
    ```
    POST /users/{user_id}/unlock
    Authorization: Bearer <admin_token>
    ```
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is not locked"
        )

    user.is_locked = False
    user.failed_login_attempts = 0
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return user


# ==================== Password Management ====================

@router.post(
    "/me/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change own password"
)
async def change_password(
    password_data: UserChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Change own password.

    **Usage:**
    ```
    POST /users/me/change-password
    Authorization: Bearer <token>
    {
        "current_password": "OldPass123!",
        "new_password": "NewSecurePass456!"
    }
    ```

    **Errors:**
    - 400: Current password incorrect or new password doesn't meet policy
    """
    # Verify current password
    if not AuthService.verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Validate new password
    try:
        AuthService.validate_password_policy(password_data.new_password)
    except PasswordValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Hash and update password
    current_user.hashed_password = AuthService.hash_password(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()

    # Revoke all refresh tokens (force re-login)
    AuthService.revoke_all_user_tokens(db, str(current_user.id))

    return {"message": "Password changed successfully. Please login again."}


# ==================== API Key Management ====================

@router.post(
    "/me/api-keys",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key"
)
async def create_api_key(
    key_data: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new API key for programmatic access.

    **IMPORTANT:** API key is only shown once at creation. Save it securely!

    **Usage:**
    ```
    POST /users/me/api-keys
    Authorization: Bearer <token>
    {
        "key_name": "Production Server",
        "expires_days": 90
    }
    ```

    **Response:**
    ```json
    {
        "id": "uuid",
        "key_name": "Production Server",
        "api_key": "dmarc_abc123...",  // SAVE THIS - NEVER SHOWN AGAIN
        "key_prefix": "dmarc_ab",
        "expires_at": "2024-04-01T00:00:00",
        "created_at": "2024-01-01T00:00:00"
    }
    ```
    """
    # Generate API key
    api_key, key_hash, key_prefix = AuthService.generate_api_key()

    # Calculate expiration
    expires_at = None
    if key_data.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=key_data.expires_days)

    # Create database record
    api_key_obj = UserAPIKey(
        user_id=current_user.id,
        key_name=key_data.key_name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        expires_at=expires_at,
        is_active=True
    )

    db.add(api_key_obj)
    db.commit()
    db.refresh(api_key_obj)

    # Return response with full API key (only time it's shown)
    return APIKeyResponse(
        id=api_key_obj.id,
        key_name=api_key_obj.key_name,
        api_key=api_key,  # Full key - only shown once
        key_prefix=key_prefix,
        expires_at=expires_at,
        created_at=api_key_obj.created_at
    )


@router.get(
    "/me/api-keys",
    response_model=list[APIKeyInfo],
    summary="List own API keys"
)
async def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all API keys for current user (without showing the actual keys).

    **Usage:**
    ```
    GET /users/me/api-keys
    Authorization: Bearer <token>
    ```
    """
    keys = db.query(UserAPIKey).filter(
        UserAPIKey.user_id == current_user.id
    ).order_by(UserAPIKey.created_at.desc()).all()

    return keys


@router.delete(
    "/me/api-keys/{key_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete API key"
)
async def delete_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete (revoke) API key.

    **Usage:**
    ```
    DELETE /users/me/api-keys/{key_id}
    Authorization: Bearer <token>
    ```
    """
    api_key = db.query(UserAPIKey).filter(
        UserAPIKey.id == key_id,
        UserAPIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    db.delete(api_key)
    db.commit()

    return {"message": f"API key '{api_key.key_name}' deleted successfully"}
