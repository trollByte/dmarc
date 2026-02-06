"""Unit tests for ForecastingService (forecasting.py)"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.services.forecasting import (
    ForecastingService, TrendDirection, ForecastPoint, ForecastResult,
)


@pytest.mark.unit
class TestHoltWintersPrediction:
    """Test Holt-Winters prediction output"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ForecastingService(mock_db)

    def test_holt_winters_fit_returns_correct_shapes(self, service):
        """Test that Holt-Winters fit returns arrays of correct size"""
        y = np.array([100, 110, 105, 115, 120, 108, 125, 130, 115, 140,
                       135, 120, 145, 150, 130, 155, 160, 140, 165, 170], dtype=float)

        level, trend, seasonal, fitted = service._holt_winters_fit(y)

        assert len(level) == len(y)
        assert len(trend) == len(y)
        assert len(seasonal) == len(y)
        assert len(fitted) == len(y)

    def test_holt_winters_fit_without_seasonality(self, service):
        """Test Holt-Winters with gamma=0 (no seasonality)"""
        y = np.array([10, 12, 14, 16, 18, 20, 22, 24, 26, 28], dtype=float)

        level, trend, seasonal, fitted = service._holt_winters_fit(
            y, alpha=0.3, beta=0.1, gamma=0
        )

        # Seasonal component should all be zeros
        assert np.all(seasonal == 0)

        # Fitted values should follow the trend
        assert len(fitted) == len(y)

    def test_forecast_volume_returns_forecast_result(self, service, mock_db):
        """Test forecast_volume returns a ForecastResult"""
        # Mock daily volume data - 30 days
        dates = pd.date_range(start="2024-01-01", periods=30, freq="D")
        volumes = np.random.randint(50, 200, size=30)

        df = pd.DataFrame({"date": dates, "volume": volumes})

        with patch.object(service, "get_daily_volume", return_value=df):
            result = service.forecast_volume(forecast_days=7, history_days=30)

        assert isinstance(result, ForecastResult)
        assert len(result.forecasts) == 7
        assert result.trend_direction in [TrendDirection.INCREASING, TrendDirection.DECREASING, TrendDirection.STABLE]
        assert 0 <= result.trend_strength <= 1

    def test_forecast_points_have_required_fields(self, service, mock_db):
        """Test each forecast point has all required fields"""
        dates = pd.date_range(start="2024-01-01", periods=30, freq="D")
        volumes = np.random.randint(50, 200, size=30)
        df = pd.DataFrame({"date": dates, "volume": volumes})

        with patch.object(service, "get_daily_volume", return_value=df):
            result = service.forecast_volume(forecast_days=3)

        for point in result.forecasts:
            assert isinstance(point, ForecastPoint)
            assert point.date is not None
            assert point.predicted_volume >= 0
            assert point.lower_bound >= 0
            assert point.upper_bound >= point.lower_bound
            assert isinstance(point.is_weekend, bool)

    def test_forecast_confidence_intervals_widen(self, service, mock_db):
        """Test that confidence intervals widen with forecast horizon"""
        dates = pd.date_range(start="2024-01-01", periods=60, freq="D")
        volumes = np.random.randint(100, 200, size=60)
        df = pd.DataFrame({"date": dates, "volume": volumes})

        with patch.object(service, "get_daily_volume", return_value=df):
            result = service.forecast_volume(forecast_days=14)

        # Width of interval should generally increase
        first_width = result.forecasts[0].upper_bound - result.forecasts[0].lower_bound
        last_width = result.forecasts[-1].upper_bound - result.forecasts[-1].lower_bound
        assert last_width >= first_width

    def test_predicted_volumes_are_non_negative(self, service, mock_db):
        """Test that all predicted volumes are non-negative"""
        dates = pd.date_range(start="2024-01-01", periods=30, freq="D")
        volumes = np.random.randint(1, 10, size=30)  # Low volumes
        df = pd.DataFrame({"date": dates, "volume": volumes})

        with patch.object(service, "get_daily_volume", return_value=df):
            result = service.forecast_volume(forecast_days=14)

        for point in result.forecasts:
            assert point.predicted_volume >= 0
            assert point.lower_bound >= 0


