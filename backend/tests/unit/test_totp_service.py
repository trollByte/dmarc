"""Unit tests for TOTPService (totp_service.py)"""
import pytest
import secrets
import hashlib
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from app.services.totp_service import TOTPService, TOTPError, BACKUP_CODES_COUNT


@pytest.mark.unit
class TestSecretGeneration:
    """Test TOTP secret generation"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.totp_service.get_settings") as mock_settings:
            mock_settings.return_value.app_name = "DMARC Dashboard"
            return TOTPService(mock_db)

    @pytest.fixture
    def mock_user(self):
        user = Mock()
        user.id = "user-123"
        user.username = "testuser"
        user.email = "test@example.com"
        user.totp_secret = None
        user.totp_enabled = False
        return user

    def test_generate_secret_returns_tuple(self, service, mock_user):
        """Test that generate_secret returns (secret, provisioning_uri)"""
        secret, uri = service.generate_secret(mock_user)

        assert secret is not None
        assert len(secret) > 0
        assert uri is not None
        assert "otpauth://totp/" in uri

    def test_generate_secret_stores_on_user(self, service, mock_user, mock_db):
        """Test that secret is stored on user object"""
        secret, uri = service.generate_secret(mock_user)

        assert mock_user.totp_secret == secret
        assert mock_db.commit.called

    def test_generate_secret_uri_contains_email(self, service, mock_user):
        """Test provisioning URI contains user's email"""
        secret, uri = service.generate_secret(mock_user)

        assert "test%40example.com" in uri or "test@example.com" in uri

    def test_generate_secret_uri_contains_issuer(self, service, mock_user):
        """Test provisioning URI contains app name as issuer"""
        secret, uri = service.generate_secret(mock_user)

        assert "DMARC" in uri

    def test_different_calls_produce_different_secrets(self, service, mock_user):
        """Test each call generates a unique secret"""
        secret1, _ = service.generate_secret(mock_user)
        secret2, _ = service.generate_secret(mock_user)

        assert secret1 != secret2


