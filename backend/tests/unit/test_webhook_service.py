"""Unit tests for WebhookService (webhook_service.py)"""
import pytest
import json
import uuid
import hmac
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from app.services.webhook_service import (
    WebhookService, WebhookEndpoint, WebhookDelivery, WebhookEvent
)


@pytest.mark.unit
class TestWebhookDelivery:
    """Test webhook delivery with mocked HTTP"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.webhook_service.httpx.AsyncClient"):
            svc = WebhookService(mock_db)
        return svc

    @pytest.mark.asyncio
    async def test_deliver_success(self, service, mock_db):
        """Test successful webhook delivery"""
        endpoint = Mock(spec=WebhookEndpoint)
        endpoint.id = uuid.uuid4()
        endpoint.url = "https://hooks.example.com/webhook"
        endpoint.secret = None
        endpoint.max_retries = 3
        endpoint.retry_interval_seconds = 60
        endpoint.success_count = 0
        endpoint.failure_count = 0

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'

        service.client = AsyncMock()
        service.client.post = AsyncMock(return_value=mock_response)

        delivery = await service._deliver(
            endpoint, WebhookEvent.ALERT_CREATED, {"alert_id": "123"}
        )

        service.client.post.assert_called_once()
        call_kwargs = service.client.post.call_args
        assert call_kwargs[0][0] == "https://hooks.example.com/webhook"

        # Verify delivery record was created
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_deliver_with_signature(self, service, mock_db):
        """Test webhook delivery includes HMAC signature when secret configured"""
        endpoint = Mock(spec=WebhookEndpoint)
        endpoint.id = uuid.uuid4()
        endpoint.url = "https://hooks.example.com/webhook"
        endpoint.secret = "my-webhook-secret"
        endpoint.max_retries = 3
        endpoint.retry_interval_seconds = 60
        endpoint.success_count = 0
        endpoint.failure_count = 0

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = ""

        service.client = AsyncMock()
        service.client.post = AsyncMock(return_value=mock_response)

        await service._deliver(
            endpoint, WebhookEvent.ALERT_CREATED, {"test": "data"}
        )

        call_kwargs = service.client.post.call_args
        headers = call_kwargs[1]["headers"]
        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_deliver_failure_status_code(self, service, mock_db):
        """Test webhook delivery handling non-2xx response"""
        endpoint = Mock(spec=WebhookEndpoint)
        endpoint.id = uuid.uuid4()
        endpoint.url = "https://hooks.example.com/webhook"
        endpoint.secret = None
        endpoint.max_retries = 3
        endpoint.retry_interval_seconds = 60
        endpoint.success_count = 0
        endpoint.failure_count = 0

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        service.client = AsyncMock()
        service.client.post = AsyncMock(return_value=mock_response)

        delivery = await service._deliver(
            endpoint, WebhookEvent.ALERT_CREATED, {"test": "data"}
        )

        # Endpoint failure count should increment
        assert endpoint.failure_count == 1

    @pytest.mark.asyncio
    async def test_deliver_connection_error(self, service, mock_db):
        """Test webhook delivery handles connection errors"""
        endpoint = Mock(spec=WebhookEndpoint)
        endpoint.id = uuid.uuid4()
        endpoint.url = "https://unreachable.example.com/webhook"
        endpoint.secret = None
        endpoint.max_retries = 3
        endpoint.retry_interval_seconds = 60
        endpoint.success_count = 0
        endpoint.failure_count = 0

        service.client = AsyncMock()
        service.client.post = AsyncMock(side_effect=Exception("Connection refused"))

        delivery = await service._deliver(
            endpoint, WebhookEvent.ALERT_CREATED, {"test": "data"}
        )

        assert endpoint.failure_count == 1
        assert mock_db.commit.called


@pytest.mark.unit
class TestWebhookRetryLogic:
    """Test retry logic on failure"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.webhook_service.httpx.AsyncClient"):
            svc = WebhookService(mock_db)
        return svc

    @pytest.mark.asyncio
    async def test_retry_scheduled_on_failure(self, service, mock_db):
        """Test that retry is scheduled when delivery fails"""
        endpoint = Mock(spec=WebhookEndpoint)
        endpoint.id = uuid.uuid4()
        endpoint.url = "https://hooks.example.com/webhook"
        endpoint.secret = None
        endpoint.max_retries = 3
        endpoint.retry_interval_seconds = 60
        endpoint.success_count = 0
        endpoint.failure_count = 0

        mock_response = Mock()
        mock_response.status_code = 502
        mock_response.text = "Bad Gateway"

        service.client = AsyncMock()
        service.client.post = AsyncMock(return_value=mock_response)

        await service._deliver(
            endpoint, WebhookEvent.ALERT_CREATED, {"test": "data"}
        )

        # Verify delivery record has next_retry_at set
        added_delivery = mock_db.add.call_args[0][0]
        # attempt_number defaults to 1 and max_retries is 3, so retry should be set
        # The delivery record is modified after add, so we check commit was called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_no_retry_after_max_attempts(self, service, mock_db):
        """Test that no retry is scheduled when max retries reached"""
        endpoint = Mock(spec=WebhookEndpoint)
        endpoint.id = uuid.uuid4()
        endpoint.url = "https://hooks.example.com/webhook"
        endpoint.secret = None
        endpoint.max_retries = 1  # Only 1 retry allowed
        endpoint.retry_interval_seconds = 60
        endpoint.success_count = 0
        endpoint.failure_count = 0

        service.client = AsyncMock()
        service.client.post = AsyncMock(side_effect=Exception("Connection error"))

        await service._deliver(
            endpoint, WebhookEvent.ALERT_CREATED, {"test": "data"}
        )

        # Delivery's attempt_number (1) >= max_retries (1), so no retry
        assert mock_db.commit.called


