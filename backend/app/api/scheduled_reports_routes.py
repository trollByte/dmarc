"""
Scheduled Reports API routes.

Endpoints:
- GET /scheduled-reports - List scheduled reports
- POST /scheduled-reports - Create schedule
- GET /scheduled-reports/{id} - Get schedule details
- PUT /scheduled-reports/{id} - Update schedule
- DELETE /scheduled-reports/{id} - Delete schedule
- POST /scheduled-reports/{id}/run - Run immediately
- GET /scheduled-reports/{id}/logs - Get delivery logs
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.dependencies.auth import get_current_user, require_role
from app.services.scheduled_reports_service import ScheduledReportsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduled-reports", tags=["Scheduled Reports"])


# ==================== Schemas ====================

class CreateScheduleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    frequency: str = Field(..., description="daily, weekly, or monthly")
    report_type: str = Field(..., description="dmarc_summary, domain_detail, threat_report, etc.")
    recipients: List[str] = Field(..., min_items=1)
    domains: Optional[List[str]] = Field(None, description="Specific domains or null for all")
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="0=Monday for weekly")
    day_of_month: Optional[int] = Field(None, ge=1, le=31, description="Day for monthly")
    hour: int = Field(default=8, ge=0, le=23, description="Hour to send (UTC)")
    timezone: str = Field(default="UTC")
    date_range_days: int = Field(default=7, ge=1, le=90)
    include_charts: bool = True
    include_recommendations: bool = True
    email_subject: Optional[str] = None
    email_body: Optional[str] = None


class UpdateScheduleRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    frequency: Optional[str] = None
    report_type: Optional[str] = None
    recipients: Optional[List[str]] = None
    domains: Optional[List[str]] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    hour: Optional[int] = Field(None, ge=0, le=23)
    timezone: Optional[str] = None
    date_range_days: Optional[int] = Field(None, ge=1, le=90)
    include_charts: Optional[bool] = None
    include_recommendations: Optional[bool] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None


class ScheduleResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    user_id: UUID
    is_active: bool
    frequency: str
    day_of_week: Optional[int]
    day_of_month: Optional[int]
    hour: int
    timezone: str
    report_type: str
    domains: Optional[List[str]]
    date_range_days: int
    include_charts: bool
    include_recommendations: bool
    recipients: List[str]
    email_subject: Optional[str]
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    run_count: int
    failure_count: int
    created_at: str


class DeliveryLogResponse(BaseModel):
    id: UUID
    scheduled_report_id: UUID
    status: str
    error_message: Optional[str]
    report_type: str
    date_range_start: str
    date_range_end: str
    domains_included: Optional[List[str]]
    file_size_bytes: Optional[int]
    generation_time_ms: Optional[int]
    recipients: List[str]
    delivered_at: Optional[str]
    started_at: str
    completed_at: Optional[str]


# ==================== Routes ====================

@router.get(
    "",
    response_model=List[ScheduleResponse],
    status_code=status.HTTP_200_OK,
    summary="List scheduled reports"
)
async def list_schedules(
    active_only: bool = Query(True, description="Only show active schedules"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List scheduled reports for the current user."""
    service = ScheduledReportsService(db)
    schedules = service.get_schedules(user_id=current_user.id, active_only=active_only)

    return [
        ScheduleResponse(
            id=s.id,
            name=s.name,
            description=s.description,
            user_id=s.user_id,
            is_active=s.is_active,
            frequency=s.frequency,
            day_of_week=s.day_of_week,
            day_of_month=s.day_of_month,
            hour=s.hour,
            timezone=s.timezone,
            report_type=s.report_type,
            domains=s.domains,
            date_range_days=s.date_range_days,
            include_charts=s.include_charts,
            include_recommendations=s.include_recommendations,
            recipients=s.recipients,
            email_subject=s.email_subject,
            last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
            next_run_at=s.next_run_at.isoformat() if s.next_run_at else None,
            run_count=s.run_count,
            failure_count=s.failure_count,
            created_at=s.created_at.isoformat(),
        )
        for s in schedules
    ]


