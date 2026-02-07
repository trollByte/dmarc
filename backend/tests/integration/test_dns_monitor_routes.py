"""Integration tests for DNS monitor API routes."""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole
from app.services.auth_service import AuthService
from app.services.dns_monitor import MonitoredDomain, DNSChangeLog


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
        username="dnsadmin",
        email="dnsadmin@example.com",
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
def viewer_user(db_session):
    hashed = AuthService.hash_password("ViewerPassword123!")
    user = User(
        username="dnsviewer",
        email="dnsviewer@example.com",
        hashed_password=hashed,
        role=UserRole.VIEWER.value,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def analyst_user(db_session):
    hashed = AuthService.hash_password("AnalystPassword123!")
    user = User(
        username="dnsanalyst",
        email="dnsanalyst@example.com",
        hashed_password=hashed,
        role=UserRole.ANALYST.value,
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
def viewer_token(viewer_user):
    return AuthService.create_access_token(
        str(viewer_user.id), viewer_user.username, UserRole.VIEWER
    )


@pytest.fixture
def analyst_token(analyst_user):
    return AuthService.create_access_token(
        str(analyst_user.id), analyst_user.username, UserRole.ANALYST
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_monitored_domain(db_session):
    """Create a sample monitored domain directly in the database."""
    domain = MonitoredDomain(
        id=uuid.uuid4(),
        domain="testdomain.com",
        is_active=True,
        monitor_dmarc=True,
        monitor_spf=True,
        monitor_dkim=False,
        monitor_mx=False,
        dkim_selectors=None,
        last_checked_at=None,
        created_at=datetime.utcnow(),
    )
    db_session.add(domain)
    db_session.commit()
    db_session.refresh(domain)
    return domain


@pytest.fixture
def sample_dns_change(db_session):
    """Create a sample DNS change log entry."""
    change = DNSChangeLog(
        id=uuid.uuid4(),
        domain="testdomain.com",
        record_type="dmarc",
        change_type="modified",
        old_value="v=DMARC1; p=none;",
        new_value="v=DMARC1; p=quarantine;",
        alert_sent=False,
        acknowledged=False,
        detected_at=datetime.utcnow(),
    )
    db_session.add(change)
    db_session.commit()
    db_session.refresh(change)
    return change


# ==================== List Domains ====================


@pytest.mark.integration
class TestListDomains:
    """Test GET /api/dns-monitor/domains"""

    def test_list_domains_empty(self, client, admin_token, admin_user):
        """List domains returns empty when none monitored."""
        response = client.get(
            "/api/dns-monitor/domains",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_domains_with_data(
        self, client, admin_token, admin_user, sample_monitored_domain
    ):
        """List domains returns existing monitored domains."""
        response = client.get(
            "/api/dns-monitor/domains",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["domain"] == "testdomain.com"
        assert data[0]["is_active"] is True
        assert data[0]["monitor_dmarc"] is True

    def test_list_domains_active_only_filter(
        self, client, admin_token, admin_user, sample_monitored_domain
    ):
        """Active-only filter works correctly."""
        response = client.get(
            "/api/dns-monitor/domains?active_only=true",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_list_domains_viewer_can_access(self, client, viewer_token, viewer_user):
        """Any authenticated user can list domains."""
        response = client.get(
            "/api/dns-monitor/domains",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200

    def test_list_domains_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        response = client.get("/api/dns-monitor/domains")
        assert response.status_code in (401, 403)


# ==================== Add Domain ====================


@pytest.mark.integration
class TestAddDomain:
    """Test POST /api/dns-monitor/domains"""

    @patch("app.services.dns_monitor.DNSMonitorService._take_snapshot")
    def test_add_domain_admin(self, mock_snapshot, client, admin_token, admin_user):
        """Admin can add a domain for monitoring."""
        mock_snapshot.return_value = None

        response = client.post(
            "/api/dns-monitor/domains",
            json={
                "domain": "example.com",
                "monitor_dmarc": True,
                "monitor_spf": True,
                "monitor_dkim": False,
                "monitor_mx": False,
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["domain"] == "example.com"
        assert data["is_active"] is True
        assert data["monitor_dmarc"] is True
        assert data["monitor_spf"] is True

    @patch("app.services.dns_monitor.DNSMonitorService._take_snapshot")
    def test_add_domain_with_dkim_selectors(
        self, mock_snapshot, client, admin_token, admin_user
    ):
        """Admin can add domain with DKIM selectors."""
        mock_snapshot.return_value = None

        response = client.post(
            "/api/dns-monitor/domains",
            json={
                "domain": "dkim-test.com",
                "monitor_dmarc": True,
                "monitor_spf": True,
                "monitor_dkim": True,
                "monitor_mx": True,
                "dkim_selectors": ["selector1", "google"],
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["domain"] == "dkim-test.com"
        assert data["monitor_dkim"] is True

    def test_add_domain_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot add domains."""
        response = client.post(
            "/api/dns-monitor/domains",
            json={"domain": "forbidden.com"},
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403

    def test_add_domain_analyst_forbidden(self, client, analyst_token, analyst_user):
        """Analyst cannot add domains."""
        response = client.post(
            "/api/dns-monitor/domains",
            json={"domain": "forbidden.com"},
            headers=auth_header(analyst_token),
        )
        assert response.status_code == 403

    def test_add_domain_missing_domain_field(self, client, admin_token, admin_user):
        """Missing domain field returns 422."""
        response = client.post(
            "/api/dns-monitor/domains",
            json={"monitor_dmarc": True},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422

    @patch("app.services.dns_monitor.DNSMonitorService._take_snapshot")
    def test_add_domain_reactivates_existing(
        self, mock_snapshot, client, admin_token, admin_user, db_session
    ):
        """Re-adding an inactive domain reactivates it."""
        mock_snapshot.return_value = None

        # Create an inactive domain directly
        domain = MonitoredDomain(
            id=uuid.uuid4(),
            domain="reactivate.com",
            is_active=False,
            monitor_dmarc=False,
            monitor_spf=False,
            monitor_dkim=False,
            monitor_mx=False,
            created_at=datetime.utcnow(),
        )
        db_session.add(domain)
        db_session.commit()

        response = client.post(
            "/api/dns-monitor/domains",
            json={"domain": "reactivate.com", "monitor_dmarc": True, "monitor_spf": True},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_active"] is True
        assert data["monitor_dmarc"] is True


# ==================== Remove Domain ====================


@pytest.mark.integration
class TestRemoveDomain:
    """Test DELETE /api/dns-monitor/domains/{domain}"""

    def test_remove_domain_admin(
        self, client, admin_token, admin_user, sample_monitored_domain
    ):
        """Admin can remove a domain."""
        response = client.delete(
            "/api/dns-monitor/domains/testdomain.com",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 204

    def test_remove_domain_not_found(self, client, admin_token, admin_user):
        """Removing non-existent domain returns 404."""
        response = client.delete(
            "/api/dns-monitor/domains/nonexistent.com",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_remove_domain_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot remove domains."""
        response = client.delete(
            "/api/dns-monitor/domains/testdomain.com",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403

    def test_remove_domain_unauthenticated(self, client):
        """Unauthenticated removal returns 401."""
        response = client.delete("/api/dns-monitor/domains/testdomain.com")
        assert response.status_code in (401, 403)


# ==================== Check All Domains ====================


@pytest.mark.integration
class TestCheckAllDomains:
    """Test POST /api/dns-monitor/check"""

    @patch("app.services.dns_monitor.DNSMonitorService.check_all_domains")
    @patch("app.services.dns_monitor.DNSMonitorService.get_domains")
    def test_check_all_domains_admin(
        self, mock_get_domains, mock_check, client, admin_token, admin_user
    ):
        """Admin can check all domains."""
        mock_check.return_value = {}
        mock_get_domains.return_value = []

        response = client.post(
            "/api/dns-monitor/check",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "domains_checked" in data
        assert "total_changes" in data

    def test_check_all_domains_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot trigger full domain check."""
        response = client.post(
            "/api/dns-monitor/check",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403

    def test_check_all_domains_analyst_forbidden(self, client, analyst_token, analyst_user):
        """Analyst cannot trigger full domain check."""
        response = client.post(
            "/api/dns-monitor/check",
            headers=auth_header(analyst_token),
        )
        assert response.status_code == 403


# ==================== Check Single Domain ====================


@pytest.mark.integration
class TestCheckSingleDomain:
    """Test POST /api/dns-monitor/check/{domain}"""

    @patch("app.services.dns_monitor.DNSMonitorService.check_domain")
    def test_check_single_domain(self, mock_check, client, admin_token, admin_user):
        """Authenticated user can check a single domain."""
        mock_check.return_value = []

        response = client.post(
            "/api/dns-monitor/check/example.com",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == "example.com"
        assert data["changes_detected"] == 0
        assert isinstance(data["changes"], list)

    @patch("app.services.dns_monitor.DNSMonitorService.check_domain")
    def test_check_single_domain_viewer(self, mock_check, client, viewer_token, viewer_user):
        """Viewer can check a single domain (any authenticated user)."""
        mock_check.return_value = []

        response = client.post(
            "/api/dns-monitor/check/example.com",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200

    def test_check_single_domain_unauthenticated(self, client):
        """Unauthenticated domain check returns 401."""
        response = client.post("/api/dns-monitor/check/example.com")
        assert response.status_code in (401, 403)


# ==================== Get Changes ====================


@pytest.mark.integration
class TestGetChanges:
    """Test GET /api/dns-monitor/changes"""

    def test_get_changes_empty(self, client, admin_token, admin_user):
        """Get changes returns empty when no changes exist."""
        response = client.get(
            "/api/dns-monitor/changes",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_changes_with_data(
        self, client, admin_token, admin_user, sample_dns_change
    ):
        """Get changes returns existing change logs."""
        response = client.get(
            "/api/dns-monitor/changes",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["domain"] == "testdomain.com"
        assert data[0]["record_type"] == "dmarc"
        assert data[0]["change_type"] == "modified"

    def test_get_changes_filter_by_domain(
        self, client, admin_token, admin_user, sample_dns_change
    ):
        """Filter changes by domain name."""
        response = client.get(
            "/api/dns-monitor/changes?domain=testdomain.com",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_get_changes_filter_by_record_type(
        self, client, admin_token, admin_user, sample_dns_change
    ):
        """Filter changes by record type."""
        response = client.get(
            "/api/dns-monitor/changes?record_type=dmarc",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200

    def test_get_changes_with_days_and_limit(self, client, admin_token, admin_user):
        """Days and limit parameters are accepted."""
        response = client.get(
            "/api/dns-monitor/changes?days=7&limit=50",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200

    def test_get_changes_viewer_can_access(self, client, viewer_token, viewer_user):
        """Viewer can access change history."""
        response = client.get(
            "/api/dns-monitor/changes",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200

    def test_get_changes_unauthenticated(self, client):
        """Unauthenticated change listing returns 401."""
        response = client.get("/api/dns-monitor/changes")
        assert response.status_code in (401, 403)


# ==================== Acknowledge Change ====================


@pytest.mark.integration
class TestAcknowledgeChange:
    """Test POST /api/dns-monitor/changes/{change_id}/acknowledge"""

    def test_acknowledge_change(
        self, client, admin_token, admin_user, sample_dns_change
    ):
        """Acknowledge an existing change."""
        response = client.post(
            f"/api/dns-monitor/changes/{sample_dns_change.id}/acknowledge",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Change acknowledged"

    def test_acknowledge_change_not_found(self, client, admin_token, admin_user):
        """Acknowledging non-existent change returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.post(
            f"/api/dns-monitor/changes/{fake_id}/acknowledge",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_acknowledge_change_viewer_can_access(
        self, client, viewer_token, viewer_user, sample_dns_change
    ):
        """Any authenticated user can acknowledge changes."""
        response = client.post(
            f"/api/dns-monitor/changes/{sample_dns_change.id}/acknowledge",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200

    def test_acknowledge_change_unauthenticated(self, client, sample_dns_change):
        """Unauthenticated acknowledgment returns 401."""
        response = client.post(
            f"/api/dns-monitor/changes/{sample_dns_change.id}/acknowledge"
        )
        assert response.status_code in (401, 403)

    def test_acknowledge_change_invalid_uuid(self, client, admin_token, admin_user):
        """Invalid UUID returns 422."""
        response = client.post(
            "/api/dns-monitor/changes/not-a-uuid/acknowledge",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422
