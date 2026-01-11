"""
Data retention models for automated purge policies.

Implements configurable retention policies for:
- DMARC reports and records
- Audit logs
- Alert history
- Analytics cache
"""

from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.database import Base


class RetentionTarget(str, enum.Enum):
    """Types of data that can have retention policies"""
    DMARC_REPORTS = "dmarc_reports"
    DMARC_RECORDS = "dmarc_records"
    AUDIT_LOGS = "audit_logs"
    ALERT_HISTORY = "alert_history"
    THREAT_INTEL_CACHE = "threat_intel_cache"
    ANALYTICS_CACHE = "analytics_cache"
    ML_PREDICTIONS = "ml_predictions"
    PASSWORD_RESET_TOKENS = "password_reset_tokens"
    REFRESH_TOKENS = "refresh_tokens"


class RetentionPolicy(Base):
    """
    Data retention policy configuration.

    Defines how long different types of data should be kept
    before automatic deletion.
    """
    __tablename__ = "retention_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Policy identification
    name = Column(String(100), unique=True, nullable=False, index=True)
    target = Column(String(50), nullable=False, index=True)  # RetentionTarget value
    description = Column(String(500), nullable=True)

    # Retention configuration
    retention_days = Column(Integer, nullable=False)  # Days to keep data
    is_enabled = Column(Boolean, default=True, nullable=False)

    # Optional filters (JSON)
    # e.g., {"domain": "*.example.com"} to only apply to specific domains
    filters = Column(JSONB, nullable=True)

    # Execution tracking
    last_run_at = Column(DateTime, nullable=True)
    last_run_deleted = Column(Integer, nullable=True)  # Count deleted in last run
    total_deleted = Column(Integer, default=0, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    created_by_user = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<RetentionPolicy(name={self.name}, target={self.target}, days={self.retention_days})>"


class RetentionLog(Base):
    """
    Log of retention policy executions.

    Tracks what was deleted and when for audit purposes.
    """
    __tablename__ = "retention_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Policy reference
    policy_id = Column(UUID(as_uuid=True), ForeignKey("retention_policies.id", ondelete="SET NULL"), nullable=True)
    policy_name = Column(String(100), nullable=False)  # Denormalized for history

    # Execution details
    target = Column(String(50), nullable=False)
    retention_days = Column(Integer, nullable=False)
    records_deleted = Column(Integer, nullable=False)
    cutoff_date = Column(DateTime, nullable=False)

    # Status
    success = Column(Boolean, nullable=False)
    error_message = Column(String(500), nullable=True)

    # Metadata
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=True)

    # Relationships
    policy = relationship("RetentionPolicy", foreign_keys=[policy_id])

    def __repr__(self):
        return f"<RetentionLog(policy={self.policy_name}, deleted={self.records_deleted})>"
