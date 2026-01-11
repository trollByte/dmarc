"""
DNS Change Monitoring API routes.

Endpoints:
- GET /dns-monitor/domains - List monitored domains
- POST /dns-monitor/domains - Add domain to monitoring
- DELETE /dns-monitor/domains/{domain} - Remove domain
- POST /dns-monitor/check - Check all domains for changes
- POST /dns-monitor/check/{domain} - Check single domain
- GET /dns-monitor/changes - Get change history
- POST /dns-monitor/changes/{id}/acknowledge - Acknowledge change
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.dependencies.auth import get_current_user, require_role
from app.services.dns_monitor import DNSMonitorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dns-monitor", tags=["DNS Monitoring"])


# ==================== Schemas ====================

class AddDomainRequest(BaseModel):
    domain: str = Field(..., description="Domain to monitor")
    monitor_dmarc: bool = Field(default=True)
    monitor_spf: bool = Field(default=True)
    monitor_dkim: bool = Field(default=False)
    monitor_mx: bool = Field(default=False)
    dkim_selectors: Optional[List[str]] = Field(None, description="DKIM selectors to monitor")


class MonitoredDomainResponse(BaseModel):
    id: UUID
    domain: str
    is_active: bool
    monitor_dmarc: bool
    monitor_spf: bool
    monitor_dkim: bool
    monitor_mx: bool
    dkim_selectors: Optional[str] = None
    last_checked_at: Optional[str] = None
    created_at: str


class DNSChangeResponse(BaseModel):
    id: UUID
    domain: str
    record_type: str
    change_type: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    acknowledged: bool
    detected_at: str


class CheckResultResponse(BaseModel):
    domain: str
    changes_detected: int
    changes: List[DNSChangeResponse]


# ==================== Routes ====================

@router.get(
    "/domains",
    response_model=List[MonitoredDomainResponse],
    status_code=status.HTTP_200_OK,
    summary="List monitored domains"
)
async def list_domains(
    active_only: bool = Query(True, description="Only show active domains"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all domains being monitored for DNS changes."""
    service = DNSMonitorService(db)
    domains = service.get_domains(active_only=active_only)

    return [
        MonitoredDomainResponse(
            id=d.id,
            domain=d.domain,
            is_active=d.is_active,
            monitor_dmarc=d.monitor_dmarc,
            monitor_spf=d.monitor_spf,
            monitor_dkim=d.monitor_dkim,
            monitor_mx=d.monitor_mx,
            dkim_selectors=d.dkim_selectors,
            last_checked_at=d.last_checked_at.isoformat() if d.last_checked_at else None,
            created_at=d.created_at.isoformat(),
        )
        for d in domains
    ]


@router.post(
    "/domains",
    response_model=MonitoredDomainResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add domain to monitoring"
)
async def add_domain(
    request: AddDomainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Add a domain to DNS change monitoring.

    **Admin only.**

    Monitors:
    - DMARC record (_dmarc.domain)
    - SPF record (TXT with v=spf1)
    - DKIM records (selector._domainkey.domain)
    - MX records
    """
    service = DNSMonitorService(db)

    domain = service.add_domain(
        domain=request.domain,
        monitor_dmarc=request.monitor_dmarc,
        monitor_spf=request.monitor_spf,
        monitor_dkim=request.monitor_dkim,
        monitor_mx=request.monitor_mx,
        dkim_selectors=request.dkim_selectors,
    )

    return MonitoredDomainResponse(
        id=domain.id,
        domain=domain.domain,
        is_active=domain.is_active,
        monitor_dmarc=domain.monitor_dmarc,
        monitor_spf=domain.monitor_spf,
        monitor_dkim=domain.monitor_dkim,
        monitor_mx=domain.monitor_mx,
        dkim_selectors=domain.dkim_selectors,
        last_checked_at=domain.last_checked_at.isoformat() if domain.last_checked_at else None,
        created_at=domain.created_at.isoformat(),
    )


@router.delete(
    "/domains/{domain}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove domain from monitoring"
)
async def remove_domain(
    domain: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Remove a domain from DNS change monitoring. Admin only."""
    service = DNSMonitorService(db)

    if not service.remove_domain(domain):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )


@router.post(
    "/check",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Check all domains"
)
async def check_all_domains(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Check all monitored domains for DNS changes.

    **Admin only.**

    Returns a summary of detected changes.
    """
    service = DNSMonitorService(db)
    results = service.check_all_domains()

    total_changes = sum(len(changes) for changes in results.values())

    return {
        "domains_checked": len(service.get_domains()),
        "domains_with_changes": len(results),
        "total_changes": total_changes,
        "changes_by_domain": {
            domain: len(changes) for domain, changes in results.items()
        }
    }


@router.post(
    "/check/{domain}",
    response_model=CheckResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Check single domain"
)
async def check_domain(
    domain: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check a specific domain for DNS changes."""
    service = DNSMonitorService(db)
    changes = service.check_domain(domain)

    return CheckResultResponse(
        domain=domain,
        changes_detected=len(changes),
        changes=[
            DNSChangeResponse(
                id=UUID(int=0),  # Placeholder
                domain=c.domain,
                record_type=c.record_type,
                change_type=c.change_type.value,
                old_value=c.old_value,
                new_value=c.new_value,
                acknowledged=False,
                detected_at=c.detected_at.isoformat(),
            )
            for c in changes
        ]
    )


@router.get(
    "/changes",
    response_model=List[DNSChangeResponse],
    status_code=status.HTTP_200_OK,
    summary="Get change history"
)
async def get_changes(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    record_type: Optional[str] = Query(None, description="Filter by record type"),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get DNS change history."""
    service = DNSMonitorService(db)
    changes = service.get_changes(
        domain=domain,
        record_type=record_type,
        days=days,
        limit=limit,
    )

    return [
        DNSChangeResponse(
            id=c.id,
            domain=c.domain,
            record_type=c.record_type,
            change_type=c.change_type,
            old_value=c.old_value,
            new_value=c.new_value,
            acknowledged=c.acknowledged,
            detected_at=c.detected_at.isoformat(),
        )
        for c in changes
    ]


@router.post(
    "/changes/{change_id}/acknowledge",
    status_code=status.HTTP_200_OK,
    summary="Acknowledge change"
)
async def acknowledge_change(
    change_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge a DNS change."""
    service = DNSMonitorService(db)

    if not service.acknowledge_change(change_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found"
        )

    return {"message": "Change acknowledged"}