@pytest.mark.unit
class TestMinimumDataRequirement:
    """Test minimum data requirement enforcement"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        return ForecastingService(mock_db)

    def test_insufficient_data_raises(self, service, mock_db):
        """Test forecast with <14 days of data raises ValueError"""
        dates = pd.date_range(start="2024-01-01", periods=10, freq="D")
        volumes = np.random.randint(50, 200, size=10)
        df = pd.DataFrame({"date": dates, "volume": volumes})

        with patch.object(service, "get_daily_volume", return_value=df):
            with pytest.raises(ValueError, match="Insufficient historical data"):
                service.forecast_volume(forecast_days=7)

    def test_empty_data_raises(self, service, mock_db):
        """Test forecast with empty data raises ValueError"""
        df = pd.DataFrame(columns=["date", "volume"])

        with patch.object(service, "get_daily_volume", return_value=df):
            with pytest.raises(ValueError, match="Insufficient historical data"):
                service.forecast_volume(forecast_days=7)

    def test_exactly_14_days_succeeds(self, service, mock_db):
        """Test forecast with exactly 14 days succeeds"""
        dates = pd.date_range(start="2024-01-01", periods=14, freq="D")
        volumes = np.random.randint(50, 200, size=14)
        df = pd.DataFrame({"date": dates, "volume": volumes})

        with patch.object(service, "get_daily_volume", return_value=df):
            result = service.forecast_volume(forecast_days=7)

        assert len(result.forecasts) == 7

    def test_13_days_raises(self, service, mock_db):
        """Test forecast with 13 days raises ValueError"""
        dates = pd.date_range(start="2024-01-01", periods=13, freq="D")
        volumes = np.random.randint(50, 200, size=13)
        df = pd.DataFrame({"date": dates, "volume": volumes})

        with patch.object(service, "get_daily_volume", return_value=df):
            with pytest.raises(ValueError, match="Insufficient historical data"):
                service.forecast_volume(forecast_days=7)


@pytest.mark.unit
class TestTrendDetection:
    """Test trend direction and strength calculation"""

    @pytest.fixture
    def service(self):
        return ForecastingService(MagicMock())

    def test_increasing_trend(self, service):
        """Test detection of increasing trend"""
        y = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], dtype=float)
        direction, strength = service._calculate_trend(y)

        assert direction == TrendDirection.INCREASING
        assert strength > 0.5  # Should be a strong trend

    def test_decreasing_trend(self, service):
        """Test detection of decreasing trend"""
        y = np.array([100, 90, 80, 70, 60, 50, 40, 30, 20, 10], dtype=float)
        direction, strength = service._calculate_trend(y)

        assert direction == TrendDirection.DECREASING
        assert strength > 0.5

    def test_stable_trend(self, service):
        """Test detection of stable trend"""
        y = np.array([100, 101, 99, 100, 101, 100, 99, 100, 101, 99], dtype=float)
        direction, strength = service._calculate_trend(y)

        assert direction == TrendDirection.STABLE

    def test_short_data_returns_stable(self, service):
        """Test that data shorter than 7 points returns STABLE"""
        y = np.array([10, 20, 30], dtype=float)
        direction, strength = service._calculate_trend(y)

        assert direction == TrendDirection.STABLE
        assert strength == 0.0


@pytest.mark.unit
class TestSeasonalityDetection:
    """Test weekly seasonality detection"""

    @pytest.fixture
    def service(self):
        return ForecastingService(MagicMock())

    def test_significant_seasonality_detected(self, service):
        """Test that significant weekly variation is detected"""
        pattern = {
            "Monday": 100, "Tuesday": 120, "Wednesday": 130,
            "Thursday": 125, "Friday": 110, "Saturday": 40, "Sunday": 30,
        }
        assert service._has_significant_seasonality(pattern) is True

    def test_no_seasonality_detected(self, service):
        """Test that uniform pattern shows no seasonality"""
        pattern = {
            "Monday": 100, "Tuesday": 100, "Wednesday": 100,
            "Thursday": 100, "Friday": 100, "Saturday": 100, "Sunday": 100,
        }
        assert service._has_significant_seasonality(pattern) is False

    def test_all_zeros_no_seasonality(self, service):
        """Test that all-zero pattern shows no seasonality"""
        pattern = {
            "Monday": 0, "Tuesday": 0, "Wednesday": 0,
            "Thursday": 0, "Friday": 0, "Saturday": 0, "Sunday": 0,
        }
        assert service._has_significant_seasonality(pattern) is False


@pytest.mark.unit
class TestMAPECalculation:
    """Test model accuracy metric calculation"""

    @pytest.fixture
    def service(self):
        return ForecastingService(MagicMock())

    def test_perfect_prediction(self, service):
        """Test MAPE is 0 for perfect prediction"""
        actual = np.array([100, 200, 300], dtype=float)
        predicted = np.array([100, 200, 300], dtype=float)
        assert service._calculate_mape(actual, predicted) == 0.0

    def test_imperfect_prediction(self, service):
        """Test MAPE is positive for imperfect prediction"""
        actual = np.array([100, 200, 300], dtype=float)
        predicted = np.array([110, 190, 280], dtype=float)
        mape = service._calculate_mape(actual, predicted)
        assert mape > 0
        assert mape < 100

    def test_mape_capped_at_100(self, service):
        """Test MAPE is capped at 100%"""
        actual = np.array([1, 1, 1], dtype=float)
        predicted = np.array([1000, 1000, 1000], dtype=float)
        mape = service._calculate_mape(actual, predicted)
        assert mape == 100

    def test_mape_ignores_zero_actuals(self, service):
        """Test MAPE ignores data points where actual is 0"""
        actual = np.array([0, 100, 200], dtype=float)
        predicted = np.array([50, 100, 200], dtype=float)
        mape = service._calculate_mape(actual, predicted)
        assert mape == 0.0  # Only non-zero actuals (100, 200) are perfect
