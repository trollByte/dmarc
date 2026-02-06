"""Integration tests for export API routes."""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole, DmarcReport, DmarcRecord
from app.services.auth_service import AuthService


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    hashed = AuthService.hash_password("AdminPassword123!")
    user = User(
        username="exportadmin",
        email="exportadmin@example.com",
        hashed_password=hashed,
        role=UserRole.ADMIN.value,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    return AuthService.create_access_token(
        str(admin_user.id), admin_user.username, UserRole.ADMIN
    )


@pytest.fixture
def seed_reports(db_session):
    """Seed database with sample reports for export."""
    report = DmarcReport(
        report_id="export-test-1",
        org_name="Google",
        email="noreply@google.com",
        domain="example.com",
        date_begin=datetime(2026, 1, 1),
        date_end=datetime(2026, 1, 1, 23, 59, 59),
        p="reject",
        pct=100,
    )
    db_session.add(report)
    db_session.flush()

    record = DmarcRecord(
        report_id=report.id,
        source_ip="192.0.2.1",
        count=10,
        disposition="none",
        dkim="pass",
        spf="pass",
        dkim_result="pass",
        spf_result="pass",
        header_from="example.com",
    )
    db_session.add(record)
    db_session.commit()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestCSVExport:
    """Test CSV export endpoints."""

    def test_export_reports_csv(self, client, admin_token, admin_user, seed_reports):
        """Export reports CSV returns correct content type."""
        response = client.get(
            "/api/export/reports/csv?days=365",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "")

    def test_export_records_csv(self, client, admin_token, admin_user, seed_reports):
        """Export records CSV returns correct content type."""
        response = client.get(
            "/api/export/records/csv?days=365",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")

    def test_export_reports_csv_with_domain(self, client, admin_token, admin_user, seed_reports):
        """Export reports CSV filtered by domain."""
        response = client.get(
            "/api/export/reports/csv?days=365&domain=example.com",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")

    def test_export_alerts_csv(self, client, admin_token, admin_user):
        """Export alerts CSV returns correct content type."""
        response = client.get(
            "/api/export/alerts/csv?days=30",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")

    def test_export_recommendations_csv(self, client, admin_token, admin_user, seed_reports):
        """Export recommendations CSV returns correct content type."""
        response = client.get(
            "/api/export/recommendations/csv?days=365",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")

    def test_export_requires_auth(self, client):
        """Export endpoints require authentication."""
        response = client.get("/api/export/reports/csv")
        assert response.status_code == 401


@pytest.mark.integration
class TestPDFExport:
    """Test PDF export endpoints."""

    def test_export_summary_pdf(self, client, admin_token, admin_user, seed_reports):
        """Export summary PDF returns correct content type."""
        response = client.get(
            "/api/export/summary/pdf?days=365",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "")

    def test_export_summary_pdf_with_domain(self, client, admin_token, admin_user, seed_reports):
        """Export summary PDF filtered by domain."""
        response = client.get(
            "/api/export/summary/pdf?days=365&domain=example.com",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("content-type", "")

    def test_export_health_pdf(self, client, admin_token, admin_user, seed_reports):
        """Export domain health PDF returns correct content type."""
        response = client.get(
            "/api/export/health/example.com/pdf?days=365",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("content-type", "")

    def test_pdf_export_requires_auth(self, client):
        """PDF export requires authentication."""
        response = client.get("/api/export/summary/pdf")
        assert response.status_code == 401
