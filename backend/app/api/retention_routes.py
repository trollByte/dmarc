"""
Data Retention API routes.

Endpoints:
- GET /retention/policies - List retention policies
- POST /retention/policies - Create retention policy
- GET /retention/policies/{id} - Get policy details
- PUT /retention/policies/{id} - Update policy
- DELETE /retention/policies/{id} - Delete policy
- POST /retention/policies/{id}/execute - Execute single policy
- POST /retention/execute - Execute all enabled policies
- GET /retention/policies/{id}/preview - Preview what would be deleted
- GET /retention/logs - Get execution logs
- GET /retention/stats - Get retention statistics
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, RetentionTarget
from app.dependencies.auth import get_current_user, require_role
from app.services.retention_service import RetentionService, RetentionError
from app.schemas.retention_schemas import (
    RetentionPolicyCreate,
    RetentionPolicyUpdate,
    RetentionPolicyResponse,
    RetentionLogResponse,
    RetentionPreviewResponse,
    RetentionStatsResponse,
    RetentionExecuteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/retention", tags=["Data Retention"])


@router.get(
    "/policies",
    response_model=list[RetentionPolicyResponse],
    status_code=status.HTTP_200_OK,
    summary="List retention policies"
)
async def list_policies(
    target: str = Query(None, description="Filter by target type"),
    is_enabled: bool = Query(None, description="Filter by enabled status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    List all retention policies.

    **Admin only.**

    **Available Targets:**
    - dmarc_reports
    - dmarc_records
    - audit_logs
    - alert_history
    - threat_intel_cache
    - analytics_cache
    - ml_predictions
    - password_reset_tokens
    - refresh_tokens
    """
    service = RetentionService(db)
    policies = service.get_policies(target=target, is_enabled=is_enabled)

    return [RetentionPolicyResponse.model_validate(p) for p in policies]


@router.post(
    "/policies",
    response_model=RetentionPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create retention policy"
)
async def create_policy(
    policy_data: RetentionPolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Create a new retention policy.

    **Admin only.**

    **Example:**
    ```json
    {
        "name": "DMARC Reports - 1 Year",
        "target": "dmarc_reports",
        "retention_days": 365,
        "description": "Keep DMARC reports for 1 year",
        "is_enabled": true
    }
    ```
    """
    service = RetentionService(db)

    try:
        policy = service.create_policy(
            name=policy_data.name,
            target=policy_data.target,
            retention_days=policy_data.retention_days,
            description=policy_data.description,
            filters=policy_data.filters,
            is_enabled=policy_data.is_enabled,
            created_by=current_user.id,
        )
    except RetentionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return RetentionPolicyResponse.model_validate(policy)


@router.get(
    "/policies/{policy_id}",
    response_model=RetentionPolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get policy details"
)
async def get_policy(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Get details of a specific retention policy.

    **Admin only.**
    """
    service = RetentionService(db)
    policy = service.get_policy(policy_id)

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )

    return RetentionPolicyResponse.model_validate(policy)


@router.put(
    "/policies/{policy_id}",
    response_model=RetentionPolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Update retention policy"
)
async def update_policy(
    policy_id: UUID,
    policy_data: RetentionPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Update an existing retention policy.

    **Admin only.**
    """
    service = RetentionService(db)

    try:
        updates = policy_data.model_dump(exclude_unset=True)
        policy = service.update_policy(policy_id, **updates)
    except RetentionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return RetentionPolicyResponse.model_validate(policy)


@router.delete(
    "/policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete retention policy"
)
async def delete_policy(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Delete a retention policy.

    **Admin only.**

    Note: This does not restore any data that was already deleted.
    """
    service = RetentionService(db)

    try:
        service.delete_policy(policy_id)
    except RetentionError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/policies/{policy_id}/execute",
    response_model=RetentionLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute single policy"
)
async def execute_policy(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Execute a specific retention policy immediately.

    **Admin only.**

    **Warning:** This will permanently delete data older than
    the policy's retention period.
    """
    service = RetentionService(db)
    policy = service.get_policy(policy_id)

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )

    log = service.execute_policy(policy)

    return RetentionLogResponse.model_validate(log)


@router.post(
    "/execute",
    response_model=RetentionExecuteResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute all enabled policies"
)
async def execute_all_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Execute all enabled retention policies.

    **Admin only.**

    **Warning:** This will permanently delete data based on
    all enabled retention policies.
    """
    service = RetentionService(db)
    logs = service.execute_all_policies()

    total_deleted = sum(log.records_deleted for log in logs)

    return RetentionExecuteResponse(
        executed=len(logs),
        total_deleted=total_deleted,
        logs=[RetentionLogResponse.model_validate(log) for log in logs]
    )


@router.get(
    "/policies/{policy_id}/preview",
    response_model=RetentionPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview policy execution"
)
async def preview_policy(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Preview what would be deleted if a policy is executed.

    **Admin only.**

    Returns the count of records that would be deleted without
    actually deleting anything.
    """
    service = RetentionService(db)
    policy = service.get_policy(policy_id)

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found"
        )

    preview = service.preview_policy(policy)

    if "error" in preview:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=preview["error"]
        )

    return RetentionPreviewResponse(**preview)


@router.get(
    "/logs",
    response_model=list[RetentionLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get execution logs"
)
async def get_logs(
    policy_id: UUID = Query(None, description="Filter by policy"),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    limit: int = Query(100, ge=10, le=500, description="Maximum results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Get retention policy execution logs.

    **Admin only.**
    """
    service = RetentionService(db)
    logs = service.get_logs(policy_id=policy_id, days=days, limit=limit)

    return [RetentionLogResponse.model_validate(log) for log in logs]


@router.get(
    "/stats",
    response_model=RetentionStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get retention statistics"
)
async def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Get retention statistics.

    **Admin only.**

    Returns:
    - Policy counts (total, enabled)
    - Total records deleted
    - Current data sizes by target
    """
    service = RetentionService(db)
    stats = service.get_stats()

    return RetentionStatsResponse(**stats)


@router.post(
    "/init-defaults",
    response_model=list[RetentionPolicyResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Initialize default policies"
)
async def init_default_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Create default retention policies if none exist.

    **Admin only.**

    Creates sensible defaults for all data types.
    Most are disabled by default for safety.
    """
    service = RetentionService(db)
    policies = service.create_default_policies()

    return [RetentionPolicyResponse.model_validate(p) for p in policies]