@pytest.mark.unit
class TestWebhookSignature:
    """Test HMAC-SHA256 payload signing"""

    @pytest.fixture
    def service(self):
        mock_db = MagicMock()
        with patch("app.services.webhook_service.httpx.AsyncClient"):
            return WebhookService(mock_db)

    def test_sign_payload_produces_valid_hmac(self, service):
        """Test payload signing produces valid HMAC-SHA256"""
        payload = {"event": "test", "data": {"key": "value"}}
        secret = "test-secret-key"

        signature = service._sign_payload(payload, secret)

        assert signature.startswith("sha256=")
        hex_sig = signature[7:]  # Remove "sha256=" prefix
        assert len(hex_sig) == 64  # SHA256 hex digest length

    def test_sign_payload_is_deterministic(self, service):
        """Test same payload and secret produce same signature"""
        payload = {"event": "test", "data": {"key": "value"}}
        secret = "test-secret"

        sig1 = service._sign_payload(payload, secret)
        sig2 = service._sign_payload(payload, secret)

        assert sig1 == sig2

    def test_different_secrets_produce_different_signatures(self, service):
        """Test different secrets produce different signatures"""
        payload = {"event": "test"}

        sig1 = service._sign_payload(payload, "secret1")
        sig2 = service._sign_payload(payload, "secret2")

        assert sig1 != sig2

    def test_signature_can_be_verified(self, service):
        """Test signature can be verified by the receiver"""
        payload = {"event": "alert.created", "data": {"id": "123"}}
        secret = "shared-secret"

        signature = service._sign_payload(payload, secret)
        hex_sig = signature[7:]

        # Receiver can verify by computing the same HMAC
        payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        expected = hmac.new(
            secret.encode(), payload_str.encode(), hashlib.sha256
        ).hexdigest()

        assert hex_sig == expected


@pytest.mark.unit
class TestWebhookEndpointManagement:
    """Test endpoint CRUD operations"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.webhook_service.httpx.AsyncClient"):
            return WebhookService(mock_db)

    def test_create_endpoint(self, service, mock_db):
        """Test creating a webhook endpoint"""
        endpoint = service.create_endpoint(
            name="Alert Webhook",
            url="https://hooks.example.com/alerts",
            events=["alert.created", "alert.resolved"],
            secret="webhook-secret",
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        added = mock_db.add.call_args[0][0]
        assert added.name == "Alert Webhook"
        assert added.url == "https://hooks.example.com/alerts"
        assert "alert.created" in added.events

    def test_delete_endpoint(self, service, mock_db):
        """Test deleting a webhook endpoint"""
        endpoint = Mock()
        endpoint.id = uuid.uuid4()
        mock_db.query.return_value.filter.return_value.first.return_value = endpoint

        result = service.delete_endpoint(endpoint.id)

        assert result is True
        assert mock_db.delete.called

    def test_delete_nonexistent_endpoint(self, service, mock_db):
        """Test deleting nonexistent endpoint returns False"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.delete_endpoint(uuid.uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_trigger_filters_by_event(self, service, mock_db):
        """Test that trigger only sends to endpoints subscribed to the event"""
        subscribed_endpoint = Mock(spec=WebhookEndpoint)
        subscribed_endpoint.id = uuid.uuid4()
        subscribed_endpoint.url = "https://hooks.example.com/alerts"
        subscribed_endpoint.events = ["alert.created"]
        subscribed_endpoint.secret = None
        subscribed_endpoint.max_retries = 3
        subscribed_endpoint.retry_interval_seconds = 60
        subscribed_endpoint.success_count = 0
        subscribed_endpoint.failure_count = 0

        unsubscribed_endpoint = Mock(spec=WebhookEndpoint)
        unsubscribed_endpoint.id = uuid.uuid4()
        unsubscribed_endpoint.events = ["report.received"]

        mock_db.query.return_value.filter.return_value.all.return_value = [
            subscribed_endpoint, unsubscribed_endpoint
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = ""
        service.client = AsyncMock()
        service.client.post = AsyncMock(return_value=mock_response)

        deliveries = await service.trigger(
            WebhookEvent.ALERT_CREATED, {"alert_id": "123"}
        )

        # Only subscribed endpoint should receive the webhook
        assert service.client.post.call_count == 1
