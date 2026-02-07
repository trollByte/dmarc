"""Unit tests for API key authentication.

Tests API key generation, SHA256 hashing, key validation,
and X-API-Key header authentication flow.
"""
import hashlib
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.dependencies.auth import AuthDependencies
from app.models.user import User, UserAPIKey, UserRole
from app.services.auth_service import AuthService


@pytest.mark.unit
class TestAPIKeyGeneration:
    """Test API key generation returns correct structure."""

    def test_generate_returns_three_parts(self):
        """generate_api_key returns (api_key, key_hash, key_prefix)."""
        api_key, key_hash, key_prefix = AuthService.generate_api_key()
        assert api_key is not None
        assert key_hash is not None
        assert key_prefix is not None

    def test_key_format_and_length(self):
        """Key is 'dmarc_' + 64 hex chars = 70 chars total."""
        api_key, _, _ = AuthService.generate_api_key()
        assert api_key.startswith("dmarc_")
        assert len(api_key) == 70

    def test_prefix_is_first_eight_chars(self):
        """key_prefix is the first 8 characters of the full key."""
        api_key, _, key_prefix = AuthService.generate_api_key()
        assert key_prefix == api_key[:8]

    def test_each_key_is_unique(self):
        """Two generated keys must differ (cryptographic randomness)."""
        key1, _, _ = AuthService.generate_api_key()
        key2, _, _ = AuthService.generate_api_key()
        assert key1 != key2


@pytest.mark.unit
class TestAPIKeyHashing:
    """Test SHA256 hashing -- plaintext is never stored."""

    def test_hash_matches_sha256(self):
        """hash_api_key produces a standard SHA256 hex digest."""
        api_key = "dmarc_abc123"
        expected = hashlib.sha256(api_key.encode()).hexdigest()
        assert AuthService.hash_api_key(api_key) == expected

    def test_hash_is_not_plaintext(self):
        """The stored hash must not equal the original key."""
        api_key, key_hash, _ = AuthService.generate_api_key()
        assert key_hash != api_key

    def test_generated_hash_matches_manual_hash(self):
        """Hash from generate_api_key equals hash_api_key(key)."""
        api_key, key_hash, _ = AuthService.generate_api_key()
        assert key_hash == AuthService.hash_api_key(api_key)

    def test_hash_is_64_hex_chars(self):
        """SHA256 hex digest is exactly 64 hex characters."""
        _, key_hash, _ = AuthService.generate_api_key()
        assert len(key_hash) == 64
        assert all(c in "0123456789abcdef" for c in key_hash)


@pytest.mark.unit
class TestValidateAPIKey:
    """Test validate_api_key with various key states."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def active_user(self):
        user = Mock(spec=User)
        user.id = uuid.uuid4()
        user.username = "analyst"
        user.is_active = True
        user.is_locked = False
        user.role = UserRole.ANALYST.value
        return user

    @pytest.fixture
    def active_key(self, active_user):
        key_obj = Mock(spec=UserAPIKey)
        key_obj.user_id = active_user.id
        key_obj.is_active = True
        key_obj.expires_at = datetime.utcnow() + timedelta(days=30)
        key_obj.last_used = None
        return key_obj

    def test_valid_key_returns_user(self, mock_db, active_user, active_key):
        """A valid, active, unexpired key returns the associated user."""
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            active_key, active_user,
        ]
        result = AuthService.validate_api_key(mock_db, "dmarc_validkey")
        assert result is active_user
        mock_db.commit.assert_called_once()

    def test_valid_key_updates_last_used(self, mock_db, active_user, active_key):
        """Successful validation updates the last_used timestamp."""
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            active_key, active_user,
        ]
        AuthService.validate_api_key(mock_db, "dmarc_validkey")
        assert active_key.last_used is not None

    def test_nonexistent_key_returns_none(self, mock_db):
        """A key hash not in the database returns None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert AuthService.validate_api_key(mock_db, "dmarc_doesnotexist") is None

    def test_expired_key_returns_none(self, mock_db, active_key):
        """An expired key returns None even if it is active."""
        active_key.expires_at = datetime.utcnow() - timedelta(days=1)
        mock_db.query.return_value.filter.return_value.first.return_value = active_key
        assert AuthService.validate_api_key(mock_db, "dmarc_expiredkey") is None

    def test_inactive_key_returns_none(self, mock_db):
        """A revoked/inactive key is filtered out by the query."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert AuthService.validate_api_key(mock_db, "dmarc_revokedkey") is None

    def test_locked_user_returns_none(self, mock_db, active_key):
        """A valid key for a locked user returns None."""
        locked_user = Mock(spec=User)
        locked_user.id = active_key.user_id
        locked_user.is_active = True
        locked_user.is_locked = True
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            active_key, locked_user,
        ]
        assert AuthService.validate_api_key(mock_db, "dmarc_lockeduser") is None

    def test_inactive_user_returns_none(self, mock_db, active_key):
        """A valid key for a deactivated user returns None."""
        inactive_user = Mock(spec=User)
        inactive_user.id = active_key.user_id
        inactive_user.is_active = False
        inactive_user.is_locked = False
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            active_key, inactive_user,
        ]
        assert AuthService.validate_api_key(mock_db, "dmarc_inactiveuser") is None


@pytest.mark.unit
class TestXAPIKeyHeaderAuth:
    """Test the X-API-Key header authentication dependency."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def active_user(self):
        user = Mock(spec=User)
        user.id = uuid.uuid4()
        user.username = "apiuser"
        user.is_active = True
        user.is_locked = False
        user.role = UserRole.VIEWER.value
        return user

    @pytest.mark.asyncio
    async def test_valid_api_key_header_authenticates(self, mock_db, active_user):
        """X-API-Key header with a valid key returns the user."""
        with patch.object(AuthService, "validate_api_key", return_value=active_user):
            user = await AuthDependencies.get_current_user(
                credentials=None, x_api_key="dmarc_validheaderkey", db=mock_db,
            )
        assert user is active_user

    @pytest.mark.asyncio
    async def test_invalid_api_key_header_raises_401(self, mock_db):
        """X-API-Key header with an invalid key raises 401."""
        with patch.object(AuthService, "validate_api_key", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await AuthDependencies.get_current_user(
                    credentials=None, x_api_key="dmarc_badkey", db=mock_db,
                )
        assert exc_info.value.status_code == 401
        assert "Invalid or expired API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_no_credentials_raises_401(self, mock_db):
        """No JWT token and no X-API-Key header raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            await AuthDependencies.get_current_user(
                credentials=None, x_api_key=None, db=mock_db,
            )
        assert exc_info.value.status_code == 401
        assert "No authentication credentials provided" in exc_info.value.detail
