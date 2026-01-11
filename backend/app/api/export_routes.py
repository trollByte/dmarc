"""
Export API routes for PDF and CSV downloads.

Provides endpoints for exporting DMARC data in various formats.
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models import User
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


def _generate_filename(prefix: str, extension: str, domain: Optional[str] = None) -> str:
    """Generate timestamped filename for exports"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if domain:
        return f"{prefix}_{domain}_{timestamp}.{extension}"
    return f"{prefix}_{timestamp}.{extension}"


# ==================== CSV Exports ====================

@router.get("/reports/csv", summary="Export reports to CSV")
async def export_reports_csv(
    days: int = Query(default=30, ge=1, le=365, description="Days of data to export"),
    domain: Optional[str] = Query(default=None, description="Filter by domain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Export DMARC reports to CSV format.

    Returns a downloadable CSV file with report summaries.
    """
    logger.info(f"User {current_user.username} exporting reports CSV (days={days}, domain={domain})")

    service = ExportService(db)
    csv_content = service.export_reports_csv(days=days, domain=domain)

    filename = _generate_filename("dmarc_reports", "csv", domain)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8",
        }
    )


@router.get("/records/csv", summary="Export records to CSV")
async def export_records_csv(
    days: int = Query(default=30, ge=1, le=365, description="Days of data to export"),
    domain: Optional[str] = Query(default=None, description="Filter by domain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Export DMARC records to CSV format.

    Returns a downloadable CSV file with individual record details.
    """
    logger.info(f"User {current_user.username} exporting records CSV (days={days}, domain={domain})")

    service = ExportService(db)
    csv_content = service.export_records_csv(days=days, domain=domain)

    filename = _generate_filename("dmarc_records", "csv", domain)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8",
        }
    )


@router.get("/alerts/csv", summary="Export alerts to CSV")
async def export_alerts_csv(
    days: int = Query(default=30, ge=1, le=365, description="Days of data to export"),
    severity: Optional[str] = Query(default=None, description="Filter by severity"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Export alert history to CSV format.

    Returns a downloadable CSV file with alert details.
    """
    logger.info(f"User {current_user.username} exporting alerts CSV (days={days}, severity={severity})")

    service = ExportService(db)
    csv_content = service.export_alerts_csv(days=days, severity=severity)

    filename = _generate_filename("dmarc_alerts", "csv")

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8",
        }
    )


@router.get("/recommendations/csv", summary="Export recommendations to CSV")
async def export_recommendations_csv(
    days: int = Query(default=30, ge=1, le=365, description="Days of data to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Export policy recommendations to CSV format.

    Returns a downloadable CSV file with recommendations for all domains.
    """
    logger.info(f"User {current_user.username} exporting recommendations CSV (days={days})")

    service = ExportService(db)
    csv_content = service.export_recommendations_csv(days=days)

    filename = _generate_filename("dmarc_recommendations", "csv")

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8",
        }
    )


# ==================== PDF Exports ====================

@router.get("/summary/pdf", summary="Export summary report to PDF")
async def export_summary_pdf(
    days: int = Query(default=30, ge=1, le=365, description="Days of data to include"),
    domain: Optional[str] = Query(default=None, description="Filter by domain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Export DMARC summary report to PDF format.

    Returns a downloadable PDF with executive summary, top domains,
    failing sources, and recommendations.
    """
    logger.info(f"User {current_user.username} exporting summary PDF (days={days}, domain={domain})")

    service = ExportService(db)
    pdf_content = service.export_summary_pdf(days=days, domain=domain)

    filename = _generate_filename("dmarc_summary", "pdf", domain)

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
        }
    )


@router.get("/health/{domain}/pdf", summary="Export domain health report to PDF")
async def export_health_pdf(
    domain: str,
    days: int = Query(default=30, ge=1, le=365, description="Days of data to analyze"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Export domain health report to PDF format.

    Returns a downloadable PDF with domain-specific health metrics,
    issues, and recommendations.
    """
    logger.info(f"User {current_user.username} exporting health PDF for {domain} (days={days})")

    service = ExportService(db)
    pdf_content = service.export_health_report_pdf(domain=domain, days=days)

    filename = _generate_filename("health_report", "pdf", domain)

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
        }
    )
