"""
Data Retention Service for automated purge policies.

Provides:
- Policy management (CRUD)
- Policy execution (data purging)
- Scheduled cleanup tasks
- Retention reporting
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import (
    RetentionPolicy, RetentionLog, RetentionTarget,
    DmarcReport, DmarcRecord, AuditLog, AlertHistory,
    MLPrediction, AnalyticsCache, PasswordResetToken, RefreshToken
)

logger = logging.getLogger(__name__)


class RetentionError(Exception):
    """Raised when retention operation fails"""
    pass


class RetentionService:
    """Service for managing data retention policies"""

    # Mapping of targets to their model classes and date fields
    TARGET_CONFIG = {
        RetentionTarget.DMARC_REPORTS.value: {
            "model": DmarcReport,
            "date_field": "date_begin",
            "cascade_delete": True,  # Records are cascade deleted
        },
        RetentionTarget.DMARC_RECORDS.value: {
            "model": DmarcRecord,
            "date_field": "created_at",
            "cascade_delete": False,
        },
        RetentionTarget.AUDIT_LOGS.value: {
            "model": AuditLog,
            "date_field": "created_at",
            "cascade_delete": False,
        },
        RetentionTarget.ALERT_HISTORY.value: {
            "model": AlertHistory,
            "date_field": "created_at",
            "cascade_delete": False,
        },
        RetentionTarget.ML_PREDICTIONS.value: {
            "model": MLPrediction,
            "date_field": "created_at",
            "cascade_delete": False,
        },
        RetentionTarget.ANALYTICS_CACHE.value: {
            "model": AnalyticsCache,
            "date_field": "created_at",
            "cascade_delete": False,
        },
        RetentionTarget.PASSWORD_RESET_TOKENS.value: {
            "model": PasswordResetToken,
            "date_field": "created_at",
            "cascade_delete": False,
        },
        RetentionTarget.REFRESH_TOKENS.value: {
            "model": RefreshToken,
            "date_field": "created_at",
            "cascade_delete": False,
        },
    }

    def __init__(self, db: Session):
        self.db = db

    # ==================== Policy Management ====================

    def create_policy(
        self,
        name: str,
        target: RetentionTarget,
        retention_days: int,
        description: Optional[str] = None,
        filters: Optional[Dict] = None,
        is_enabled: bool = True,
        created_by: Optional[UUID] = None,
    ) -> RetentionPolicy:
        """Create a new retention policy"""
        # Check for duplicate name
        existing = self.db.query(RetentionPolicy).filter(
            RetentionPolicy.name == name
        ).first()
        if existing:
            raise RetentionError(f"Policy with name '{name}' already exists")

        policy = RetentionPolicy(
            name=name,
            target=target.value,
            retention_days=retention_days,
            description=description,
            filters=filters,
            is_enabled=is_enabled,
            created_by=created_by,
        )

        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)

        logger.info(f"Created retention policy: {name} ({target.value}, {retention_days} days)")

        return policy

    def update_policy(
        self,
        policy_id: UUID,
        **updates,
    ) -> RetentionPolicy:
        """Update a retention policy"""
        policy = self.db.query(RetentionPolicy).filter(
            RetentionPolicy.id == policy_id
        ).first()

        if not policy:
            raise RetentionError("Policy not found")

        for key, value in updates.items():
            if hasattr(policy, key):
                setattr(policy, key, value)

        self.db.commit()
        self.db.refresh(policy)

        logger.info(f"Updated retention policy: {policy.name}")

        return policy

    def delete_policy(self, policy_id: UUID) -> bool:
        """Delete a retention policy"""
        policy = self.db.query(RetentionPolicy).filter(
            RetentionPolicy.id == policy_id
        ).first()

        if not policy:
            raise RetentionError("Policy not found")

        name = policy.name
        self.db.delete(policy)
        self.db.commit()

        logger.info(f"Deleted retention policy: {name}")

        return True

    def get_policy(self, policy_id: UUID) -> Optional[RetentionPolicy]:
        """Get a policy by ID"""
        return self.db.query(RetentionPolicy).filter(
            RetentionPolicy.id == policy_id
        ).first()

    def get_policies(
        self,
        target: Optional[str] = None,
        is_enabled: Optional[bool] = None,
    ) -> List[RetentionPolicy]:
        """Get all policies with optional filters"""
        query = self.db.query(RetentionPolicy)

        if target:
            query = query.filter(RetentionPolicy.target == target)
        if is_enabled is not None:
            query = query.filter(RetentionPolicy.is_enabled == is_enabled)

        return query.order_by(RetentionPolicy.name).all()

    # ==================== Policy Execution ====================

    def execute_policy(self, policy: RetentionPolicy) -> RetentionLog:
        """Execute a single retention policy"""
        start_time = time.time()
        cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)

        config = self.TARGET_CONFIG.get(policy.target)
        if not config:
            return self._create_log(
                policy=policy,
                cutoff_date=cutoff_date,
                records_deleted=0,
                success=False,
                error_message=f"Unknown target: {policy.target}",
                duration=0,
            )

        try:
            model = config["model"]
            date_field = getattr(model, config["date_field"])

            # Build query
            query = self.db.query(model).filter(date_field < cutoff_date)

            # Apply filters if any
            if policy.filters:
                query = self._apply_filters(query, model, policy.filters)

            # Count and delete
            count = query.count()
            if count > 0:
                query.delete(synchronize_session=False)
                self.db.commit()

            # Update policy stats
            policy.last_run_at = datetime.utcnow()
            policy.last_run_deleted = count
            policy.total_deleted += count
            self.db.commit()

            duration = int(time.time() - start_time)

            log = self._create_log(
                policy=policy,
                cutoff_date=cutoff_date,
                records_deleted=count,
                success=True,
                duration=duration,
            )

            logger.info(
                f"Executed retention policy '{policy.name}': "
                f"deleted {count} records older than {cutoff_date.date()}"
            )

            return log

        except Exception as e:
            self.db.rollback()
            duration = int(time.time() - start_time)

            log = self._create_log(
                policy=policy,
                cutoff_date=cutoff_date,
                records_deleted=0,
                success=False,
                error_message=str(e),
                duration=duration,
            )

            logger.error(f"Failed to execute retention policy '{policy.name}': {e}")

            return log

    def execute_all_policies(self) -> List[RetentionLog]:
        """Execute all enabled retention policies"""
        policies = self.get_policies(is_enabled=True)
        logs = []

        for policy in policies:
            log = self.execute_policy(policy)
            logs.append(log)

        return logs

    def preview_policy(self, policy: RetentionPolicy) -> Dict[str, Any]:
        """Preview what would be deleted by a policy"""
        cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)

        config = self.TARGET_CONFIG.get(policy.target)
        if not config:
            return {"error": f"Unknown target: {policy.target}"}

        model = config["model"]
        date_field = getattr(model, config["date_field"])

        query = self.db.query(func.count()).select_from(model).filter(
            date_field < cutoff_date
        )

        if policy.filters:
            query = self._apply_filters(query, model, policy.filters)

        count = query.scalar() or 0

        return {
            "target": policy.target,
            "retention_days": policy.retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "records_to_delete": count,
        }

    def _apply_filters(self, query, model, filters: Dict):
        """Apply JSON filters to query"""
        for field, value in filters.items():
            if hasattr(model, field):
                column = getattr(model, field)
                if isinstance(value, str) and value.startswith("*"):
                    # Wildcard suffix match
                    query = query.filter(column.like(f"%{value[1:]}"))
                elif isinstance(value, str) and value.endswith("*"):
                    # Wildcard prefix match
                    query = query.filter(column.like(f"{value[:-1]}%"))
                else:
                    query = query.filter(column == value)
        return query

    def _create_log(
        self,
        policy: RetentionPolicy,
        cutoff_date: datetime,
        records_deleted: int,
        success: bool,
        error_message: Optional[str] = None,
        duration: int = 0,
    ) -> RetentionLog:
        """Create a retention execution log"""
        log = RetentionLog(
            policy_id=policy.id,
            policy_name=policy.name,
            target=policy.target,
            retention_days=policy.retention_days,
            records_deleted=records_deleted,
            cutoff_date=cutoff_date,
            success=success,
            error_message=error_message,
            duration_seconds=duration,
        )

        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        return log

    # ==================== Reporting ====================

    def get_logs(
        self,
        policy_id: Optional[UUID] = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[RetentionLog]:
        """Get retention execution logs"""
        since = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(RetentionLog).filter(
            RetentionLog.executed_at >= since
        )

        if policy_id:
            query = query.filter(RetentionLog.policy_id == policy_id)

        return query.order_by(RetentionLog.executed_at.desc()).limit(limit).all()

    def get_stats(self) -> Dict[str, Any]:
        """Get retention statistics"""
        policies = self.get_policies()

        total_deleted = sum(p.total_deleted for p in policies)
        enabled_count = sum(1 for p in policies if p.is_enabled)

        # Get data sizes
        sizes = {}
        for target, config in self.TARGET_CONFIG.items():
            model = config["model"]
            count = self.db.query(func.count()).select_from(model).scalar() or 0
            sizes[target] = count

        return {
            "policies": {
                "total": len(policies),
                "enabled": enabled_count,
            },
            "total_records_deleted": total_deleted,
            "data_sizes": sizes,
        }

    def create_default_policies(self) -> List[RetentionPolicy]:
        """Create default retention policies if none exist"""
        existing = self.get_policies()
        if existing:
            return existing

        defaults = [
            {
                "name": "DMARC Reports - 1 Year",
                "target": RetentionTarget.DMARC_REPORTS,
                "retention_days": 365,
                "description": "Keep DMARC reports for 1 year",
                "is_enabled": False,  # Disabled by default
            },
            {
                "name": "Audit Logs - 90 Days",
                "target": RetentionTarget.AUDIT_LOGS,
                "retention_days": 90,
                "description": "Keep audit logs for 90 days",
                "is_enabled": False,
            },
            {
                "name": "Alert History - 180 Days",
                "target": RetentionTarget.ALERT_HISTORY,
                "retention_days": 180,
                "description": "Keep alert history for 6 months",
                "is_enabled": False,
            },
            {
                "name": "Analytics Cache - 30 Days",
                "target": RetentionTarget.ANALYTICS_CACHE,
                "retention_days": 30,
                "description": "Keep analytics cache for 30 days",
                "is_enabled": True,  # Enable this one
            },
            {
                "name": "Expired Tokens - 7 Days",
                "target": RetentionTarget.PASSWORD_RESET_TOKENS,
                "retention_days": 7,
                "description": "Clean up expired password reset tokens",
                "is_enabled": True,
            },
            {
                "name": "Refresh Tokens - 30 Days",
                "target": RetentionTarget.REFRESH_TOKENS,
                "retention_days": 30,
                "description": "Clean up old refresh tokens",
                "is_enabled": True,
            },
        ]

        policies = []
        for config in defaults:
            policy = self.create_policy(**config)
            policies.append(policy)

        logger.info(f"Created {len(policies)} default retention policies")

        return policies