@pytest.mark.unit
class TestCodeVerification:
    """Test TOTP code verification (valid/invalid)"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.totp_service.get_settings") as mock_settings:
            mock_settings.return_value.app_name = "Test"
            return TOTPService(mock_db)

    def test_verify_valid_code(self, service):
        """Test verification of a valid TOTP code"""
        import pyotp

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        mock_user = Mock()
        mock_user.totp_secret = secret

        assert service.verify_code(mock_user, valid_code) is True

    def test_verify_invalid_code(self, service):
        """Test verification rejects invalid code"""
        import pyotp

        secret = pyotp.random_base32()

        mock_user = Mock()
        mock_user.totp_secret = secret

        assert service.verify_code(mock_user, "000000") is False

    def test_verify_without_secret_returns_false(self, service):
        """Test verification returns False when no secret set"""
        mock_user = Mock()
        mock_user.totp_secret = None

        assert service.verify_code(mock_user, "123456") is False

    def test_verify_and_enable_with_valid_code(self, service, mock_db):
        """Test enabling 2FA with a valid code returns backup codes"""
        import pyotp

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        mock_user = Mock()
        mock_user.totp_secret = secret
        mock_user.totp_enabled = False

        backup_codes = service.verify_and_enable(mock_user, valid_code)

        assert len(backup_codes) == BACKUP_CODES_COUNT
        assert mock_user.totp_enabled is True
        assert mock_db.commit.called

    def test_verify_and_enable_with_invalid_code_raises(self, service):
        """Test enabling 2FA with invalid code raises TOTPError"""
        import pyotp

        secret = pyotp.random_base32()

        mock_user = Mock()
        mock_user.totp_secret = secret

        with pytest.raises(TOTPError, match="Invalid verification code"):
            service.verify_and_enable(mock_user, "000000")

    def test_verify_and_enable_without_secret_raises(self, service):
        """Test enabling 2FA without secret raises TOTPError"""
        mock_user = Mock()
        mock_user.totp_secret = None

        with pytest.raises(TOTPError, match="TOTP secret not set"):
            service.verify_and_enable(mock_user, "123456")


@pytest.mark.unit
class TestBackupCodes:
    """Test backup code generation and validation"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.totp_service.get_settings") as mock_settings:
            mock_settings.return_value.app_name = "Test"
            return TOTPService(mock_db)

    def test_generate_backup_codes_count(self, service):
        """Test correct number of backup codes generated"""
        codes = service._generate_backup_codes()
        assert len(codes) == BACKUP_CODES_COUNT

    def test_backup_codes_format(self, service):
        """Test backup codes are in XXXX-XXXX format"""
        codes = service._generate_backup_codes()
        for code in codes:
            assert "-" in code
            parts = code.split("-")
            assert len(parts) == 2
            assert len(parts[0]) == 4
            assert len(parts[1]) == 4

    def test_backup_codes_are_unique(self, service):
        """Test all backup codes are unique"""
        codes = service._generate_backup_codes()
        assert len(codes) == len(set(codes))

    def test_hash_backup_code_deterministic(self, service):
        """Test backup code hashing is deterministic"""
        h1 = service._hash_backup_code("ABCD-1234")
        h2 = service._hash_backup_code("ABCD-1234")
        assert h1 == h2

    def test_hash_backup_code_normalizes(self, service):
        """Test hashing normalizes dashes and case"""
        h1 = service._hash_backup_code("abcd-1234")
        h2 = service._hash_backup_code("ABCD1234")
        assert h1 == h2

    def test_verify_backup_code_success(self, service, mock_db):
        """Test verifying a valid backup code"""
        code = "ABCD-1234"
        code_hash = service._hash_backup_code(code)

        mock_user = Mock()
        mock_user.totp_backup_codes = [code_hash, "other_hash"]

        result = service.verify_backup_code(mock_user, code)

        assert result is True
        # Code should be removed after use
        assert mock_user.totp_backup_codes == ["other_hash"]
        assert mock_db.commit.called

    def test_verify_backup_code_invalid(self, service, mock_db):
        """Test verifying an invalid backup code"""
        mock_user = Mock()
        mock_user.totp_backup_codes = ["valid_hash"]

        result = service.verify_backup_code(mock_user, "WRONG-CODE")

        assert result is False

    def test_verify_backup_code_no_codes(self, service):
        """Test verifying when user has no backup codes"""
        mock_user = Mock()
        mock_user.totp_backup_codes = None

        result = service.verify_backup_code(mock_user, "ABCD-1234")
        assert result is False

    def test_backup_codes_count(self, service):
        """Test get_backup_codes_count returns correct count"""
        mock_user = Mock()
        mock_user.totp_backup_codes = ["hash1", "hash2", "hash3"]

        count = service.get_backup_codes_count(mock_user)
        assert count == 3

    def test_backup_codes_count_none(self, service):
        """Test get_backup_codes_count returns 0 when no codes"""
        mock_user = Mock()
        mock_user.totp_backup_codes = None

        count = service.get_backup_codes_count(mock_user)
        assert count == 0

    def test_disable_2fa_with_correct_password(self, service, mock_db):
        """Test disabling 2FA with correct password"""
        mock_user = Mock()
        mock_user.totp_enabled = True
        mock_user.totp_secret = "secret123"
        mock_user.hashed_password = "hashed"

        with patch("app.services.totp_service.AuthService") as mock_auth:
            mock_auth.verify_password.return_value = True
            result = service.disable(mock_user, "correct_password")

        assert result is True
        assert mock_user.totp_secret is None
        assert mock_user.totp_enabled is False

    def test_disable_2fa_with_wrong_password_raises(self, service, mock_db):
        """Test disabling 2FA with wrong password raises TOTPError"""
        mock_user = Mock()
        mock_user.hashed_password = "hashed"

        with patch("app.services.totp_service.AuthService") as mock_auth:
            mock_auth.verify_password.return_value = False
            with pytest.raises(TOTPError, match="Invalid password"):
                service.disable(mock_user, "wrong_password")
