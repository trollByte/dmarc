"""
Saved View Models

Stores user-created saved views/filter combinations.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class SavedView(Base):
    """Saved dashboard view/filter combination"""
    __tablename__ = "saved_views"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # View metadata
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)  # Optional icon identifier

    # Filter configuration (stored as JSON)
    filters = Column(JSONB, nullable=False, default={})
    # Example filters structure:
    # {
    #   "domain": "example.com",
    #   "disposition": "reject",
    #   "dateRange": "7d",
    #   "startDate": "2026-01-01",
    #   "endDate": "2026-01-07",
    #   "sourceIp": "192.168.1.1",
    #   "minCount": 100,
    #   "dkimResult": "pass",
    #   "spfResult": "fail"
    # }

    # Display preferences
    display_settings = Column(JSONB, nullable=True, default={})
    # Example display_settings structure:
    # {
    #   "sortBy": "date",
    #   "sortOrder": "desc",
    #   "pageSize": 25,
    #   "visibleColumns": ["domain", "source_ip", "count"],
    #   "chartType": "bar"
    # }

    # Sharing
    is_shared = Column(Boolean, default=False, nullable=False)  # Visible to all users
    is_default = Column(Boolean, default=False, nullable=False)  # User's default view

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    # Relationship
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<SavedView(id={self.id}, name={self.name}, user_id={self.user_id})>"

    def update_last_used(self):
        """Update the last used timestamp"""
        self.last_used_at = datetime.utcnow()
