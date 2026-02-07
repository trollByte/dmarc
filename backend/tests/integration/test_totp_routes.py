"""Integration tests for TOTP two-factor authentication API routes."""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime
from fastapi.testclient import TestClient

import pyotp

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
        username="totpadmin",
        email="totpadmin@example.com",
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
        username="totpviewer",
        email="totpviewer@example.com",
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
def totp_enabled_user(db_session):
    """User with TOTP already enabled and a known secret."""
    import hashlib

    hashed = AuthService.hash_password("TotpUserPassword123!")
    secret = pyotp.random_base32(length=32)

    # Generate backup codes and hash them
    backup_codes_plain = ["AAAA-BBBB", "CCCC-DDDD", "EEEE-FFFF"]
    backup_codes_hashed = [
        hashlib.sha256(c.replace("-", "").upper().encode()).hexdigest()
        for c in backup_codes_plain
    ]

    user = User(
        username="totpenabled",
        email="totpenabled@example.com",
        hashed_password=hashed,
        role=UserRole.ADMIN.value,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
        totp_secret=secret,
        totp_enabled=True,
        totp_backup_codes=backup_codes_hashed,
        totp_verified_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Attach the plaintext secret for test use
    user._test_secret = secret
    user._test_backup_codes = backup_codes_plain
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
def totp_enabled_token(totp_enabled_user):
    role = UserRole(totp_enabled_user.role)
    return AuthService.create_access_token(
        str(totp_enabled_user.id), totp_enabled_user.username, role
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ==================== Get 2FA Status ====================


@pytest.mark.integration
class TestGet2FAStatus:
    """Test GET /api/2fa/status"""

    def test_status_2fa_disabled(self, client, admin_token, admin_user):
        """Get 2FA status when not enabled."""
        response = client.get(
            "/api/2fa/status",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["verified_at"] is None
        assert data["backup_codes_remaining"] == 0

    def test_status_2fa_enabled(self, client, totp_enabled_token, totp_enabled_user):
        """Get 2FA status when enabled."""
        response = client.get(
            "/api/2fa/status",
            headers=auth_header(totp_enabled_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["verified_at"] is not None
        assert data["backup_codes_remaining"] == 3

    def test_status_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        response = client.get("/api/2fa/status")
        assert response.status_code in (401, 403)

    def test_status_viewer_can_access(self, client, viewer_token, viewer_user):
        """Viewer can check their own 2FA status."""
        response = client.get(
            "/api/2fa/status",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False


# ==================== Setup 2FA ====================


@pytest.mark.integration
class TestSetup2FA:
    """Test POST /api/2fa/setup"""

    def test_setup_2fa(self, client, admin_token, admin_user):
        """Setup 2FA returns secret and QR code."""
        response = client.post(
            "/api/2fa/setup",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        assert "provisioning_uri" in data
        assert "qr_code" in data
        assert len(data["secret"]) > 0
        assert data["provisioning_uri"].startswith("otpauth://")

    def test_setup_2fa_viewer(self, client, viewer_token, viewer_user):
        """Any authenticated user can setup 2FA."""
        response = client.post(
            "/api/2fa/setup",
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "secret" in data

    def test_setup_2fa_unauthenticated(self, client):
        """Unauthenticated setup returns 401."""
        response = client.post("/api/2fa/setup")
        assert response.status_code in (401, 403)

    def test_setup_2fa_already_enabled(self, client, totp_enabled_token, totp_enabled_user):
        """Setup can be called even if 2FA is already enabled (to reset)."""
        response = client.post(
            "/api/2fa/setup",
            headers=auth_header(totp_enabled_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "secret" in data


# ==================== Verify and Enable 2FA ====================


@pytest.mark.integration
class TestVerifyAndEnable2FA:
    """Test POST /api/2fa/verify"""

    def test_verify_valid_code(self, client, admin_token, admin_user, db_session):
        """Verify with valid TOTP code enables 2FA."""
        # First, setup 2FA
        setup_resp = client.post(
            "/api/2fa/setup",
            headers=auth_header(admin_token),
        )
        secret = setup_resp.json()["secret"]

        # Generate valid code
        totp = pyotp.TOTP(secret)
        code = totp.now()

        response = client.post(
            "/api/2fa/verify",
            json={"code": code},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "backup_codes" in data
        assert isinstance(data["backup_codes"], list)
        assert len(data["backup_codes"]) > 0
        assert "message" in data

    def test_verify_invalid_code(self, client, admin_token, admin_user, db_session):
        """Verify with invalid TOTP code returns 400."""
        # First, setup 2FA to generate a secret
        client.post(
            "/api/2fa/setup",
            headers=auth_header(admin_token),
        )

        response = client.post(
            "/api/2fa/verify",
            json={"code": "000000"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 400

    def test_verify_no_secret_set(self, client, admin_token, admin_user):
        """Verify without calling setup first returns 400."""
        response = client.post(
            "/api/2fa/verify",
            json={"code": "123456"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 400

    def test_verify_short_code(self, client, admin_token, admin_user):
        """Code shorter than 6 digits returns 422."""
        response = client.post(
            "/api/2fa/verify",
            json={"code": "12345"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422

    def test_verify_long_code(self, client, admin_token, admin_user):
        """Code longer than 6 digits returns 422."""
        response = client.post(
            "/api/2fa/verify",
            json={"code": "1234567"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422

    def test_verify_unauthenticated(self, client):
        """Unauthenticated verify returns 401."""
        response = client.post(
            "/api/2fa/verify",
            json={"code": "123456"},
        )
        assert response.status_code in (401, 403)


# ==================== Disable 2FA ====================


@pytest.mark.integration
class TestDisable2FA:
    """Test POST /api/2fa/disable"""

    def test_disable_2fa_with_correct_password(
        self, client, totp_enabled_token, totp_enabled_user
    ):
        """Disable 2FA with correct password."""
        response = client.post(
            "/api/2fa/disable",
            json={"password": "TotpUserPassword123!"},
            headers=auth_header(totp_enabled_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data

    def test_disable_2fa_wrong_password(
        self, client, totp_enabled_token, totp_enabled_user
    ):
        """Disable 2FA with wrong password returns 400."""
        response = client.post(
            "/api/2fa/disable",
            json={"password": "WrongPassword123!"},
            headers=auth_header(totp_enabled_token),
        )
        assert response.status_code == 400

    def test_disable_2fa_not_enabled(self, client, admin_token, admin_user):
        """Disable 2FA when it is not enabled returns 400."""
        response = client.post(
            "/api/2fa/disable",
            json={"password": "AdminPassword123!"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 400
        data = response.json()
        assert "not enabled" in data["detail"].lower()

    def test_disable_2fa_missing_password(
        self, client, totp_enabled_token, totp_enabled_user
    ):
        """Missing password field returns 422."""
        response = client.post(
            "/api/2fa/disable",
            json={},
            headers=auth_header(totp_enabled_token),
        )
        assert response.status_code == 422

    def test_disable_2fa_unauthenticated(self, client):
        """Unauthenticated disable returns 401."""
        response = client.post(
            "/api/2fa/disable",
            json={"password": "Password123!"},
        )
        assert response.status_code in (401, 403)


# ==================== Regenerate Backup Codes ====================


@pytest.mark.integration
class TestRegenerateBackupCodes:
    """Test POST /api/2fa/backup-codes/regenerate"""

    def test_regenerate_with_valid_code(
        self, client, totp_enabled_token, totp_enabled_user
    ):
        """Regenerate backup codes with valid TOTP code."""
        totp = pyotp.TOTP(totp_enabled_user._test_secret)
        code = totp.now()

        response = client.post(
            "/api/2fa/backup-codes/regenerate",
            json={"code": code},
            headers=auth_header(totp_enabled_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "backup_codes" in data
        assert isinstance(data["backup_codes"], list)
        assert len(data["backup_codes"]) > 0
        assert "message" in data

    def test_regenerate_with_invalid_code(
        self, client, totp_enabled_token, totp_enabled_user
    ):
        """Regenerate backup codes with invalid TOTP code returns 400."""
        response = client.post(
            "/api/2fa/backup-codes/regenerate",
            json={"code": "000000"},
            headers=auth_header(totp_enabled_token),
        )
        assert response.status_code == 400

    def test_regenerate_2fa_not_enabled(self, client, admin_token, admin_user):
        """Regenerate when 2FA not enabled returns 400."""
        response = client.post(
            "/api/2fa/backup-codes/regenerate",
            json={"code": "123456"},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 400
        data = response.json()
        assert "not enabled" in data["detail"].lower()

    def test_regenerate_short_code(
        self, client, totp_enabled_token, totp_enabled_user
    ):
        """Short code returns 422."""
        response = client.post(
            "/api/2fa/backup-codes/regenerate",
            json={"code": "123"},
            headers=auth_header(totp_enabled_token),
        )
        assert response.status_code == 422

    def test_regenerate_unauthenticated(self, client):
        """Unauthenticated regenerate returns 401."""
        response = client.post(
            "/api/2fa/backup-codes/regenerate",
            json={"code": "123456"},
        )
        assert response.status_code in (401, 403)


# ==================== Full 2FA Lifecycle ====================


@pytest.mark.integration
class TestFull2FALifecycle:
    """Test the complete 2FA setup -> verify -> disable lifecycle."""

    def test_full_lifecycle(self, client, admin_token, admin_user):
        """Complete 2FA lifecycle: setup, verify, check status, disable."""
        # Step 1: Check initial status (disabled)
        status_resp = client.get(
            "/api/2fa/status",
            headers=auth_header(admin_token),
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["enabled"] is False

        # Step 2: Setup 2FA
        setup_resp = client.post(
            "/api/2fa/setup",
            headers=auth_header(admin_token),
        )
        assert setup_resp.status_code == 200
        secret = setup_resp.json()["secret"]

        # Step 3: Verify with valid code
        totp = pyotp.TOTP(secret)
        code = totp.now()

        verify_resp = client.post(
            "/api/2fa/verify",
            json={"code": code},
            headers=auth_header(admin_token),
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["success"] is True
        backup_codes = verify_resp.json()["backup_codes"]
        assert len(backup_codes) > 0

        # Step 4: Verify status is now enabled
        status_resp = client.get(
            "/api/2fa/status",
            headers=auth_header(admin_token),
        )
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["enabled"] is True
        assert status_data["backup_codes_remaining"] > 0

        # Step 5: Disable 2FA
        disable_resp = client.post(
            "/api/2fa/disable",
            json={"password": "AdminPassword123!"},
            headers=auth_header(admin_token),
        )
        assert disable_resp.status_code == 200
        assert disable_resp.json()["success"] is True

        # Step 6: Verify status is disabled again
        status_resp = client.get(
            "/api/2fa/status",
            headers=auth_header(admin_token),
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["enabled"] is False
