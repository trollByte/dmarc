"""Integration tests for scheduled reports API routes."""
import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole
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
        username="schedadmin",
        email="schedadmin@example.com",
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
        username="schedviewer",
        email="schedviewer@example.com",
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
def viewer_token(viewer_user):
    return AuthService.create_access_token(
        str(viewer_user.id), viewer_user.username, UserRole.VIEWER
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _create_schedule_payload(**overrides):
    """Helper to build a valid create-schedule JSON body."""
    payload = {
        "name": "Weekly DMARC Summary",
        "frequency": "daily",
        "report_type": "dmarc_summary",
        "recipients": ["ops@example.com"],
        "hour": 9,
        "date_range_days": 7,
    }
    payload.update(overrides)
    return payload


@pytest.mark.integration
class TestListSchedules:
    """Test GET /api/scheduled-reports"""

    def test_list_schedules_empty(self, client, admin_token, admin_user):
        """Listing schedules with no data returns an empty list."""
        response = client.get(
            "/api/scheduled-reports",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_schedules_after_create(self, client, admin_token, admin_user):
        """Listing schedules returns schedules owned by the user."""
        client.post(
            "/api/scheduled-reports",
            json=_create_schedule_payload(),
            headers=auth_header(admin_token),
        )

        response = client.get(
            "/api/scheduled-reports",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["name"] == "Weekly DMARC Summary"

    def test_list_schedules_unauthenticated(self, client):
        """Unauthenticated request returns 401/403."""
        response = client.get("/api/scheduled-reports")
        assert response.status_code in (401, 403)

    def test_list_schedules_viewer_can_access(self, client, viewer_token, viewer_user):
        """Viewer can list their own schedules (endpoint requires auth only)."""
        response = client.get(
            "/api/scheduled-reports",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200

    def test_list_schedules_includes_inactive(self, client, admin_token, admin_user):
        """active_only=false returns inactive schedules too."""
        # Create then deactivate
        create_resp = client.post(
            "/api/scheduled-reports",
            json=_create_schedule_payload(name="Inactive Report"),
            headers=auth_header(admin_token),
        )
        schedule_id = create_resp.json()["id"]

        client.put(
            f"/api/scheduled-reports/{schedule_id}",
            json={"is_active": False},
            headers=auth_header(admin_token),
        )

        response = client.get(
            "/api/scheduled-reports?active_only=false",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        names = [s["name"] for s in response.json()]
        assert "Inactive Report" in names


@pytest.mark.integration
class TestCreateSchedule:
    """Test POST /api/scheduled-reports"""

    def test_create_daily_schedule(self, client, admin_token, admin_user):
        """Create a daily scheduled report."""
        payload = _create_schedule_payload()
        response = client.post(
            "/api/scheduled-reports",
            json=payload,
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Weekly DMARC Summary"
        assert data["frequency"] == "daily"
        assert data["report_type"] == "dmarc_summary"
        assert data["recipients"] == ["ops@example.com"]
        assert data["is_active"] is True
        assert data["run_count"] == 0
        assert data["failure_count"] == 0

    def test_create_weekly_schedule(self, client, admin_token, admin_user):
        """Weekly schedule requires day_of_week."""
        payload = _create_schedule_payload(
            name="Weekly Report",
            frequency="weekly",
            day_of_week=1,
        )
        response = client.post(
            "/api/scheduled-reports",
            json=payload,
            headers=auth_header(admin_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["frequency"] == "weekly"
        assert data["day_of_week"] == 1

    def test_create_weekly_missing_day_of_week(self, client, admin_token, admin_user):
        """Weekly schedule without day_of_week returns 400."""
        payload = _create_schedule_payload(
            name="Bad Weekly",
            frequency="weekly",
        )
        response = client.post(
            "/api/scheduled-reports",
            json=payload,
            headers=auth_header(admin_token),
        )
        assert response.status_code == 400
        assert "day_of_week" in response.json()["detail"].lower()

    def test_create_monthly_missing_day_of_month(self, client, admin_token, admin_user):
        """Monthly schedule without day_of_month returns 400."""
        payload = _create_schedule_payload(
            name="Bad Monthly",
            frequency="monthly",
        )
        response = client.post(
            "/api/scheduled-reports",
            json=payload,
            headers=auth_header(admin_token),
        )
        assert response.status_code == 400
        assert "day_of_month" in response.json()["detail"].lower()

    def test_create_schedule_missing_name(self, client, admin_token, admin_user):
        """Missing required name field returns 422."""
        payload = _create_schedule_payload()
        del payload["name"]
        response = client.post(
            "/api/scheduled-reports",
            json=payload,
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422

    def test_create_schedule_empty_recipients(self, client, admin_token, admin_user):
        """Empty recipients list returns 422."""
        payload = _create_schedule_payload(recipients=[])
        response = client.post(
            "/api/scheduled-reports",
            json=payload,
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestGetSchedule:
    """Test GET /api/scheduled-reports/{id}"""

    def test_get_schedule(self, client, admin_token, admin_user):
        """Get details of a schedule."""
        create_resp = client.post(
            "/api/scheduled-reports",
            json=_create_schedule_payload(name="Detail Schedule"),
            headers=auth_header(admin_token),
        )
        schedule_id = create_resp.json()["id"]

        response = client.get(
            f"/api/scheduled-reports/{schedule_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == schedule_id
        assert data["name"] == "Detail Schedule"

    def test_get_schedule_not_found(self, client, admin_token, admin_user):
        """Non-existent schedule returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/scheduled-reports/{fake_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_get_schedule_wrong_user(self, client, admin_token, admin_user, viewer_token, viewer_user):
        """Schedule owned by another user returns 404."""
        create_resp = client.post(
            "/api/scheduled-reports",
            json=_create_schedule_payload(name="Admin Only"),
            headers=auth_header(admin_token),
        )
        schedule_id = create_resp.json()["id"]

        response = client.get(
            f"/api/scheduled-reports/{schedule_id}",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestUpdateSchedule:
    """Test PUT /api/scheduled-reports/{id}"""

    def test_update_schedule_name(self, client, admin_token, admin_user):
        """Update schedule name."""
        create_resp = client.post(
            "/api/scheduled-reports",
            json=_create_schedule_payload(name="Before Update"),
            headers=auth_header(admin_token),
        )
        schedule_id = create_resp.json()["id"]

        response = client.put(
            f"/api/scheduled-reports/{schedule_id}",
            json={"name": "After Update"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "After Update"

    def test_update_schedule_deactivate(self, client, admin_token, admin_user):
        """Deactivate a schedule."""
        create_resp = client.post(
            "/api/scheduled-reports",
            json=_create_schedule_payload(name="To Deactivate"),
            headers=auth_header(admin_token),
        )
        schedule_id = create_resp.json()["id"]

        response = client.put(
            f"/api/scheduled-reports/{schedule_id}",
            json={"is_active": False},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_update_nonexistent_schedule(self, client, admin_token, admin_user):
        """Updating a non-existent schedule returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/api/scheduled-reports/{fake_id}",
            json={"name": "Ghost"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestDeleteSchedule:
    """Test DELETE /api/scheduled-reports/{id}"""

    def test_delete_schedule(self, client, admin_token, admin_user):
        """Delete an existing schedule."""
        create_resp = client.post(
            "/api/scheduled-reports",
            json=_create_schedule_payload(name="Delete Me"),
            headers=auth_header(admin_token),
        )
        schedule_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/scheduled-reports/{schedule_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 204

        # Confirm it is gone
        response = client.get(
            f"/api/scheduled-reports/{schedule_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_delete_nonexistent_schedule(self, client, admin_token, admin_user):
        """Deleting a non-existent schedule returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(
            f"/api/scheduled-reports/{fake_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestRunScheduleNow:
    """Test POST /api/scheduled-reports/{id}/run"""

    def test_run_nonexistent_schedule(self, client, admin_token, admin_user):
        """Running a non-existent schedule returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.post(
            f"/api/scheduled-reports/{fake_id}/run",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_run_schedule_wrong_user(self, client, admin_token, admin_user, viewer_token, viewer_user):
        """Running a schedule owned by another user returns 404."""
        create_resp = client.post(
            "/api/scheduled-reports",
            json=_create_schedule_payload(name="Admin Run Only"),
            headers=auth_header(admin_token),
        )
        schedule_id = create_resp.json()["id"]

        response = client.post(
            f"/api/scheduled-reports/{schedule_id}/run",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestDeliveryLogs:
    """Test GET /api/scheduled-reports/{id}/logs"""

    def test_get_logs_empty(self, client, admin_token, admin_user):
        """Getting logs for a new schedule returns empty list."""
        create_resp = client.post(
            "/api/scheduled-reports",
            json=_create_schedule_payload(name="Logs Test"),
            headers=auth_header(admin_token),
        )
        schedule_id = create_resp.json()["id"]

        response = client.get(
            f"/api/scheduled-reports/{schedule_id}/logs",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_logs_nonexistent_schedule(self, client, admin_token, admin_user):
        """Getting logs for a non-existent schedule returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/scheduled-reports/{fake_id}/logs",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_get_logs_wrong_user(self, client, admin_token, admin_user, viewer_token, viewer_user):
        """Getting logs for a schedule owned by another user returns 404."""
        create_resp = client.post(
            "/api/scheduled-reports",
            json=_create_schedule_payload(name="Private Logs"),
            headers=auth_header(admin_token),
        )
        schedule_id = create_resp.json()["id"]

        response = client.get(
            f"/api/scheduled-reports/{schedule_id}/logs",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 404
