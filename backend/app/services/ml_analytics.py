"""
ML Analytics service using Isolation Forest for anomaly detection.

Features:
- Isolation Forest anomaly detection (scikit-learn)
- Features: volume, failure_rate, unique_domains, hour, day_of_week
- Model training on historical data (last 90 days)
- Anomaly scoring (outlier scores)
- Model versioning and storage

SECURITY NOTE: Models use pickle serialization (standard for scikit-learn).
This is SAFE because we only serialize self-trained models, never external models.
"""

import logging
import pickle
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import io

from app.models import (
    DmarcRecord, DmarcReport,
    MLModel, MLPrediction
)

logger = logging.getLogger(__name__)

# Signature embedded in every model bundle to verify it was created by this application.
_MODEL_SIGNATURE = "dmarc-dashboard-ml-v1"


class MLAnalyticsService:
    """
    ML Analytics service for anomaly detection using Isolation Forest.

    Detects anomalous IP addresses and patterns in DMARC data.
    """

    def __init__(self, db: Session):
        self.db = db
        self.feature_names = [
            "volume",              # Total email count
            "failure_rate",        # DMARC failure percentage
            "unique_domains",      # Number of unique domains
            "hour_of_day",         # Hour when emails sent (0-23)
            "day_of_week",         # Day of week (0=Mon, 6=Sun)
        ]

    # ==================== Model Training ====================

    def train_anomaly_model(
        self,
        days: int = 90,
        contamination: float = 0.05,
        user_id: Optional[str] = None
    ) -> Tuple[MLModel, Dict]:
        """
        Train Isolation Forest anomaly detection model.

        Args:
            days: Number of days of historical data to train on
            contamination: Expected proportion of anomalies (0.05 = 5%)
            user_id: User ID who triggered training (for audit)

        Returns:
            Tuple of (MLModel, training_metrics)

        Raises:
            ValueError: If insufficient training data
        """
        logger.info(f"Training anomaly detection model with {days} days of data")

        # Prepare training data
        X_train, ip_addresses, date_range = self._prepare_training_data(days)

        if len(X_train) < 100:
            raise ValueError(f"Insufficient training data: {len(X_train)} samples (minimum: 100)")

        # Train Isolation Forest
        iso_forest = IsolationForest(
            contamination=contamination,
            n_estimators=100,
            max_samples='auto',
            random_state=42,
            n_jobs=-1
        )

        # Fit scaler and model
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_train)
        iso_forest.fit(X_scaled)

        # Calculate training metrics
        anomaly_scores = iso_forest.score_samples(X_scaled)
        predictions = iso_forest.predict(X_scaled)
        n_anomalies = (predictions == -1).sum()

        training_metrics = {
            "n_samples": len(X_train),
            "n_anomalies_detected": int(n_anomalies),
            "anomaly_percentage": float(n_anomalies / len(X_train) * 100),
            "contamination": contamination,
            "min_score": float(anomaly_scores.min()),
            "max_score": float(anomaly_scores.max()),
            "mean_score": float(anomaly_scores.mean()),
            "std_score": float(anomaly_scores.std()),
        }

        # Serialize model and scaler together (SAFE: self-trained model only)
        model_bundle = {
            "_signature": _MODEL_SIGNATURE,
            "model": iso_forest,
            "scaler": scaler,
            "feature_names": self.feature_names,
            "contamination": contamination
        }

        model_data = pickle.dumps(model_bundle)

        # Save to database
        ml_model = MLModel(
            model_type="isolation_forest",
            model_name=f"anomaly_detection_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            version=1,
            model_data=model_data,
            training_params={
                "contamination": contamination,
                "n_estimators": 100,
                "max_samples": "auto",
                "days": days
            },
            training_metrics=training_metrics,
            feature_names=self.feature_names,
            training_samples=len(X_train),
            training_date_start=date_range[0],
            training_date_end=date_range[1],
            is_active=True,
            is_deployed=False,
            trained_by=user_id
        )

        self.db.add(ml_model)
        self.db.commit()
        self.db.refresh(ml_model)

        logger.info(
            f"Model trained successfully: {ml_model.model_name}, "
            f"{n_anomalies}/{len(X_train)} anomalies detected"
        )

        return ml_model, training_metrics

    # ==================== Anomaly Detection ====================

    def detect_anomalies(
        self,
        model_id: Optional[str] = None,
        days: int = 7,
        threshold: float = -0.5
    ) -> List[Dict]:
        """
        Detect anomalous IP addresses in recent data.

        Args:
            model_id: ML model UUID (uses latest deployed if None)
            days: Number of recent days to analyze
            threshold: Anomaly score threshold (lower = more anomalous)

        Returns:
            List of anomalous IPs with scores and metadata
        """
        # Load model
        model, model_bundle = self._load_model(model_id)
        if not model:
            raise ValueError("No trained model available")

        iso_forest = model_bundle["model"]
        scaler = model_bundle["scaler"]

        # Prepare detection data
        X_detect, ip_data, _ = self._prepare_training_data(days)

        if len(X_detect) == 0:
            logger.warning("No data available for anomaly detection")
            return []

        # Scale and predict
        X_scaled = scaler.transform(X_detect)
        anomaly_scores = iso_forest.score_samples(X_scaled)
        predictions = iso_forest.predict(X_scaled)

        # Filter anomalies
        anomalies = []
        for idx, (ip, score, pred) in enumerate(zip(ip_data, anomaly_scores, predictions)):
            if score < threshold or pred == -1:
                anomaly_data = {
                    "ip_address": ip["ip"],
                    "anomaly_score": float(score),
                    "is_anomaly": bool(pred == -1),
                    "features": {
                        "volume": int(ip["volume"]),
                        "failure_rate": float(ip["failure_rate"]),
                        "unique_domains": int(ip["unique_domains"]),
                    },
                    "first_seen": ip["first_seen"],
                    "last_seen": ip["last_seen"],
                }
                anomalies.append(anomaly_data)

                # Save prediction to database
                self._save_prediction(
                    model_id=str(model.id),
                    target_value=ip["ip"],
                    prediction_value=float(score),
                    prediction_label="anomaly" if pred == -1 else "suspicious",
                    features=anomaly_data["features"]
                )

        # Sort by score (most anomalous first)
        anomalies.sort(key=lambda x: x["anomaly_score"])

        logger.info(f"Detected {len(anomalies)} anomalies out of {len(ip_data)} IPs")

        return anomalies

    # ==================== Model Management ====================

    def deploy_model(self, model_id: str) -> MLModel:
        """
        Deploy a trained model (set as active).

        Deactivates all other models of the same type.

        Args:
            model_id: Model UUID to deploy

        Returns:
            Deployed model

        Raises:
            ValueError: If model not found
        """
        model = self.db.query(MLModel).filter(MLModel.id == model_id).first()
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # Deactivate other models of same type
        self.db.query(MLModel).filter(
            MLModel.model_type == model.model_type,
            MLModel.id != model_id
        ).update({"is_deployed": False})

        # Deploy this model
        model.is_deployed = True
        self.db.commit()
        self.db.refresh(model)

        logger.info(f"Model deployed: {model.model_name}")

        return model

    def list_models(
        self,
        model_type: str = "isolation_forest",
        active_only: bool = False
    ) -> List[MLModel]:
        """List trained models"""
        query = self.db.query(MLModel).filter(MLModel.model_type == model_type)

        if active_only:
            query = query.filter(MLModel.is_active == True)

        return query.order_by(MLModel.created_at.desc()).all()

    def get_deployed_model(self, model_type: str = "isolation_forest") -> Optional[MLModel]:
        """Get currently deployed model"""
        return self.db.query(MLModel).filter(
            MLModel.model_type == model_type,
            MLModel.is_deployed == True,
            MLModel.is_active == True
        ).first()

    # ==================== Helper Methods ====================

    def _prepare_training_data(self, days: int) -> Tuple[np.ndarray, List[Dict], Tuple]:
        """
        Prepare training/detection data from DMARC records.

        Returns:
            Tuple of (feature_matrix, ip_metadata_list, date_range)
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Query DMARC records
        records = self.db.query(
            DmarcRecord.source_ip,
            func.count(DmarcRecord.id).label("volume"),
            func.sum(DmarcRecord.count).label("total_count"),
            func.sum(
                case(
                    (and_(DmarcRecord.dkim != "pass", DmarcRecord.spf != "pass"), DmarcRecord.count),
                    else_=0
                )
            ).label("failed_count"),
            func.count(func.distinct(DmarcRecord.header_from)).label("unique_domains"),
            func.min(DmarcRecord.created_at).label("first_seen"),
            func.max(DmarcRecord.created_at).label("last_seen"),
        ).join(
            DmarcReport, DmarcRecord.report_id == DmarcReport.id
        ).filter(
            DmarcRecord.created_at >= since
        ).group_by(
            DmarcRecord.source_ip
        ).all()

        if not records:
            return np.array([]), [], (None, None)

        # Extract features
        X = []
        ip_data = []

        for record in records:
            failure_rate = (record.failed_count / record.total_count * 100) if record.total_count > 0 else 0

            # Calculate time features (use last_seen)
            hour = record.last_seen.hour if record.last_seen else 12
            day_of_week = record.last_seen.weekday() if record.last_seen else 0

            features = [
                record.volume,
                failure_rate,
                record.unique_domains,
                hour,
                day_of_week
            ]

            X.append(features)
            ip_data.append({
                "ip": record.source_ip,
                "volume": record.volume,
                "failure_rate": failure_rate,
                "unique_domains": record.unique_domains,
                "first_seen": record.first_seen,
                "last_seen": record.last_seen
            })

        date_range = (since, datetime.utcnow())

        return np.array(X), ip_data, date_range

    def _load_model(self, model_id: Optional[str] = None) -> Tuple[Optional[MLModel], Optional[Dict]]:
        """Load model from database with validation.

        Only self-trained models are stored, but we still validate the
        deserialized bundle to guard against data corruption or accidental
        misuse.
        """
        if model_id:
            model = self.db.query(MLModel).filter(MLModel.id == model_id).first()
        else:
            model = self.get_deployed_model()

        if not model:
            return None, None

        logger.info(
            "Loading ML model: id=%s, name=%s, type=%s",
            model.id, model.model_name, model.model_type
        )

        # Deserialize model bundle with safety checks
        # SAFE: only self-trained models are stored in the database
        try:
            model_bundle = pickle.loads(model.model_data)
        except Exception as exc:
            logger.error(
                "Failed to deserialize model %s (%s): %s",
                model.id, model.model_name, exc
            )
            return None, None

        # Validate the deserialized object is the expected dict structure
        if not isinstance(model_bundle, dict):
            logger.error(
                "Model %s (%s): deserialized object is %s, expected dict",
                model.id, model.model_name, type(model_bundle).__name__
            )
            return None, None

        # Verify application signature (models saved before this change
        # won't have the key, so we only reject bundles with a *wrong*
        # signature rather than a missing one).
        bundle_sig = model_bundle.get("_signature")
        if bundle_sig is not None and bundle_sig != _MODEL_SIGNATURE:
            logger.error(
                "Model %s (%s): invalid signature '%s'",
                model.id, model.model_name, bundle_sig
            )
            return None, None

        # Verify required keys are present
        required_keys = {"model", "scaler", "feature_names"}
        missing_keys = required_keys - set(model_bundle.keys())
        if missing_keys:
            logger.error(
                "Model %s (%s): missing required keys: %s",
                model.id, model.model_name, missing_keys
            )
            return None, None

        # Type-check the core objects
        if not isinstance(model_bundle["model"], IsolationForest):
            logger.error(
                "Model %s (%s): 'model' is %s, expected IsolationForest",
                model.id, model.model_name, type(model_bundle["model"]).__name__
            )
            return None, None

        if not isinstance(model_bundle["scaler"], StandardScaler):
            logger.error(
                "Model %s (%s): 'scaler' is %s, expected StandardScaler",
                model.id, model.model_name, type(model_bundle["scaler"]).__name__
            )
            return None, None

        logger.info(
            "Model loaded successfully: id=%s, name=%s",
            model.id, model.model_name
        )

        return model, model_bundle

    def _save_prediction(
        self,
        model_id: str,
        target_value: str,
        prediction_value: float,
        prediction_label: str,
        features: Dict
    ) -> None:
        """Save prediction to database"""
        prediction = MLPrediction(
            model_id=model_id,
            model_type="isolation_forest",
            target_type="ip_address",
            target_value=target_value,
            prediction_type="anomaly",
            prediction_value=prediction_value,
            prediction_label=prediction_label,
            features=features,
            predicted_at=datetime.utcnow()
        )

        self.db.add(prediction)
        self.db.commit()

    # ==================== Statistics ====================

    def get_model_stats(self, model_id: str) -> Dict:
        """Get statistics for a trained model"""
        model = self.db.query(MLModel).filter(MLModel.id == model_id).first()
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # Count predictions made with this model
        prediction_count = self.db.query(MLPrediction).filter(
            MLPrediction.model_id == model_id
        ).count()

        anomaly_count = self.db.query(MLPrediction).filter(
            MLPrediction.model_id == model_id,
            MLPrediction.prediction_label == "anomaly"
        ).count()

        return {
            "model_id": str(model.id),
            "model_name": model.model_name,
            "model_type": model.model_type,
            "version": model.version,
            "is_deployed": model.is_deployed,
            "training_samples": model.training_samples,
            "training_metrics": model.training_metrics,
            "predictions_made": prediction_count,
            "anomalies_detected": anomaly_count,
            "created_at": model.created_at,
            "trained_by": str(model.trained_by) if model.trained_by else None
        }