@router.post(
    "",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create scheduled report"
)
async def create_schedule(
    request: CreateScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new scheduled report.

    **Frequency options:**
    - daily: Runs every day at specified hour
    - weekly: Runs every week on day_of_week (0=Monday)
    - monthly: Runs every month on day_of_month

    **Report types:**
    - dmarc_summary: Overall DMARC compliance summary
    - domain_detail: Detailed per-domain analysis
    - threat_report: Security threats and issues
    - compliance_report: Policy compliance status
    - executive_summary: High-level executive report
    """
    # Validate frequency-specific fields
    if request.frequency == "weekly" and request.day_of_week is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_of_week required for weekly frequency"
        )
    if request.frequency == "monthly" and request.day_of_month is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_of_month required for monthly frequency"
        )

    service = ScheduledReportsService(db)
    schedule = service.create_schedule(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        frequency=request.frequency,
        report_type=request.report_type,
        recipients=request.recipients,
        domains=request.domains,
        day_of_week=request.day_of_week,
        day_of_month=request.day_of_month,
        hour=request.hour,
        timezone=request.timezone,
        date_range_days=request.date_range_days,
        include_charts=request.include_charts,
        include_recommendations=request.include_recommendations,
        email_subject=request.email_subject,
        email_body=request.email_body,
    )

    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        user_id=schedule.user_id,
        is_active=schedule.is_active,
        frequency=schedule.frequency,
        day_of_week=schedule.day_of_week,
        day_of_month=schedule.day_of_month,
        hour=schedule.hour,
        timezone=schedule.timezone,
        report_type=schedule.report_type,
        domains=schedule.domains,
        date_range_days=schedule.date_range_days,
        include_charts=schedule.include_charts,
        include_recommendations=schedule.include_recommendations,
        recipients=schedule.recipients,
        email_subject=schedule.email_subject,
        last_run_at=None,
        next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        run_count=schedule.run_count,
        failure_count=schedule.failure_count,
        created_at=schedule.created_at.isoformat(),
    )


@router.get(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get schedule details"
)
async def get_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details of a scheduled report."""
    service = ScheduledReportsService(db)
    schedule = service.get_schedule(schedule_id)

    if not schedule or schedule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        user_id=schedule.user_id,
        is_active=schedule.is_active,
        frequency=schedule.frequency,
        day_of_week=schedule.day_of_week,
        day_of_month=schedule.day_of_month,
        hour=schedule.hour,
        timezone=schedule.timezone,
        report_type=schedule.report_type,
        domains=schedule.domains,
        date_range_days=schedule.date_range_days,
        include_charts=schedule.include_charts,
        include_recommendations=schedule.include_recommendations,
        recipients=schedule.recipients,
        email_subject=schedule.email_subject,
        last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        run_count=schedule.run_count,
        failure_count=schedule.failure_count,
        created_at=schedule.created_at.isoformat(),
    )


@router.put(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update schedule"
)
async def update_schedule(
    schedule_id: UUID,
    request: UpdateScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a scheduled report."""
    service = ScheduledReportsService(db)
    schedule = service.update_schedule(
        schedule_id=schedule_id,
        user_id=current_user.id,
        **request.dict(exclude_unset=True),
    )

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        user_id=schedule.user_id,
        is_active=schedule.is_active,
        frequency=schedule.frequency,
        day_of_week=schedule.day_of_week,
        day_of_month=schedule.day_of_month,
        hour=schedule.hour,
        timezone=schedule.timezone,
        report_type=schedule.report_type,
        domains=schedule.domains,
        date_range_days=schedule.date_range_days,
        include_charts=schedule.include_charts,
        include_recommendations=schedule.include_recommendations,
        recipients=schedule.recipients,
        email_subject=schedule.email_subject,
        last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        run_count=schedule.run_count,
        failure_count=schedule.failure_count,
        created_at=schedule.created_at.isoformat(),
    )


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete schedule"
)
async def delete_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a scheduled report."""
    service = ScheduledReportsService(db)

    if not service.delete_schedule(schedule_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )


@router.post(
    "/{schedule_id}/run",
    response_model=DeliveryLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Run schedule now"
)
async def run_schedule_now(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run a scheduled report immediately."""
    service = ScheduledReportsService(db)
    log = service.run_now(schedule_id, current_user.id)

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    return DeliveryLogResponse(
        id=log.id,
        scheduled_report_id=log.scheduled_report_id,
        status=log.status,
        error_message=log.error_message,
        report_type=log.report_type,
        date_range_start=log.date_range_start.isoformat(),
        date_range_end=log.date_range_end.isoformat(),
        domains_included=log.domains_included,
        file_size_bytes=log.file_size_bytes,
        generation_time_ms=log.generation_time_ms,
        recipients=log.recipients,
        delivered_at=log.delivered_at.isoformat() if log.delivered_at else None,
        started_at=log.started_at.isoformat(),
        completed_at=log.completed_at.isoformat() if log.completed_at else None,
    )


@router.get(
    "/{schedule_id}/logs",
    response_model=List[DeliveryLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get delivery logs"
)
async def get_delivery_logs(
    schedule_id: UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get delivery logs for a scheduled report."""
    service = ScheduledReportsService(db)

    # Verify ownership
    schedule = service.get_schedule(schedule_id)
    if not schedule or schedule.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    logs = service.get_delivery_logs(
        schedule_id=schedule_id,
        status=status_filter,
        days=days,
        limit=limit,
    )

    return [
        DeliveryLogResponse(
            id=log.id,
            scheduled_report_id=log.scheduled_report_id,
            status=log.status,
            error_message=log.error_message,
            report_type=log.report_type,
            date_range_start=log.date_range_start.isoformat(),
            date_range_end=log.date_range_end.isoformat(),
            domains_included=log.domains_included,
            file_size_bytes=log.file_size_bytes,
            generation_time_ms=log.generation_time_ms,
            recipients=log.recipients,
            delivered_at=log.delivered_at.isoformat() if log.delivered_at else None,
            started_at=log.started_at.isoformat(),
            completed_at=log.completed_at.isoformat() if log.completed_at else None,
        )
        for log in logs
    ]
