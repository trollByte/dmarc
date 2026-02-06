"""Integration tests for dashboard API routes."""
import pytest
from datetime import datetime, timedelta
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
        username="dashadmin",
        email="dashadmin@example.com",
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
def seed_dashboard_data(db_session):
    """Seed database with recent data for dashboard."""
    now = datetime.utcnow()
    report = DmarcReport(
        report_id="dash-report-1",
        org_name="Google",
        email="noreply@google.com",
        domain="example.com",
        date_begin=now - timedelta(days=1),
        date_end=now,
        p="reject",
        pct=100,
    )
    db_session.add(report)
    db_session.flush()

    records = [
        DmarcRecord(
            report_id=report.id,
            source_ip="192.0.2.1",
            count=100,
            disposition="none",
            dkim="pass",
            spf="pass",
            dkim_result="pass",
            spf_result="pass",
            header_from="example.com",
        ),
        DmarcRecord(
            report_id=report.id,
            source_ip="10.0.0.1",
            count=5,
            disposition="reject",
            dkim="fail",
            spf="fail",
            dkim_result="fail",
            spf_result="fail",
            header_from="example.com",
        ),
    ]
    for r in records:
        db_session.add(r)
    db_session.commit()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestDashboardSummary:
    """Test GET /api/dashboard/summary"""

    def test_summary_returns_structure(self, client, admin_token, admin_user, seed_dashboard_data):
        """Dashboard summary returns expected structure."""
        response = client.get(
            "/api/dashboard/summary?days=30",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()

        assert "period" in data
        assert "health" in data
        assert "email_volume" in data
        assert "domains" in data
        assert "alerts" in data
        assert "threats" in data
        assert "activity" in data

        assert data["period"]["days"] == 30
        assert "score" in data["health"]
        assert "grade" in data["health"]
        assert "total" in data["email_volume"]
        assert "passed" in data["email_volume"]
        assert "failed" in data["email_volume"]
        assert "pass_rate" in data["email_volume"]

    def test_summary_empty_data(self, client, admin_token, admin_user):
        """Dashboard summary with no data returns zero values."""
        response = client.get(
            "/api/dashboard/summary?days=7",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email_volume"]["total"] == 0

    def test_summary_requires_auth(self, client):
        """Dashboard summary requires authentication."""
        response = client.get("/api/dashboard/summary")
        assert response.status_code == 401


@pytest.mark.integration
class TestVolumeChart:
    """Test GET /api/dashboard/charts/volume"""

    def test_volume_chart_returns_data(self, client, admin_token, admin_user, seed_dashboard_data):
        """Volume chart returns time series data."""
        response = client.get(
            "/api/dashboard/charts/volume?days=30",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "period_days" in data
        assert "data" in data
        assert data["period_days"] == 30

    def test_volume_chart_empty(self, client, admin_token, admin_user):
        """Volume chart with no data returns empty list."""
        response = client.get(
            "/api/dashboard/charts/volume?days=7",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["data"], list)


@pytest.mark.integration
class TestAuthChart:
    """Test GET /api/dashboard/charts/authentication"""

    def test_auth_chart_returns_data(self, client, admin_token, admin_user, seed_dashboard_data):
        """Authentication chart returns time series data."""
        response = client.get(
            "/api/dashboard/charts/authentication?days=30",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "period_days" in data
        assert "data" in data


@pytest.mark.integration
class TestTopSenders:
    """Test GET /api/dashboard/charts/top-senders"""

    def test_top_senders(self, client, admin_token, admin_user, seed_dashboard_data):
        """Top senders returns list of IPs."""
        response = client.get(
            "/api/dashboard/charts/top-senders?days=7",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "senders" in data
        assert isinstance(data["senders"], list)


@pytest.mark.integration
class TestGeoDistribution:
    """Test GET /api/dashboard/charts/geo-distribution"""

    def test_geo_distribution(self, client, admin_token, admin_user):
        """Geo distribution endpoint works."""
        response = client.get(
            "/api/dashboard/charts/geo-distribution?days=7",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert isinstance(data["countries"], list)


@pytest.mark.integration
class TestAuthAnalysis:
    """Test GET /api/dashboard/auth-analysis"""

    def test_auth_analysis_returns_structure(self, client, admin_token, admin_user, seed_dashboard_data):
        """Auth analysis returns expected structure."""
        response = client.get(
            "/api/dashboard/auth-analysis?days=30",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "dkim_selectors" in data
        assert "spf_domains" in data
        assert "failing_sources" in data
        assert "recommendations" in data

    def test_auth_analysis_with_domain(self, client, admin_token, admin_user, seed_dashboard_data):
        """Auth analysis filtered by domain."""
        response = client.get(
            "/api/dashboard/auth-analysis?days=30&domain=example.com",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == "example.com"
