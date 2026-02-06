"""Integration tests for alert management API routes."""
import pytest
import uuid
import hashlib
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import (
    User, UserRole, AlertHistory, AlertRule, AlertSuppression,
    AlertSeverity, AlertType, AlertStatus,
)
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
        username="alertadmin",
        email="alertadmin@example.com",
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
        username="alertanalyst",
        email="alertanalyst@example.com",
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
        username="alertviewer",
        email="alertviewer@example.com",
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


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_alert(db_session):
    """Create a sample alert in the database."""
    alert = AlertHistory(
        alert_type=AlertType.FAILURE_RATE.value,
        severity=AlertSeverity.WARNING.value,
        fingerprint=hashlib.sha256(b"test-alert-1").hexdigest(),
        title="High failure rate detected",
        message="Failure rate for example.com is 15%",
        domain="example.com",
        current_value=15.0,
        threshold_value=10.0,
        status=AlertStatus.CREATED.value,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    return alert


@pytest.fixture
def sample_alert_rule(db_session, admin_user):
    """Create a sample alert rule."""
    rule = AlertRule(
        name="Test Failure Rule",
        description="Test rule for high failure rate",
        alert_type=AlertType.FAILURE_RATE.value,
        is_enabled=True,
        severity=AlertSeverity.WARNING.value,
        conditions={"failure_rate": {"warning": 10.0, "critical": 25.0}},
        cooldown_minutes=60,
        notify_email=True,
        notify_teams=False,
        notify_slack=False,
        notify_webhook=False,
        created_by=admin_user.id,
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)
    return rule


@pytest.mark.integration
class TestAlertHistory:
    """Test GET /api/alerts/history"""

    def test_get_alert_history(self, client, admin_token, admin_user, sample_alert):
        """Get alert history returns alerts."""
        response = client.get(
            "/api/alerts/history", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_alert_history_filter_domain(self, client, admin_token, admin_user, sample_alert):
        """Filter alerts by domain."""
        response = client.get(
            "/api/alerts/history?domain=example.com",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert all(a["domain"] == "example.com" for a in data if a["domain"])

    def test_alert_history_requires_auth(self, client):
        """Alert history requires authentication."""
        response = client.get("/api/alerts/history")
        assert response.status_code == 401


@pytest.mark.integration
class TestAlertActive:
    """Test GET /api/alerts/active"""

    def test_get_active_alerts(self, client, admin_token, admin_user, sample_alert):
        """Get active alerts returns unresolved alerts."""
        response = client.get(
            "/api/alerts/active", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.integration
class TestAlertStats:
    """Test GET /api/alerts/stats"""

    def test_get_alert_stats(self, client, admin_token, admin_user, sample_alert):
        """Get alert statistics."""
        response = client.get(
            "/api/alerts/stats?days=30", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_alerts" in data
        assert "period_days" in data


@pytest.mark.integration
class TestAcknowledgeAlert:
    """Test POST /api/alerts/{id}/acknowledge"""

    def test_acknowledge_alert_analyst(self, client, analyst_token, analyst_user, sample_alert):
        """Analyst can acknowledge an alert."""
        response = client.post(
            f"/api/alerts/{sample_alert.id}/acknowledge",
            json={"note": "Looking into this"},
            headers=auth_header(analyst_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "acknowledged"

    def test_acknowledge_alert_viewer_forbidden(self, client, viewer_token, viewer_user, sample_alert):
        """Viewer cannot acknowledge alerts."""
        response = client.post(
            f"/api/alerts/{sample_alert.id}/acknowledge",
            json={"note": "test"},
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestResolveAlert:
    """Test POST /api/alerts/{id}/resolve"""

    def test_resolve_alert_admin(self, client, db_session, admin_token, admin_user, sample_alert):
        """Admin can resolve an alert."""
        # First acknowledge it
        sample_alert.status = AlertStatus.ACKNOWLEDGED.value
        sample_alert.acknowledged_at = datetime.utcnow()
        sample_alert.acknowledged_by = admin_user.id
        db_session.commit()

        response = client.post(
            f"/api/alerts/{sample_alert.id}/resolve",
            json={"note": "Issue fixed"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"


@pytest.mark.integration
class TestAlertRulesCRUD:
    """Test alert rules CRUD operations."""

    def test_list_alert_rules(self, client, admin_token, admin_user, sample_alert_rule):
        """List all alert rules."""
        response = client.get(
            "/api/alerts/rules", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_create_alert_rule(self, client, admin_token, admin_user):
        """Admin can create an alert rule."""
        response = client.post(
            "/api/alerts/rules",
            json={
                "name": "New Volume Spike Rule",
                "description": "Alert on volume spikes",
                "alert_type": "volume_spike",
                "is_enabled": True,
                "severity": "critical",
                "conditions": {"volume_spike": {"threshold": 200}},
                "cooldown_minutes": 30,
                "notify_email": True,
                "notify_teams": False,
                "notify_slack": False,
                "notify_webhook": False,
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Volume Spike Rule"
        assert data["is_enabled"] is True

    def test_create_duplicate_rule_name(self, client, admin_token, admin_user, sample_alert_rule):
        """Duplicate rule name returns 400."""
        response = client.post(
            "/api/alerts/rules",
            json={
                "name": "Test Failure Rule",
                "alert_type": "failure_rate",
                "severity": "warning",
                "conditions": {"failure_rate": {"warning": 5.0}},
            },
            headers=auth_header(admin_token),
        )
        assert response.status_code == 400

    def test_update_alert_rule(self, client, admin_token, admin_user, sample_alert_rule):
        """Admin can update an alert rule."""
        response = client.patch(
            f"/api/alerts/rules/{sample_alert_rule.id}",
            json={"is_enabled": False},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["is_enabled"] is False

    def test_update_nonexistent_rule(self, client, admin_token, admin_user):
        """Updating non-existent rule returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.patch(
            f"/api/alerts/rules/{fake_id}",
            json={"is_enabled": False},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_delete_alert_rule(self, client, admin_token, admin_user, sample_alert_rule):
        """Admin can delete an alert rule."""
        response = client.delete(
            f"/api/alerts/rules/{sample_alert_rule.id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200

    def test_delete_nonexistent_rule(self, client, admin_token, admin_user):
        """Deleting non-existent rule returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(
            f"/api/alerts/rules/{fake_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_create_rule_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot create alert rules."""
        response = client.post(
            "/api/alerts/rules",
            json={
                "name": "Forbidden Rule",
                "alert_type": "failure_rate",
                "severity": "info",
                "conditions": {},
            },
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestAlertSuppressions:
    """Test alert suppression CRUD operations."""

    def test_list_suppressions(self, client, admin_token, admin_user):
        """List all alert suppressions."""
        response = client.get(
            "/api/alerts/suppressions", headers=auth_header(admin_token)
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_suppression(self, client, analyst_token, analyst_user):
        """Analyst can create a suppression."""
        response = client.post(
            "/api/alerts/suppressions",
            json={
                "name": "Weekend Maintenance",
                "description": "Suppress during maintenance",
                "is_active": True,
            },
            headers=auth_header(analyst_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Weekend Maintenance"

    def test_delete_suppression(self, client, db_session, analyst_token, analyst_user):
        """Analyst can delete a suppression."""
        suppression = AlertSuppression(
            name="ToDelete",
            is_active=True,
            created_by=analyst_user.id,
        )
        db_session.add(suppression)
        db_session.commit()
        db_session.refresh(suppression)

        response = client.delete(
            f"/api/alerts/suppressions/{suppression.id}",
            headers=auth_header(analyst_token),
        )
        assert response.status_code == 200
