"""
Webhook Management API routes.

Endpoints:
- GET /webhooks - List webhook endpoints
- POST /webhooks - Create webhook endpoint
- GET /webhooks/{id} - Get endpoint details
- PUT /webhooks/{id} - Update endpoint
- DELETE /webhooks/{id} - Delete endpoint
- POST /webhooks/{id}/test - Test webhook
- GET /webhooks/{id}/deliveries - Get delivery history
"""

import secrets
import logging
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.dependencies.auth import get_current_user, require_role
from app.services.webhook_service import WebhookService, WebhookEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ==================== Schemas ====================

class WebhookEndpointCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1, max_length=500)
    events: List[str] = Field(..., min_length=1)
    generate_secret: bool = Field(default=True)


class WebhookEndpointUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = Field(None, min_length=1, max_length=500)
    events: Optional[List[str]] = None
    is_enabled: Optional[bool] = None


class WebhookEndpointResponse(BaseModel):
    id: UUID
    name: str
    url: str
    is_enabled: bool
    events: List[str]
    max_retries: int
    success_count: int
    failure_count: int
    last_triggered_at: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    event_type: str
    success: Optional[bool] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    attempt_number: int
    created_at: str
    delivered_at: Optional[str] = None
    duration_ms: Optional[int] = None

    class Config:
        from_attributes = True


class WebhookSecretResponse(BaseModel):
    id: UUID
    name: str
    secret: str


# ==================== Routes ====================

@router.get(
    "",
    response_model=List[WebhookEndpointResponse],
    status_code=status.HTTP_200_OK,
    summary="List webhook endpoints"
)
async def list_endpoints(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List all configured webhook endpoints. Admin only."""
    service = WebhookService(db)
    endpoints = service.get_endpoints()

    return [
        WebhookEndpointResponse(
            id=e.id,
            name=e.name,
            url=e.url,
            is_enabled=e.is_enabled,
            events=e.events or [],
            max_retries=e.max_retries,
            success_count=e.success_count,
            failure_count=e.failure_count,
            last_triggered_at=e.last_triggered_at.isoformat() if e.last_triggered_at else None,
            created_at=e.created_at.isoformat(),
        )
        for e in endpoints
    ]


@router.post(
    "",
    response_model=WebhookSecretResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook endpoint"
)
async def create_endpoint(
    endpoint_data: WebhookEndpointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Create a new webhook endpoint. Admin only.

    **Available Events:**
    - alert.created
    - alert.acknowledged
    - alert.resolved
    - report.received
    - report.processed
    - threat.detected
    - threat.high_failure_rate
    - policy.recommendation
    - system.health_check
    """
    # Validate events
    valid_events = [e.value for e in WebhookEvent]
    for event in endpoint_data.events:
        if event not in valid_events:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event: {event}. Valid events: {valid_events}"
            )

    # Generate secret if requested
    secret = secrets.token_hex(32) if endpoint_data.generate_secret else None

    service = WebhookService(db)
    endpoint = service.create_endpoint(
        name=endpoint_data.name,
        url=endpoint_data.url,
        events=endpoint_data.events,
        secret=secret,
        created_by=current_user.id,
    )

    return WebhookSecretResponse(
        id=endpoint.id,
        name=endpoint.name,
        secret=secret or "No secret configured",
    )


@router.get(
    "/events",
    response_model=List[str],
    status_code=status.HTTP_200_OK,
    summary="List available events"
)
async def list_events(
    current_user: User = Depends(get_current_user),
):
    """List all available webhook event types."""
    return [e.value for e in WebhookEvent]


@router.get(
    "/{endpoint_id}",
    response_model=WebhookEndpointResponse,
    status_code=status.HTTP_200_OK,
    summary="Get endpoint details"
)
async def get_endpoint(
    endpoint_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get webhook endpoint details. Admin only."""
    service = WebhookService(db)
    endpoint = service.get_endpoint(endpoint_id)

    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found"
        )

    return WebhookEndpointResponse(
        id=endpoint.id,
        name=endpoint.name,
        url=endpoint.url,
        is_enabled=endpoint.is_enabled,
        events=endpoint.events or [],
        max_retries=endpoint.max_retries,
        success_count=endpoint.success_count,
        failure_count=endpoint.failure_count,
        last_triggered_at=endpoint.last_triggered_at.isoformat() if endpoint.last_triggered_at else None,
        created_at=endpoint.created_at.isoformat(),
    )


@router.put(
    "/{endpoint_id}",
    response_model=WebhookEndpointResponse,
    status_code=status.HTTP_200_OK,
    summary="Update endpoint"
)
async def update_endpoint(
    endpoint_id: UUID,
    endpoint_data: WebhookEndpointUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update a webhook endpoint. Admin only."""
    service = WebhookService(db)

    updates = endpoint_data.model_dump(exclude_unset=True)
    endpoint = service.update_endpoint(endpoint_id, **updates)

    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found"
        )

    return WebhookEndpointResponse(
        id=endpoint.id,
        name=endpoint.name,
        url=endpoint.url,
        is_enabled=endpoint.is_enabled,
        events=endpoint.events or [],
        max_retries=endpoint.max_retries,
        success_count=endpoint.success_count,
        failure_count=endpoint.failure_count,
        last_triggered_at=endpoint.last_triggered_at.isoformat() if endpoint.last_triggered_at else None,
        created_at=endpoint.created_at.isoformat(),
    )


@router.delete(
    "/{endpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete endpoint"
)
async def delete_endpoint(
    endpoint_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Delete a webhook endpoint. Admin only."""
    service = WebhookService(db)

    if not service.delete_endpoint(endpoint_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found"
        )


@router.post(
    "/{endpoint_id}/test",
    response_model=WebhookDeliveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Test webhook"
)
async def test_endpoint(
    endpoint_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Send a test webhook. Admin only."""
    service = WebhookService(db)
    endpoint = service.get_endpoint(endpoint_id)

    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found"
        )

    delivery = await service.test_endpoint(endpoint)

    return WebhookDeliveryResponse(
        id=delivery.id,
        event_type=delivery.event_type,
        success=delivery.success,
        status_code=delivery.status_code,
        error_message=delivery.error_message,
        attempt_number=delivery.attempt_number,
        created_at=delivery.created_at.isoformat(),
        delivered_at=delivery.delivered_at.isoformat() if delivery.delivered_at else None,
        duration_ms=delivery.duration_ms,
    )


@router.get(
    "/{endpoint_id}/deliveries",
    response_model=List[WebhookDeliveryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get delivery history"
)
async def get_deliveries(
    endpoint_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get webhook delivery history. Admin only."""
    service = WebhookService(db)
    deliveries = service.get_deliveries(endpoint_id=endpoint_id, limit=limit)

    return [
        WebhookDeliveryResponse(
            id=d.id,
            event_type=d.event_type,
            success=d.success,
            status_code=d.status_code,
            error_message=d.error_message,
            attempt_number=d.attempt_number,
            created_at=d.created_at.isoformat(),
            delivered_at=d.delivered_at.isoformat() if d.delivered_at else None,
            duration_ms=d.duration_ms,
        )
        for d in deliveries
    ]
