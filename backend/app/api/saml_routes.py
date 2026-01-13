"""
SAML SSO API routes.

Endpoints:
- GET /saml/providers - List SAML providers
- POST /saml/providers - Create provider (admin)
- PUT /saml/providers/{id} - Update provider (admin)
- DELETE /saml/providers/{id} - Delete provider (admin)
- GET /saml/metadata - Get SP metadata
- GET /saml/login/{provider_id} - Initiate SSO login
- POST /saml/acs - Assertion Consumer Service (callback)
- GET /saml/slo - Single Logout
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Form, Request, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.dependencies.auth import get_current_user, require_role
from app.services.auth_service import AuthService
from app.services.saml_service import SAMLService, NameIDFormat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saml", tags=["SAML SSO"])


# ==================== Schemas ====================

class CreateProviderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    entity_id: str = Field(..., description="IdP Entity ID")
    sso_url: str = Field(..., description="IdP SSO URL")
    x509_cert: str = Field(..., description="IdP X.509 certificate")
    slo_url: Optional[str] = Field(None, description="IdP SLO URL")
    attribute_mapping: Optional[dict] = Field(None, description="SAML attribute to user field mapping")
    name_id_format: str = Field(default=NameIDFormat.EMAIL.value)
    auto_provision_users: bool = True
    default_role: str = Field(default="viewer")
    admin_groups: Optional[List[str]] = Field(None, description="Groups that grant admin role")
    sign_requests: bool = False
    want_assertions_signed: bool = True
    allow_idp_initiated: bool = False


class UpdateProviderRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    sso_url: Optional[str] = None
    slo_url: Optional[str] = None
    x509_cert: Optional[str] = None
    attribute_mapping: Optional[dict] = None
    name_id_format: Optional[str] = None
    auto_provision_users: Optional[bool] = None
    default_role: Optional[str] = None
    admin_groups: Optional[List[str]] = None
    sign_requests: Optional[bool] = None
    want_assertions_signed: Optional[bool] = None
    allow_idp_initiated: Optional[bool] = None


class ProviderResponse(BaseModel):
    id: UUID
    name: str
    entity_id: str
    is_active: bool
    sso_url: str
    slo_url: Optional[str]
    name_id_format: str
    auto_provision_users: bool
    default_role: str
    admin_groups: List[str]
    sign_requests: bool
    want_assertions_signed: bool
    allow_idp_initiated: bool
    created_at: str
    updated_at: str


class ProviderListResponse(BaseModel):
    id: UUID
    name: str
    entity_id: str
    is_active: bool
    sso_url: str


class LoginResponse(BaseModel):
    redirect_url: str
    request_id: str


# ==================== Routes ====================

@router.get(
    "/providers",
    response_model=List[ProviderListResponse],
    status_code=status.HTTP_200_OK,
    summary="List SAML providers"
)
async def list_providers(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """List available SAML identity providers."""
    service = SAMLService(db)
    providers = service.get_providers(active_only=active_only)

    return [
        ProviderListResponse(
            id=p.id,
            name=p.name,
            entity_id=p.entity_id,
            is_active=p.is_active,
            sso_url=p.sso_url,
        )
        for p in providers
    ]


@router.post(
    "/providers",
    response_model=ProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create SAML provider"
)
async def create_provider(
    request: CreateProviderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Create a new SAML identity provider configuration.

    **Admin only.**

    Required information from your IdP:
    - Entity ID
    - SSO URL
    - X.509 Certificate
    """
    service = SAMLService(db)

    try:
        provider = service.create_provider(
            name=request.name,
            entity_id=request.entity_id,
            sso_url=request.sso_url,
            x509_cert=request.x509_cert,
            slo_url=request.slo_url,
            attribute_mapping=request.attribute_mapping,
            name_id_format=request.name_id_format,
            auto_provision_users=request.auto_provision_users,
            default_role=request.default_role,
            admin_groups=request.admin_groups,
            sign_requests=request.sign_requests,
            want_assertions_signed=request.want_assertions_signed,
            allow_idp_initiated=request.allow_idp_initiated,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        entity_id=provider.entity_id,
        is_active=provider.is_active,
        sso_url=provider.sso_url,
        slo_url=provider.slo_url,
        name_id_format=provider.name_id_format,
        auto_provision_users=provider.auto_provision_users,
        default_role=provider.default_role,
        admin_groups=provider.admin_groups,
        sign_requests=provider.sign_requests,
        want_assertions_signed=provider.want_assertions_signed,
        allow_idp_initiated=provider.allow_idp_initiated,
        created_at=provider.created_at.isoformat(),
        updated_at=provider.updated_at.isoformat(),
    )


