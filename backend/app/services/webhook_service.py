"""
Webhook Service for real-time event notifications.

Supports:
- Custom webhook endpoints
- Multiple event types
- Retry logic with exponential backoff
- Signature verification (HMAC-SHA256)
"""

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base
from app.models import User

logger = logging.getLogger(__name__)


class WebhookEvent(str, Enum):
    """Types of webhook events"""
    # Alert events
    ALERT_CREATED = "alert.created"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    ALERT_RESOLVED = "alert.resolved"

    # Report events
    REPORT_RECEIVED = "report.received"
    REPORT_PROCESSED = "report.processed"

    # Threat events
    THREAT_DETECTED = "threat.detected"
    HIGH_FAILURE_RATE = "threat.high_failure_rate"

    # Policy events
    POLICY_RECOMMENDATION = "policy.recommendation"

    # System events
    HEALTH_CHECK = "system.health_check"


class WebhookEndpoint(Base):
    """Configured webhook endpoints"""
    __tablename__ = "webhook_endpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    secret = Column(String(64), nullable=True)  # For HMAC signing
    is_enabled = Column(Boolean, default=True, nullable=False, index=True)

    # Event filters (JSON array of event types to subscribe to)
    events = Column(JSONB, nullable=False)

    # Retry configuration
    max_retries = Column(Integer, default=3, nullable=False)
    retry_interval_seconds = Column(Integer, default=60, nullable=False)

    # Stats
    last_triggered_at = Column(DateTime, nullable=True)
    success_count = Column(Integer, default=0, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self):
        return f"<WebhookEndpoint(name={self.name}, url={self.url})>"


class WebhookDelivery(Base):
    """Log of webhook delivery attempts"""
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint_id = Column(UUID(as_uuid=True), ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False)

    event_type = Column(String(50), nullable=False, index=True)
    payload = Column(JSONB, nullable=False)

    # Delivery status
    success = Column(Boolean, nullable=True)
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(String(500), nullable=True)

    # Retry tracking
    attempt_number = Column(Integer, default=1, nullable=False)
    next_retry_at = Column(DateTime, nullable=True)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    delivered_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<WebhookDelivery(event={self.event_type}, success={self.success})>"


@dataclass
class WebhookPayload:
    """Webhook payload structure"""
    id: str
    event: str
    timestamp: str
    data: Dict[str, Any]


class WebhookService:
    """Service for managing and triggering webhooks"""

    def __init__(self, db: Session):
        self.db = db
        self.client = httpx.AsyncClient(timeout=30.0)

    async def trigger(
        self,
        event: WebhookEvent,
        data: Dict[str, Any],
    ) -> List[WebhookDelivery]:
        """
        Trigger webhooks for an event.

        Args:
            event: Event type
            data: Event data

        Returns:
            List of delivery records
        """
        # Find subscribed endpoints
        endpoints = self.db.query(WebhookEndpoint).filter(
            WebhookEndpoint.is_enabled == True,
        ).all()

        # Filter by event subscription
        subscribed = [e for e in endpoints if event.value in (e.events or [])]

        deliveries = []
        for endpoint in subscribed:
            delivery = await self._deliver(endpoint, event, data)
            deliveries.append(delivery)

        return deliveries

    async def _deliver(
        self,
        endpoint: WebhookEndpoint,
        event: WebhookEvent,
        data: Dict[str, Any],
    ) -> WebhookDelivery:
        """Deliver webhook to endpoint"""
        payload = {
            "id": str(uuid.uuid4()),
            "event": event.value,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }

        # Create delivery record
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            event_type=event.value,
            payload=payload,
            attempt_number=1,
        )
        self.db.add(delivery)
        self.db.commit()

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-ID": payload["id"],
            "X-Webhook-Event": event.value,
        }

        # Add signature if secret configured
        if endpoint.secret:
            signature = self._sign_payload(payload, endpoint.secret)
            headers["X-Webhook-Signature"] = signature

        # Attempt delivery
        start_time = time.time()
        try:
            response = await self.client.post(
                endpoint.url,
                json=payload,
                headers=headers,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            delivery.success = response.status_code < 400
            delivery.status_code = response.status_code
            delivery.response_body = response.text[:1000] if response.text else None
            delivery.delivered_at = datetime.utcnow()
            delivery.duration_ms = duration_ms

            if delivery.success:
                endpoint.success_count += 1
            else:
                endpoint.failure_count += 1
                # Schedule retry
                if delivery.attempt_number < endpoint.max_retries:
                    delivery.next_retry_at = datetime.utcnow() + timedelta(
                        seconds=endpoint.retry_interval_seconds * delivery.attempt_number
                    )

            endpoint.last_triggered_at = datetime.utcnow()

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            delivery.success = False
            delivery.error_message = str(e)[:500]
            delivery.duration_ms = duration_ms
            endpoint.failure_count += 1

            # Schedule retry
            if delivery.attempt_number < endpoint.max_retries:
                delivery.next_retry_at = datetime.utcnow() + timedelta(
                    seconds=endpoint.retry_interval_seconds * delivery.attempt_number
                )

            logger.error(f"Webhook delivery failed: {e}")

        self.db.commit()
        self.db.refresh(delivery)

        return delivery

    def _sign_payload(self, payload: Dict, secret: str) -> str:
        """Sign payload with HMAC-SHA256"""
        payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    # ==================== Endpoint Management ====================

    def create_endpoint(
        self,
        name: str,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> WebhookEndpoint:
        """Create a webhook endpoint"""
        endpoint = WebhookEndpoint(
            name=name,
            url=url,
            events=events,
            secret=secret,
            created_by=created_by,
        )
        self.db.add(endpoint)
        self.db.commit()
        self.db.refresh(endpoint)
        return endpoint

    def get_endpoints(self) -> List[WebhookEndpoint]:
        """Get all webhook endpoints"""
        return self.db.query(WebhookEndpoint).order_by(WebhookEndpoint.name).all()

    def get_endpoint(self, endpoint_id: uuid.UUID) -> Optional[WebhookEndpoint]:
        """Get endpoint by ID"""
        return self.db.query(WebhookEndpoint).filter(
            WebhookEndpoint.id == endpoint_id
        ).first()

    def update_endpoint(self, endpoint_id: uuid.UUID, **updates) -> Optional[WebhookEndpoint]:
        """Update endpoint"""
        endpoint = self.get_endpoint(endpoint_id)
        if not endpoint:
            return None

        for key, value in updates.items():
            if hasattr(endpoint, key):
                setattr(endpoint, key, value)

        self.db.commit()
        self.db.refresh(endpoint)
        return endpoint

    def delete_endpoint(self, endpoint_id: uuid.UUID) -> bool:
        """Delete endpoint"""
        endpoint = self.get_endpoint(endpoint_id)
        if not endpoint:
            return False

        self.db.delete(endpoint)
        self.db.commit()
        return True

    def get_deliveries(
        self,
        endpoint_id: Optional[uuid.UUID] = None,
        limit: int = 100,
    ) -> List[WebhookDelivery]:
        """Get delivery history"""
        query = self.db.query(WebhookDelivery)

        if endpoint_id:
            query = query.filter(WebhookDelivery.endpoint_id == endpoint_id)

        return query.order_by(WebhookDelivery.created_at.desc()).limit(limit).all()

    async def test_endpoint(self, endpoint: WebhookEndpoint) -> WebhookDelivery:
        """Send a test webhook"""
        return await self._deliver(
            endpoint,
            WebhookEvent.HEALTH_CHECK,
            {"message": "Test webhook from DMARC Dashboard", "timestamp": datetime.utcnow().isoformat()}
        )
