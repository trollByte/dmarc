"""Unit tests for Prometheus metrics module (app/metrics.py)"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from prometheus_client import REGISTRY, CollectorRegistry

from app.metrics import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUESTS_IN_PROGRESS,
    DMARC_REPORTS_PROCESSED,
    DMARC_RECORDS_INGESTED,
    ALERTS_TRIGGERED,
    ALERTS_ACTIVE,
    APP_INFO,
    metrics_middleware,
    record_report_processed,
    record_records_ingested,
    record_alert_triggered,
    update_active_alerts,
    record_celery_task,
    record_ml_prediction,
    CELERY_TASKS_TOTAL,
    CELERY_TASK_DURATION,
    ML_PREDICTIONS_TOTAL,
)


@pytest.mark.unit
class TestCounterIncrements:
    """Test that counters increment correctly with labels"""

    def test_http_requests_total_increments(self):
        """Counter increments for a specific label combination"""
        labels = {"method": "GET", "endpoint": "/api/test-inc", "status_code": "200"}
        before = HTTP_REQUESTS_TOTAL.labels(**labels)._value.get()
        HTTP_REQUESTS_TOTAL.labels(**labels).inc()
        after = HTTP_REQUESTS_TOTAL.labels(**labels)._value.get()
        assert after == before + 1

    def test_dmarc_reports_processed_increments(self):
        """Business counter increments via helper function"""
        before = DMARC_REPORTS_PROCESSED.labels(status="success")._value.get()
        record_report_processed("success")
        after = DMARC_REPORTS_PROCESSED.labels(status="success")._value.get()
        assert after == before + 1

    def test_dmarc_reports_processed_failed(self):
        """Failed status tracked independently from success"""
        before = DMARC_REPORTS_PROCESSED.labels(status="failed")._value.get()
        record_report_processed("failed")
        after = DMARC_REPORTS_PROCESSED.labels(status="failed")._value.get()
        assert after == before + 1

    def test_dmarc_records_ingested_increments_by_count(self):
        """Records ingested counter can increment by arbitrary count"""
        before = DMARC_RECORDS_INGESTED._value.get()
        record_records_ingested(42)
        after = DMARC_RECORDS_INGESTED._value.get()
        assert after == before + 42

    def test_alerts_triggered_increments(self):
        """Alert counter tracks type and severity labels"""
        labels = {"alert_type": "failure_rate", "severity": "critical"}
        before = ALERTS_TRIGGERED.labels(**labels)._value.get()
        record_alert_triggered("failure_rate", "critical")
        after = ALERTS_TRIGGERED.labels(**labels)._value.get()
        assert after == before + 1


@pytest.mark.unit
class TestHistogramBuckets:
    """Test histogram bucket boundaries"""

    def test_http_duration_bucket_boundaries(self):
        """HTTP histogram has the expected bucket thresholds"""
        expected = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf"))
        assert HTTP_REQUEST_DURATION._upper_bounds == expected

    def test_http_duration_records_observation(self):
        """Histogram observation updates sum"""
        labels = {"method": "POST", "endpoint": "/api/hist-test", "status_code": "201"}
        before_sum = HTTP_REQUEST_DURATION.labels(**labels)._sum.get()
        HTTP_REQUEST_DURATION.labels(**labels).observe(0.123)
        after_sum = HTTP_REQUEST_DURATION.labels(**labels)._sum.get()
        assert after_sum == pytest.approx(before_sum + 0.123)


@pytest.mark.unit
class TestGaugeValues:
    """Test gauge set / inc / dec behavior"""

    def test_in_progress_inc_and_dec(self):
        """Gauge increments and decrements for in-progress tracking"""
        labels = {"method": "GET", "endpoint": "/api/gauge-test"}
        HTTP_REQUESTS_IN_PROGRESS.labels(**labels).set(0)
        HTTP_REQUESTS_IN_PROGRESS.labels(**labels).inc()
        assert HTTP_REQUESTS_IN_PROGRESS.labels(**labels)._value.get() == 1
        HTTP_REQUESTS_IN_PROGRESS.labels(**labels).dec()
        assert HTTP_REQUESTS_IN_PROGRESS.labels(**labels)._value.get() == 0

    def test_active_alerts_gauge_set(self):
        """Active alerts gauge can be set to an absolute value"""
        update_active_alerts("critical", 5)
        assert ALERTS_ACTIVE.labels(severity="critical")._value.get() == 5
        update_active_alerts("critical", 3)
        assert ALERTS_ACTIVE.labels(severity="critical")._value.get() == 3


@pytest.mark.unit
class TestLabelCardinality:
    """Test that metrics carry the correct label names"""

    def test_http_requests_total_labels(self):
        """HTTP request counter has method, endpoint, status_code labels"""
        assert HTTP_REQUESTS_TOTAL._labelnames == ("method", "endpoint", "status_code")

    def test_http_duration_labels(self):
        """HTTP duration histogram has the same three labels"""
        assert HTTP_REQUEST_DURATION._labelnames == ("method", "endpoint", "status_code")

    def test_in_progress_labels(self):
        """In-progress gauge has method and endpoint only (no status yet)"""
        assert HTTP_REQUESTS_IN_PROGRESS._labelnames == ("method", "endpoint")

    def test_dmarc_reports_processed_labels(self):
        """Report counter carries a status label"""
        assert DMARC_REPORTS_PROCESSED._labelnames == ("status",)

    def test_alerts_triggered_labels(self):
        """Alert counter carries alert_type and severity labels"""
        assert ALERTS_TRIGGERED._labelnames == ("alert_type", "severity")

    def test_ml_predictions_labels(self):
        """ML predictions counter carries model_type and is_anomaly labels"""
        assert ML_PREDICTIONS_TOTAL._labelnames == ("model_type", "is_anomaly")


@pytest.mark.unit
class TestMetricsEndpoint:
    """Test the /metrics endpoint returns Prometheus text format"""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_prometheus_format(self):
        """Endpoint returns content-type for Prometheus scraping"""
        from app.metrics import metrics

        response = await metrics()
        assert response.media_type == "text/plain; version=0.0.4; charset=utf-8"
        body = response.body.decode("utf-8")
        # Check for standard Prometheus exposition elements
        assert "# HELP" in body
        assert "# TYPE" in body
        assert "http_requests_total" in body
        assert "dmarc_reports_processed_total" in body

    @pytest.mark.asyncio
    async def test_metrics_endpoint_contains_app_info(self):
        """App info metric is present in output"""
        from app.metrics import metrics

        response = await metrics()
        body = response.body.decode("utf-8")
        assert 'dmarc_dashboard_info' in body
        assert 'version="2.0.0"' in body


@pytest.mark.unit
class TestHelperFunctions:
    """Test business metric helper functions"""

    def test_record_celery_task_counter_only(self):
        """Celery helper increments counter without duration"""
        labels = {"task_name": "test_task", "status": "succeeded"}
        before = CELERY_TASKS_TOTAL.labels(**labels)._value.get()
        record_celery_task("test_task", "succeeded")
        after = CELERY_TASKS_TOTAL.labels(**labels)._value.get()
        assert after == before + 1

    def test_record_celery_task_with_duration(self):
        """Celery helper also records duration when provided"""
        before_sum = CELERY_TASK_DURATION.labels(task_name="timed_task")._sum.get()
        record_celery_task("timed_task", "succeeded", duration=1.5)
        after_sum = CELERY_TASK_DURATION.labels(task_name="timed_task")._sum.get()
        assert after_sum == pytest.approx(before_sum + 1.5)

    def test_record_ml_prediction(self):
        """ML prediction helper converts bool to lowercase string label"""
        before = ML_PREDICTIONS_TOTAL.labels(model_type="isolation_forest", is_anomaly="true")._value.get()
        record_ml_prediction("isolation_forest", True)
        after = ML_PREDICTIONS_TOTAL.labels(model_type="isolation_forest", is_anomaly="true")._value.get()
        assert after == before + 1


@pytest.mark.unit
class TestMetricsMiddleware:
    """Test the HTTP metrics middleware"""

    @pytest.mark.asyncio
    async def test_middleware_records_success(self):
        """Middleware records duration, counter, and in-progress gauge"""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/middleware-test"

        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_call_next(req):
            return mock_response

        before = HTTP_REQUESTS_TOTAL.labels(
            method="GET", endpoint="/api/middleware-test", status_code="200"
        )._value.get()

        await metrics_middleware(request, mock_call_next)

        after = HTTP_REQUESTS_TOTAL.labels(
            method="GET", endpoint="/api/middleware-test", status_code="200"
        )._value.get()
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_middleware_normalizes_numeric_ids(self):
        """Middleware replaces numeric path segments with {id}"""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/reports/12345"

        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_call_next(req):
            return mock_response

        before = HTTP_REQUESTS_TOTAL.labels(
            method="GET", endpoint="/api/reports/{id}", status_code="200"
        )._value.get()

        await metrics_middleware(request, mock_call_next)

        after = HTTP_REQUESTS_TOTAL.labels(
            method="GET", endpoint="/api/reports/{id}", status_code="200"
        )._value.get()
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_middleware_records_500_on_exception(self):
        """Middleware records status 500 when call_next raises"""
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/error-test"

        async def mock_call_next(req):
            raise RuntimeError("boom")

        before = HTTP_REQUESTS_TOTAL.labels(
            method="POST", endpoint="/api/error-test", status_code="500"
        )._value.get()

        with pytest.raises(RuntimeError, match="boom"):
            await metrics_middleware(request, mock_call_next)

        after = HTTP_REQUESTS_TOTAL.labels(
            method="POST", endpoint="/api/error-test", status_code="500"
        )._value.get()
        assert after == before + 1
