"""Unit tests for authentication service"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import jwt

from app.services.auth_service import AuthService, PasswordValidationError
from app.models.user import User, UserRole


class TestPasswordHashing:
    """Test password hashing functionality"""

    def test_hash_password(self):
        """Test password is hashed correctly"""
        password = "SecurePassword123!"
        hashed = AuthService.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_password_correct(self):
        """Test correct password verification"""
        password = "SecurePassword123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test incorrect password verification"""
        password = "SecurePassword123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password("WrongPassword", hashed) is False

    def test_different_passwords_different_hashes(self):
        """Test different passwords produce different hashes"""
        hash1 = AuthService.hash_password("Password1")
        hash2 = AuthService.hash_password("Password2")

        assert hash1 != hash2

    def test_same_password_different_hashes(self):
        """Test same password produces different hashes (salt)"""
        password = "SamePassword123!"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)

        assert hash1 != hash2  # Different due to salt
        assert AuthService.verify_password(password, hash1) is True
        assert AuthService.verify_password(password, hash2) is True


class TestPasswordValidation:
    """Test password policy validation"""

    @pytest.fixture(autouse=True)
    def mock_settings(self):
        """Mock settings for password policy"""
        with patch("app.services.auth_service.settings") as mock_s:
            mock_s.password_min_length = 8
            mock_s.password_require_uppercase = True
            mock_s.password_require_lowercase = True
            mock_s.password_require_digit = True
            mock_s.password_require_special = True
            yield mock_s

    def test_valid_password(self):
        """Test valid password passes validation"""
        password = "SecurePass123!"
        # Should not raise
        AuthService.validate_password_policy(password)

    def test_password_too_short(self):
        """Test short password fails validation"""
        password = "Short1!"
        with pytest.raises(PasswordValidationError, match="at least"):
            AuthService.validate_password_policy(password)

    def test_password_no_uppercase(self):
        """Test password without uppercase fails"""
        password = "nouppercase123!"
        with pytest.raises(PasswordValidationError, match="uppercase"):
            AuthService.validate_password_policy(password)

    def test_password_no_lowercase(self):
        """Test password without lowercase fails"""
        password = "NOLOWERCASE123!"
        with pytest.raises(PasswordValidationError, match="lowercase"):
            AuthService.validate_password_policy(password)

    def test_password_no_digit(self):
        """Test password without digit fails"""
        password = "NoDigitsHere!"
        with pytest.raises(PasswordValidationError, match="digit"):
            AuthService.validate_password_policy(password)

    def test_password_no_special(self):
        """Test password without special char fails"""
        password = "NoSpecialChar123"
        with pytest.raises(PasswordValidationError, match="special"):
            AuthService.validate_password_policy(password)


class TestJWTTokens:
    """Test JWT token creation and validation"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for JWT"""
        settings = Mock()
        settings.jwt_secret_key = "test-secret-key-for-jwt"
        settings.jwt_algorithm = "HS256"
        settings.jwt_access_token_expire_minutes = 15
        settings.jwt_refresh_token_expire_days = 7
        return settings

    def test_create_access_token(self, mock_settings):
        """Test access token creation"""
        with patch("app.services.auth_service.settings", mock_settings):
            token = AuthService.create_access_token(
                user_id="user123",
                username="testuser",
                role=UserRole.VIEWER
            )

            assert token is not None
            # Decode to verify
            decoded = jwt.decode(
                token,
                mock_settings.jwt_secret_key,
                algorithms=[mock_settings.jwt_algorithm]
            )
            assert decoded["sub"] == "user123"
            assert "exp" in decoded

    def test_access_token_expiration(self, mock_settings):
        """Test access token has correct expiration"""
        mock_settings.jwt_access_token_expire_minutes = 30
        with patch("app.services.auth_service.settings", mock_settings):
            token = AuthService.create_access_token(
                user_id="user123",
                username="testuser",
                role=UserRole.VIEWER
            )

            decoded = jwt.decode(
                token,
                mock_settings.jwt_secret_key,
                algorithms=[mock_settings.jwt_algorithm]
            )

            exp_time = datetime.utcfromtimestamp(decoded["exp"])
            now = datetime.utcnow()
            diff = exp_time - now

            # Should be close to 30 minutes
            assert 29 <= diff.total_seconds() / 60 <= 31

    def test_create_refresh_token(self, mock_settings):
        """Test refresh token creation"""
        with patch("app.services.auth_service.settings", mock_settings):
            token = AuthService.create_refresh_token(
                user_id="user123"
            )

            assert token is not None
            decoded = jwt.decode(
                token,
                mock_settings.jwt_secret_key,
                algorithms=[mock_settings.jwt_algorithm]
            )
            assert decoded["sub"] == "user123"


class TestUserAuthentication:
    """Test user authentication flow"""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user"""
        user = Mock(spec=User)
        user.id = "user-uuid-123"
        user.username = "testuser"
        user.email = "test@example.com"
        user.hashed_password = AuthService.hash_password("ValidPassword123!")
        user.is_active = True
        user.role = UserRole.VIEWER.value
        user.failed_login_attempts = 0
        user.is_locked = False
        user.updated_at = None
        user.last_login = None
        return user

    def test_authenticate_valid_user(self, mock_user):
        """Test valid user authentication"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.max_failed_login_attempts = 5
            mock_settings.account_lockout_duration_minutes = 30

            result = AuthService.authenticate_user(
                mock_db,
                "testuser",
                "ValidPassword123!"
            )

            assert result is not None
            assert result.username == "testuser"

    def test_authenticate_invalid_password(self, mock_user):
        """Test authentication with wrong password"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.max_failed_login_attempts = 5
            mock_settings.account_lockout_duration_minutes = 30

            result = AuthService.authenticate_user(
                mock_db,
                "testuser",
                "WrongPassword123!"
            )

            assert result is None

    def test_authenticate_user_not_found(self):
        """Test authentication with non-existent user"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = AuthService.authenticate_user(
            mock_db,
            "nonexistent",
            "Password123!"
        )

        assert result is None

    def test_authenticate_inactive_user(self, mock_user):
        """Test authentication with inactive user"""
        mock_user.is_active = False
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.max_failed_login_attempts = 5
            mock_settings.account_lockout_duration_minutes = 30

            result = AuthService.authenticate_user(
                mock_db,
                "testuser",
                "ValidPassword123!"
            )

            assert result is None

    def test_authenticate_locked_user(self, mock_user):
        """Test authentication with locked user"""
        mock_user.is_locked = True
        # Set updated_at to recently so the lock hasn't expired
        mock_user.updated_at = datetime.utcnow()
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.auth_service.settings") as mock_settings:
            mock_settings.max_failed_login_attempts = 5
            mock_settings.account_lockout_duration_minutes = 30

            result = AuthService.authenticate_user(
                mock_db,
                "testuser",
                "ValidPassword123!"
            )

            # Locked users should not authenticate
            assert result is None
