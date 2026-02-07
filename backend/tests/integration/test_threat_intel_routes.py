"""Integration tests for threat intelligence API routes."""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole
from app.services.auth_service import AuthService
from app.services.threat_intel import ThreatIntelCache, ThreatLevel


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
        username="threatadmin",
        email="threatadmin@example.com",
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
def analyst_user(db_session):
    hashed = AuthService.hash_password("AnalystPassword123!")
    user = User(
        username="threatanalyst",
        email="threatanalyst@example.com",
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
def viewer_user(db_session):
    hashed = AuthService.hash_password("ViewerPassword123!")
    user = User(
        username="threatviewer",
        email="threatviewer@example.com",
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
def admin_token(admin_user):
    return AuthService.create_access_token(
        str(admin_user.id), admin_user.username, UserRole.ADMIN
    )


@pytest.fixture
def analyst_token(analyst_user):
    return AuthService.create_access_token(
        str(analyst_user.id), analyst_user.username, UserRole.ANALYST
    )


@pytest.fixture
def viewer_token(viewer_user):
    return AuthService.create_access_token(
        str(viewer_user.id), viewer_user.username, UserRole.VIEWER
    )


@pytest.fixture
def cached_threat_entry(db_session):
    """Insert a threat intel cache entry for use in tests."""
    entry = ThreatIntelCache(
        ip_address="198.51.100.1",
        source="abuseipdb",
        threat_level=ThreatLevel.HIGH.value,
        abuse_score=75,
        total_reports=42,
        last_reported=datetime.utcnow() - timedelta(days=1),
        is_whitelisted=0,
        is_tor=0,
        isp="Test ISP",
        domain="example.com",
        country_code="US",
        usage_type="Data Center",
        categories=["Email Spam", "Brute-Force"],
        raw_response={},
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Check single IP ----------

@pytest.mark.integration
class TestCheckIP:
    """Test GET /api/threat-intel/check/{ip_address}"""

    def test_check_ip_cached(self, client, admin_token, admin_user, cached_threat_entry):
        """Check an IP that exists in the cache."""
        response = client.get(
            "/api/threat-intel/check/198.51.100.1",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ip_address"] == "198.51.100.1"
        assert data["abuse_score"] == 75
        assert data["threat_level"] == "high"

    def test_check_ip_uncached_no_api_key(self, client, admin_token, admin_user):
        """Check an uncached IP when AbuseIPDB API key is not configured."""
        response = client.get(
            "/api/threat-intel/check/10.0.0.1",
            headers=auth_header(admin_token),
        )
        # Without an API key the service returns a ThreatInfo with source="none"
        # The route will still return 200 since check_ip returns a fallback
        assert response.status_code == 200
        data = response.json()
        assert data["ip_address"] == "10.0.0.1"
        assert data["threat_level"] == "unknown"

    def test_check_ip_unauthenticated(self, client):
        """Unauthenticated request returns 401/403."""
        response = client.get("/api/threat-intel/check/192.168.1.1")
        assert response.status_code in (401, 403)

    def test_check_ip_viewer_can_access(self, client, viewer_token, viewer_user):
        """Viewer can check a single IP (endpoint requires auth only, not role)."""
        response = client.get(
            "/api/threat-intel/check/10.0.0.1",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200


# ---------- Bulk check ----------

@pytest.mark.integration
class TestBulkCheckIPs:
    """Test POST /api/threat-intel/check-bulk"""

    def test_bulk_check_analyst(self, client, analyst_token, analyst_user):
        """Analyst can perform bulk IP check."""
        response = client.post(
            "/api/threat-intel/check-bulk",
            json={"ip_addresses": ["10.0.0.1", "10.0.0.2"], "use_cache": True},
            headers=auth_header(analyst_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert "results" in data
        assert "summary" in data

    def test_bulk_check_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot perform bulk check (analyst+ required)."""
        response = client.post(
            "/api/threat-intel/check-bulk",
            json={"ip_addresses": ["10.0.0.1"]},
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403

    def test_bulk_check_empty_list(self, client, analyst_token, analyst_user):
        """Empty IP list returns 422 validation error."""
        response = client.post(
            "/api/threat-intel/check-bulk",
            json={"ip_addresses": []},
            headers=auth_header(analyst_token),
        )
        assert response.status_code == 422

    def test_bulk_check_unauthenticated(self, client):
        """Unauthenticated bulk check returns 401/403."""
        response = client.post(
            "/api/threat-intel/check-bulk",
            json={"ip_addresses": ["10.0.0.1"]},
        )
        assert response.status_code in (401, 403)


# ---------- Cache stats ----------

@pytest.mark.integration
class TestCacheStats:
    """Test GET /api/threat-intel/cache/stats"""

    def test_cache_stats_empty(self, client, admin_token, admin_user):
        """Cache stats work on empty cache."""
        response = client.get(
            "/api/threat-intel/cache/stats",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_entries" in data
        assert "active_entries" in data
        assert "expired_entries" in data
        assert "by_threat_level" in data
        assert "api_configured" in data

    def test_cache_stats_with_entries(self, client, admin_token, admin_user, cached_threat_entry):
        """Cache stats reflect cached entries."""
        response = client.get(
            "/api/threat-intel/cache/stats",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_entries"] >= 1
        assert data["active_entries"] >= 1

    def test_cache_stats_unauthenticated(self, client):
        """Unauthenticated cache stats request returns 401/403."""
        response = client.get("/api/threat-intel/cache/stats")
        assert response.status_code in (401, 403)


# ---------- High-threat IPs ----------

@pytest.mark.integration
class TestHighThreatIPs:
    """Test GET /api/threat-intel/high-threat"""

    def test_high_threat_empty(self, client, admin_token, admin_user):
        """High threat list is empty when no matching entries exist."""
        response = client.get(
            "/api/threat-intel/high-threat?min_score=90",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_high_threat_returns_entries(self, client, admin_token, admin_user, cached_threat_entry):
        """High threat list returns entries above the score threshold."""
        response = client.get(
            "/api/threat-intel/high-threat?min_score=50",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["ip_address"] == "198.51.100.1"
        assert data[0]["abuse_score"] >= 50

    def test_high_threat_respects_limit(self, client, admin_token, admin_user, cached_threat_entry):
        """Limit parameter restricts the number of results."""
        response = client.get(
            "/api/threat-intel/high-threat?min_score=50&limit=1",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert len(response.json()) <= 1

    def test_high_threat_unauthenticated(self, client):
        """Unauthenticated request returns 401/403."""
        response = client.get("/api/threat-intel/high-threat")
        assert response.status_code in (401, 403)


# ---------- Cache purge ----------

@pytest.mark.integration
class TestPurgeCache:
    """Test POST /api/threat-intel/cache/purge"""

    def test_purge_cache_admin(self, client, admin_token, admin_user):
        """Admin can purge expired cache entries."""
        response = client.post(
            "/api/threat-intel/cache/purge",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "purged_entries" in data

    def test_purge_cache_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot purge cache (admin only)."""
        response = client.post(
            "/api/threat-intel/cache/purge",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403

    def test_purge_cache_analyst_forbidden(self, client, analyst_token, analyst_user):
        """Analyst cannot purge cache (admin only)."""
        response = client.post(
            "/api/threat-intel/cache/purge",
            headers=auth_header(analyst_token),
        )
        assert response.status_code == 403

    def test_purge_cache_unauthenticated(self, client):
        """Unauthenticated purge request returns 401/403."""
        response = client.post("/api/threat-intel/cache/purge")
        assert response.status_code in (401, 403)


# ---------- Enriched anomalies ----------

@pytest.mark.integration
class TestEnrichedAnomalies:
    """Test GET /api/threat-intel/enrich-anomalies"""

    def test_enrich_anomalies_no_model(self, client, admin_token, admin_user):
        """Returns 400 when no deployed ML model exists."""
        response = client.get(
            "/api/threat-intel/enrich-anomalies",
            headers=auth_header(admin_token),
        )
        # No deployed ML model -> 400
        assert response.status_code == 400
        assert "model" in response.json()["detail"].lower()

    def test_enrich_anomalies_unauthenticated(self, client):
        """Unauthenticated request returns 401/403."""
        response = client.get("/api/threat-intel/enrich-anomalies")
        assert response.status_code in (401, 403)
