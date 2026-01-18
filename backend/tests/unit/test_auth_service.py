"""Unit tests for authentication service"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import jwt

from app.services.auth_service import AuthService
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

    def test_valid_password(self):
        """Test valid password passes validation"""
        password = "SecurePass123!"
        is_valid, error = AuthService.validate_password_strength(password)
        assert is_valid is True
        assert error is None

    def test_password_too_short(self):
        """Test short password fails validation"""
        password = "Short1!"
        is_valid, error = AuthService.validate_password_strength(password)
        assert is_valid is False
        assert "length" in error.lower()

    def test_password_no_uppercase(self):
        """Test password without uppercase fails"""
        password = "nouppercase123!"
        is_valid, error = AuthService.validate_password_strength(password)
        assert is_valid is False
        assert "uppercase" in error.lower()

    def test_password_no_lowercase(self):
        """Test password without lowercase fails"""
        password = "NOLOWERCASE123!"
        is_valid, error = AuthService.validate_password_strength(password)
        assert is_valid is False
        assert "lowercase" in error.lower()

    def test_password_no_digit(self):
        """Test password without digit fails"""
        password = "NoDigitsHere!"
        is_valid, error = AuthService.validate_password_strength(password)
        assert is_valid is False
        assert "digit" in error.lower()

    def test_password_no_special(self):
        """Test password without special char fails"""
        password = "NoSpecialChar123"
        is_valid, error = AuthService.validate_password_strength(password)
        assert is_valid is False
        assert "special" in error.lower()


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
        with patch("app.services.auth_service.get_settings", return_value=mock_settings):
            token = AuthService.create_access_token(
                data={"sub": "user123"},
                expires_delta=timedelta(minutes=15)
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
        with patch("app.services.auth_service.get_settings", return_value=mock_settings):
            expires_delta = timedelta(minutes=30)
            token = AuthService.create_access_token(
                data={"sub": "user123"},
                expires_delta=expires_delta
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
        with patch("app.services.auth_service.get_settings", return_value=mock_settings):
            token = AuthService.create_refresh_token(
                data={"sub": "user123"}
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
        user.role = UserRole.USER.value
        user.failed_login_attempts = 0
        user.locked_until = None
        return user

    def test_authenticate_valid_user(self, mock_user):
        """Test valid user authentication"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.auth_service.get_settings") as mock_settings:
            mock_settings.return_value.max_failed_login_attempts = 5
            mock_settings.return_value.account_lockout_duration_minutes = 30

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

        with patch("app.services.auth_service.get_settings") as mock_settings:
            mock_settings.return_value.max_failed_login_attempts = 5
            mock_settings.return_value.account_lockout_duration_minutes = 30

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

        result = AuthService.authenticate_user(
            mock_db,
            "testuser",
            "ValidPassword123!"
        )

        assert result is None

    def test_authenticate_locked_user(self, mock_user):
        """Test authentication with locked user"""
        mock_user.locked_until = datetime.utcnow() + timedelta(hours=1)
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("app.services.auth_service.get_settings") as mock_settings:
            mock_settings.return_value.max_failed_login_attempts = 5
            mock_settings.return_value.account_lockout_duration_minutes = 30

            result = AuthService.authenticate_user(
                mock_db,
                "testuser",
                "ValidPassword123!"
            )

            # Locked users should not authenticate
            assert result is None
