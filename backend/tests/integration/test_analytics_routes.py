"""Integration tests for analytics API routes."""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User, UserRole, MLModel, MLPrediction, DmarcRecord
from app.services.auth_service import AuthService


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    hashed = AuthService.hash_password("AdminPassword123!")
    user = User(
        username="analyticsadmin",
        email="analyticsadmin@example.com",
        hashed_password=hashed,
        role=UserRole.ADMIN.value,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def viewer_user(db_session):
    hashed = AuthService.hash_password("ViewerPassword123!")
    user = User(
        username="analyticsviewer",
        email="analyticsviewer@example.com",
        hashed_password=hashed,
        role=UserRole.VIEWER.value,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def analyst_user(db_session):
    hashed = AuthService.hash_password("AnalystPassword123!")
    user = User(
        username="analyticsanalyst",
        email="analyticsanalyst@example.com",
        hashed_password=hashed,
        role=UserRole.ANALYST.value,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    return AuthService.create_access_token(
        str(admin_user.id), admin_user.username, UserRole.ADMIN
    )


@pytest.fixture
def viewer_token(viewer_user):
    return AuthService.create_access_token(
        str(viewer_user.id), viewer_user.username, UserRole.VIEWER
    )


@pytest.fixture
def analyst_token(analyst_user):
    return AuthService.create_access_token(
        str(analyst_user.id), analyst_user.username, UserRole.ANALYST
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_ml_model(db_session, admin_user):
    """Create a sample ML model in the database."""
    # Store minimal bytes as model_data; the column requires a non-null binary blob.
    model_data = b"fake-model-bytes"

    model = MLModel(
        id=uuid.uuid4(),
        model_type="isolation_forest",
        model_name="test_anomaly_model_v1",
        version=1,
        model_data=model_data,
        training_params={"contamination": 0.05, "n_estimators": 100},
        training_metrics={"accuracy": 0.95, "n_anomalies_detected": 5, "anomaly_percentage": 5.0},
        feature_names=["volume", "failure_rate", "unique_domains"],
        training_samples=1000,
        training_date_start=datetime.utcnow() - timedelta(days=90),
        training_date_end=datetime.utcnow(),
        is_active=True,
        is_deployed=True,
        trained_by=admin_user.id,
    )
    db_session.add(model)
    db_session.commit()
    db_session.refresh(model)
    return model


@pytest.fixture
def sample_prediction(db_session, sample_ml_model):
    """Create a sample ML prediction."""
    prediction = MLPrediction(
        id=uuid.uuid4(),
        model_id=sample_ml_model.id,
        model_type="isolation_forest",
        target_type="ip_address",
        target_value="192.168.1.100",
        prediction_type="anomaly",
        prediction_value=-0.65,
        prediction_label="anomaly",
        confidence_score=0.87,
        features={"volume": 500, "failure_rate": 45.2, "unique_domains": 3},
        predicted_at=datetime.utcnow(),
    )
    db_session.add(prediction)
    db_session.commit()
    db_session.refresh(prediction)
    return prediction


# ==================== Geolocation Endpoints ====================


@pytest.mark.integration
class TestGetCountryHeatmap:
    """Test GET /api/analytics/geolocation/map"""

    @patch("app.api.analytics_routes.GeoLocationService")
    def test_get_heatmap_empty(self, mock_geo_cls, client, admin_token, admin_user):
        """Get heatmap returns empty data when no IPs exist."""
        response = client.get(
            "/api/analytics/geolocation/map",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert data["total_ips"] == 0

    @patch("app.api.analytics_routes.GeoLocationService")
    def test_get_heatmap_with_days_param(self, mock_geo_cls, client, admin_token, admin_user):
        """Get heatmap accepts days query parameter."""
        response = client.get(
            "/api/analytics/geolocation/map?days=7",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200

    def test_get_heatmap_invalid_days(self, client, admin_token, admin_user):
        """Invalid days parameter returns 422."""
        response = client.get(
            "/api/analytics/geolocation/map?days=0",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422

    def test_get_heatmap_unauthenticated(self, client):
        """Unauthenticated request returns 401."""
        response = client.get("/api/analytics/geolocation/map")
        assert response.status_code in (401, 403)


@pytest.mark.integration
class TestLookupIPGeolocation:
    """Test GET /api/analytics/geolocation/lookup/{ip_address}"""

    @patch("app.api.analytics_routes.GeoLocationService")
    def test_lookup_ip_not_found(self, mock_geo_cls, client, admin_token, admin_user):
        """IP not found in geo database returns 404."""
        mock_service = MagicMock()
        mock_service.lookup_ip.return_value = None
        mock_geo_cls.return_value = mock_service

        response = client.get(
            "/api/analytics/geolocation/lookup/192.168.1.1",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    @patch("app.api.analytics_routes.GeoLocationService")
    def test_lookup_ip_found(self, mock_geo_cls, client, admin_token, admin_user):
        """Successful IP lookup returns geolocation data."""
        mock_service = MagicMock()
        mock_service.lookup_ip.return_value = {
            "ip_address": "8.8.8.8",
            "country_code": "US",
            "country_name": "United States",
            "city_name": "Mountain View",
            "latitude": 37.386,
            "longitude": -122.0838,
            "timezone": "America/Los_Angeles",
        }
        mock_geo_cls.return_value = mock_service

        response = client.get(
            "/api/analytics/geolocation/lookup/8.8.8.8",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ip_address"] == "8.8.8.8"
        assert data["country_code"] == "US"

    def test_lookup_ip_viewer_can_access(self, client, viewer_token, viewer_user):
        """Viewer users can access geolocation lookup."""
        with patch("app.api.analytics_routes.GeoLocationService") as mock_geo_cls:
            mock_service = MagicMock()
            mock_service.lookup_ip.return_value = {
                "ip_address": "1.1.1.1",
                "country_code": "AU",
            }
            mock_geo_cls.return_value = mock_service

            response = client.get(
                "/api/analytics/geolocation/lookup/1.1.1.1",
                headers=auth_header(viewer_token),
            )
            assert response.status_code == 200


@pytest.mark.integration
class TestBulkLookup:
    """Test POST /api/analytics/geolocation/lookup-bulk"""

    @patch("app.api.analytics_routes.GeoLocationService")
    def test_bulk_lookup(self, mock_geo_cls, client, admin_token, admin_user):
        """Bulk lookup returns results for multiple IPs."""
        mock_service = MagicMock()
        mock_service.lookup_ips_bulk.return_value = {
            "8.8.8.8": {"ip_address": "8.8.8.8", "country_code": "US"},
            "1.1.1.1": {"ip_address": "1.1.1.1", "country_code": "AU"},
        }
        mock_geo_cls.return_value = mock_service

        response = client.post(
            "/api/analytics/geolocation/lookup-bulk",
            json={"ip_addresses": ["8.8.8.8", "1.1.1.1"], "use_cache": True},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_bulk_lookup_unauthenticated(self, client):
        """Unauthenticated bulk lookup returns 401."""
        response = client.post(
            "/api/analytics/geolocation/lookup-bulk",
            json={"ip_addresses": ["8.8.8.8"]},
        )
        assert response.status_code in (401, 403)


@pytest.mark.integration
class TestCacheStats:
    """Test GET /api/analytics/geolocation/cache-stats"""

    @patch("app.api.analytics_routes.GeoLocationService")
    def test_get_cache_stats(self, mock_geo_cls, client, admin_token, admin_user):
        """Get cache statistics."""
        mock_service = MagicMock()
        mock_service.get_cache_stats.return_value = {
            "total_entries": 150,
            "expired_entries": 10,
            "active_entries": 140,
            "database_loaded": True,
            "database_path": "/opt/GeoLite2-City.mmdb",
        }
        mock_geo_cls.return_value = mock_service

        response = client.get(
            "/api/analytics/geolocation/cache-stats",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_entries"] == 150
        assert data["database_loaded"] is True


# ==================== ML Model Endpoints ====================


@pytest.mark.integration
class TestListMLModels:
    """Test GET /api/analytics/ml/models"""

    @patch("app.api.analytics_routes.MLAnalyticsService")
    def test_list_models_empty(self, mock_ml_cls, client, admin_token, admin_user):
        """List models returns empty list when none exist."""
        mock_service = MagicMock()
        mock_service.list_models.return_value = []
        mock_ml_cls.return_value = mock_service

        response = client.get(
            "/api/analytics/ml/models",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @patch("app.api.analytics_routes.MLAnalyticsService")
    def test_list_models_with_type_filter(self, mock_ml_cls, client, admin_token, admin_user):
        """List models accepts model_type filter."""
        mock_service = MagicMock()
        mock_service.list_models.return_value = []
        mock_ml_cls.return_value = mock_service

        response = client.get(
            "/api/analytics/ml/models?model_type=isolation_forest&active_only=true",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        mock_service.list_models.assert_called_once_with(
            model_type="isolation_forest", active_only=True
        )


@pytest.mark.integration
class TestGetMLModelDetail:
    """Test GET /api/analytics/ml/models/{model_id}"""

    def test_get_model_detail(self, client, admin_token, admin_user, sample_ml_model):
        """Get model details for existing model."""
        response = client.get(
            f"/api/analytics/ml/models/{sample_ml_model.id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "test_anomaly_model_v1"
        assert data["model_type"] == "isolation_forest"
        assert data["is_deployed"] is True

    def test_get_model_detail_not_found(self, client, admin_token, admin_user):
        """Get model details for non-existent model returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/api/analytics/ml/models/{fake_id}",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 404

    def test_get_model_detail_invalid_uuid(self, client, admin_token, admin_user):
        """Invalid model UUID returns 422."""
        response = client.get(
            "/api/analytics/ml/models/not-a-uuid",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422


# ==================== Train Model ====================


@pytest.mark.integration
class TestTrainModel:
    """Test POST /api/analytics/ml/train"""

    def test_train_model_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot train models."""
        response = client.post(
            "/api/analytics/ml/train",
            json={"days": 90, "contamination": 0.05},
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403

    @patch("app.api.analytics_routes.MLAnalyticsService")
    def test_train_model_admin(self, mock_ml_cls, client, admin_token, admin_user):
        """Admin can train a model."""
        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        mock_model.model_name = "anomaly_v1"
        mock_model.training_samples = 500

        mock_service = MagicMock()
        mock_service.train_anomaly_model.return_value = (
            mock_model,
            {"n_anomalies_detected": 25, "anomaly_percentage": 5.0},
        )
        mock_service.get_deployed_model.return_value = None
        mock_ml_cls.return_value = mock_service

        response = client.post(
            "/api/analytics/ml/train",
            json={"days": 90, "contamination": 0.05},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["training_samples"] == 500

    def test_train_model_invalid_params(self, client, admin_token, admin_user):
        """Invalid training params return 422."""
        response = client.post(
            "/api/analytics/ml/train",
            json={"days": 5, "contamination": 0.05},  # days < 30
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422


# ==================== Deploy Model ====================


@pytest.mark.integration
class TestDeployModel:
    """Test POST /api/analytics/ml/deploy"""

    def test_deploy_model_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot deploy models."""
        response = client.post(
            "/api/analytics/ml/deploy",
            json={"model_id": str(uuid.uuid4())},
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403

    @patch("app.api.analytics_routes.MLAnalyticsService")
    def test_deploy_model_admin(self, mock_ml_cls, client, admin_token, admin_user):
        """Admin can deploy a model."""
        model_id = uuid.uuid4()
        mock_model = MagicMock()
        mock_model.id = model_id
        mock_model.model_name = "anomaly_v2"

        mock_service = MagicMock()
        mock_service.deploy_model.return_value = mock_model
        mock_ml_cls.return_value = mock_service

        response = client.post(
            "/api/analytics/ml/deploy",
            json={"model_id": str(model_id)},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


# ==================== Anomaly Detection ====================


@pytest.mark.integration
class TestDetectAnomalies:
    """Test POST /api/analytics/anomalies/detect"""

    @patch("app.api.analytics_routes.MLAnalyticsService")
    def test_detect_anomalies(self, mock_ml_cls, client, admin_token, admin_user):
        """Detect anomalies returns results."""
        mock_service = MagicMock()
        mock_service.detect_anomalies.return_value = []
        mock_deployed = MagicMock()
        mock_deployed.id = uuid.uuid4()
        mock_deployed.model_name = "anomaly_v1"
        mock_service.get_deployed_model.return_value = mock_deployed
        mock_ml_cls.return_value = mock_service

        response = client.post(
            "/api/analytics/anomalies/detect",
            json={"days": 7, "threshold": -0.5},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["anomalies_detected"] == 0

    def test_detect_anomalies_unauthenticated(self, client):
        """Unauthenticated anomaly detection returns 401."""
        response = client.post(
            "/api/analytics/anomalies/detect",
            json={"days": 7, "threshold": -0.5},
        )
        assert response.status_code in (401, 403)


@pytest.mark.integration
class TestDetectAnomaliesWithAlerts:
    """Test POST /api/analytics/anomalies/detect-with-alerts"""

    def test_viewer_forbidden(self, client, viewer_token, viewer_user):
        """Viewer cannot detect anomalies with alerts."""
        response = client.post(
            "/api/analytics/anomalies/detect-with-alerts",
            json={"days": 7, "threshold": -0.5},
            headers=auth_header(viewer_token),
        )
        assert response.status_code == 403

    def test_admin_forbidden(self, client, admin_token, admin_user):
        """Admin is forbidden (only analyst role allowed for this endpoint)."""
        response = client.post(
            "/api/analytics/anomalies/detect-with-alerts",
            json={"days": 7, "threshold": -0.5},
            headers=auth_header(admin_token),
        )
        assert response.status_code == 403


# ==================== Recent Anomalies ====================


@pytest.mark.integration
class TestGetRecentAnomalies:
    """Test GET /api/analytics/anomalies/recent"""

    def test_get_recent_anomalies_empty(self, client, admin_token, admin_user):
        """Get recent anomalies returns empty list when none exist."""
        response = client.get(
            "/api/analytics/anomalies/recent",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_recent_anomalies_with_data(
        self, client, admin_token, admin_user, sample_prediction
    ):
        """Get recent anomalies returns predictions."""
        response = client.get(
            "/api/analytics/anomalies/recent?days=30",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["prediction_type"] == "anomaly"
        assert data[0]["target_value"] == "192.168.1.100"

    def test_get_recent_anomalies_with_limit(self, client, admin_token, admin_user):
        """Limit parameter is accepted."""
        response = client.get(
            "/api/analytics/anomalies/recent?days=7&limit=50",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200

    def test_get_recent_anomalies_invalid_days(self, client, admin_token, admin_user):
        """Invalid days parameter returns 422."""
        response = client.get(
            "/api/analytics/anomalies/recent?days=0",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422


# ==================== Forecast Endpoints ====================


@pytest.mark.integration
class TestForecastVolume:
    """Test GET /api/analytics/forecast/volume"""

    @patch("app.services.forecasting.ForecastingService")
    def test_forecast_volume(self, mock_forecast_cls, client, admin_token, admin_user):
        """Forecast volume endpoint is accessible."""
        mock_service = MagicMock()
        mock_service.get_anomaly_forecast.return_value = {
            "forecasts": [],
            "trend": "stable",
        }
        mock_forecast_cls.return_value = mock_service

        response = client.get(
            "/api/analytics/forecast/volume?forecast_days=14&history_days=90",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200

    def test_forecast_volume_invalid_params(self, client, admin_token, admin_user):
        """Invalid forecast parameters return 422."""
        response = client.get(
            "/api/analytics/forecast/volume?forecast_days=0",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 422

    def test_forecast_volume_unauthenticated(self, client):
        """Unauthenticated forecast request returns 401."""
        response = client.get("/api/analytics/forecast/volume")
        assert response.status_code in (401, 403)


@pytest.mark.integration
class TestForecastSummary:
    """Test GET /api/analytics/forecast/summary"""

    @patch("app.services.forecasting.ForecastingService")
    def test_forecast_summary_no_data(self, mock_forecast_cls, client, admin_token, admin_user):
        """Forecast summary handles ValueError gracefully."""
        mock_service = MagicMock()
        mock_service.forecast_volume.side_effect = ValueError("Not enough data")
        mock_forecast_cls.return_value = mock_service

        response = client.get(
            "/api/analytics/forecast/summary",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["predictions"] == []
        assert "error" in data["summary"]