@router.get(
    "/providers/{provider_id}",
    response_model=ProviderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get provider details"
)
async def get_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Get SAML provider details. Admin only."""
    service = SAMLService(db)
    provider = service.get_provider(provider_id)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        entity_id=provider.entity_id,
        is_active=provider.is_active,
        sso_url=provider.sso_url,
        slo_url=provider.slo_url,
        name_id_format=provider.name_id_format,
        auto_provision_users=provider.auto_provision_users,
        default_role=provider.default_role,
        admin_groups=provider.admin_groups,
        sign_requests=provider.sign_requests,
        want_assertions_signed=provider.want_assertions_signed,
        allow_idp_initiated=provider.allow_idp_initiated,
        created_at=provider.created_at.isoformat(),
        updated_at=provider.updated_at.isoformat(),
    )


@router.put(
    "/providers/{provider_id}",
    response_model=ProviderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update provider"
)
async def update_provider(
    provider_id: UUID,
    request: UpdateProviderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a SAML provider. Admin only."""
    service = SAMLService(db)
    provider = service.update_provider(
        provider_id=provider_id,
        **request.dict(exclude_unset=True),
    )

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    return ProviderResponse(
        id=provider.id,
        name=provider.name,
        entity_id=provider.entity_id,
        is_active=provider.is_active,
        sso_url=provider.sso_url,
        slo_url=provider.slo_url,
        name_id_format=provider.name_id_format,
        auto_provision_users=provider.auto_provision_users,
        default_role=provider.default_role,
        admin_groups=provider.admin_groups,
        sign_requests=provider.sign_requests,
        want_assertions_signed=provider.want_assertions_signed,
        allow_idp_initiated=provider.allow_idp_initiated,
        created_at=provider.created_at.isoformat(),
        updated_at=provider.updated_at.isoformat(),
    )


@router.delete(
    "/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete provider"
)
async def delete_provider(
    provider_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Delete a SAML provider. Admin only."""
    service = SAMLService(db)

    if not service.delete_provider(provider_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )


@router.get(
    "/metadata",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    summary="Get SP metadata"
)
async def get_sp_metadata(
    db: Session = Depends(get_db),
):
    """
    Get Service Provider SAML metadata.

    Provide this metadata to your Identity Provider to configure the trust relationship.
    """
    service = SAMLService(db)
    metadata = service.generate_sp_metadata()

    return Response(
        content=metadata,
        media_type="application/xml",
        headers={
            "Content-Disposition": "attachment; filename=saml-metadata.xml"
        }
    )


@router.get(
    "/login/{provider_id}",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate SSO login"
)
async def initiate_login(
    provider_id: UUID,
    redirect_url: Optional[str] = Query(None, description="URL to redirect after login"),
    db: Session = Depends(get_db),
):
    """
    Initiate SAML SSO login flow.

    Returns the IdP redirect URL. The client should redirect the user to this URL.
    """
    service = SAMLService(db)
    request = service.create_auth_request(
        provider_id=provider_id,
        relay_state=redirect_url,
        redirect_url=redirect_url,
    )

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    return LoginResponse(
        redirect_url=request.redirect_url,
        request_id=request.id,
    )


@router.post(
    "/acs",
    status_code=status.HTTP_200_OK,
    summary="Assertion Consumer Service"
)
async def assertion_consumer_service(
    SAMLResponse: str = Form(...),
    RelayState: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    SAML Assertion Consumer Service callback.

    This endpoint receives the SAML response from the IdP after authentication.
    """
    service = SAMLService(db)
    result = service.process_response(SAMLResponse, RelayState)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.get("error", "Authentication failed")
        )

    # Generate JWT token
    if result.get("user_id"):
        # Get user from database to get role
        user = db.query(User).filter(User.id == result["user_id"]).first()
        if user:
            token = AuthService.create_access_token(
                user_id=str(user.id),
                username=user.username,
                role=user.role
            )

            # Redirect to frontend with token
            redirect_url = RelayState or "/"
            separator = "&" if "?" in redirect_url else "?"
            return RedirectResponse(
                url=f"{redirect_url}{separator}token={token}",
                status_code=status.HTTP_302_FOUND,
            )

    return result


@router.get(
    "/slo",
    status_code=status.HTTP_200_OK,
    summary="Single Logout"
)
async def single_logout(
    SAMLRequest: Optional[str] = Query(None),
    SAMLResponse: Optional[str] = Query(None),
    RelayState: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    SAML Single Logout endpoint.

    Handles logout requests and responses from the IdP.
    """
    # For now, just acknowledge the logout
    redirect_url = RelayState or "/"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
