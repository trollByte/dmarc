"""
Time-series Forecasting Service.

Predicts future email volumes using:
- Exponential Smoothing (Holt-Winters)
- Moving Average baselines
- Seasonal pattern detection

No TensorFlow required - uses pandas and numpy.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Report, Record

logger = logging.getLogger(__name__)


class TrendDirection(str, Enum):
    """Trend direction classification"""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


@dataclass
class ForecastPoint:
    """Single forecast data point"""
    date: datetime
    predicted_volume: float
    lower_bound: float  # 95% confidence interval
    upper_bound: float
    is_weekend: bool


@dataclass
class ForecastResult:
    """Complete forecast result"""
    forecasts: List[ForecastPoint]
    trend_direction: TrendDirection
    trend_strength: float  # 0-1
    seasonality_detected: bool
    weekly_pattern: Dict[str, float]  # day -> avg volume
    model_accuracy: float  # MAPE on historical data
    historical_avg: float
    historical_std: float


class ForecastingService:
    """
    Time-series forecasting for email volume prediction.

    Uses Holt-Winters exponential smoothing with daily seasonality.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_daily_volume(self, days: int = 90) -> pd.DataFrame:
        """
        Get daily email volume time series.

        Args:
            days: Number of historical days

        Returns:
            DataFrame with date and volume columns
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Query daily volumes
        daily_data = self.db.query(
            func.date(Report.date_range_begin).label("date"),
            func.sum(Record.count).label("volume"),
        ).join(Record).filter(
            Report.date_range_begin >= since
        ).group_by(
            func.date(Report.date_range_begin)
        ).order_by(
            func.date(Report.date_range_begin)
        ).all()

        if not daily_data:
            return pd.DataFrame(columns=["date", "volume"])

        df = pd.DataFrame([
            {"date": row.date, "volume": row.volume or 0}
            for row in daily_data
        ])

        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").asfreq("D", fill_value=0).reset_index()

        return df

    def forecast_volume(
        self,
        forecast_days: int = 14,
        history_days: int = 90,
        confidence_level: float = 0.95
    ) -> ForecastResult:
        """
        Forecast future email volumes.

        Args:
            forecast_days: Number of days to forecast
            history_days: Days of historical data to use
            confidence_level: Confidence interval level (default 95%)

        Returns:
            ForecastResult with predictions and metadata
        """
        # Get historical data
        df = self.get_daily_volume(history_days)

        if len(df) < 14:
            raise ValueError(f"Insufficient historical data: {len(df)} days (minimum: 14)")

        volumes = df["volume"].values.astype(float)
        dates = df["date"].values

        # Detect seasonality (weekly pattern)
        weekly_pattern = self._detect_weekly_pattern(df)
        seasonality_detected = self._has_significant_seasonality(weekly_pattern)

        # Calculate trend
        trend_direction, trend_strength = self._calculate_trend(volumes)

        # Fit exponential smoothing model
        alpha = 0.3  # Level smoothing
        beta = 0.1   # Trend smoothing
        gamma = 0.2 if seasonality_detected else 0  # Seasonal smoothing

        # Triple exponential smoothing (Holt-Winters)
        level, trend, seasonal, fitted = self._holt_winters_fit(
            volumes,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            seasonal_periods=7
        )

        # Calculate model accuracy (MAPE)
        mape = self._calculate_mape(volumes, fitted)

        # Generate forecasts
        forecasts = []
        last_date = pd.Timestamp(dates[-1])
        residuals = volumes - fitted
        std_residual = np.std(residuals)

        z_score = 1.96 if confidence_level == 0.95 else 1.645  # 95% or 90%

        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)

            # Holt-Winters forecast
            h = i  # Forecast horizon
            forecast_level = level[-1]
            forecast_trend = trend[-1] * h

            # Seasonal component
            if seasonality_detected and len(seasonal) >= 7:
                seasonal_idx = (len(volumes) + i - 1) % 7
                seasonal_component = seasonal[-(7 - seasonal_idx)] if seasonal_idx < 7 else 0
            else:
                seasonal_component = 0

            predicted = max(0, forecast_level + forecast_trend + seasonal_component)

            # Confidence intervals (widen with horizon)
            horizon_factor = np.sqrt(h)
            margin = z_score * std_residual * horizon_factor

            forecasts.append(ForecastPoint(
                date=forecast_date.to_pydatetime(),
                predicted_volume=round(predicted),
                lower_bound=max(0, round(predicted - margin)),
                upper_bound=round(predicted + margin),
                is_weekend=forecast_date.weekday() >= 5
            ))

        return ForecastResult(
            forecasts=forecasts,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            seasonality_detected=seasonality_detected,
            weekly_pattern=weekly_pattern,
            model_accuracy=mape,
            historical_avg=float(np.mean(volumes)),
            historical_std=float(np.std(volumes)),
        )

    def _holt_winters_fit(
        self,
        y: np.ndarray,
        alpha: float = 0.3,
        beta: float = 0.1,
        gamma: float = 0.2,
        seasonal_periods: int = 7
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Fit Holt-Winters triple exponential smoothing.

        Returns level, trend, seasonal components and fitted values.
        """
        n = len(y)
        level = np.zeros(n)
        trend = np.zeros(n)
        seasonal = np.zeros(n)
        fitted = np.zeros(n)

        # Initialize
        level[0] = y[0]
        trend[0] = (y[min(seasonal_periods, n-1)] - y[0]) / seasonal_periods if n > seasonal_periods else 0

        # Initialize seasonal factors
        if gamma > 0 and n >= seasonal_periods:
            for i in range(seasonal_periods):
                seasonal[i] = y[i] - level[0]

        # Fit model
        for t in range(1, n):
            # Previous seasonal factor
            seasonal_idx = (t - seasonal_periods) % n if t >= seasonal_periods else t
            s_prev = seasonal[seasonal_idx] if gamma > 0 else 0

            # Update level
            level[t] = alpha * (y[t] - s_prev) + (1 - alpha) * (level[t-1] + trend[t-1])

            # Update trend
            trend[t] = beta * (level[t] - level[t-1]) + (1 - beta) * trend[t-1]

            # Update seasonal
            if gamma > 0:
                seasonal[t] = gamma * (y[t] - level[t]) + (1 - gamma) * s_prev

            # Fitted value
            fitted[t] = level[t-1] + trend[t-1] + (s_prev if gamma > 0 else 0)

        return level, trend, seasonal, fitted

    def _detect_weekly_pattern(self, df: pd.DataFrame) -> Dict[str, float]:
        """Detect weekly seasonality pattern"""
        df = df.copy()
        df["day_name"] = pd.to_datetime(df["date"]).dt.day_name()

        pattern = df.groupby("day_name")["volume"].mean().to_dict()

        # Ensure all days are present
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return {day: pattern.get(day, 0) for day in days}

    def _has_significant_seasonality(self, weekly_pattern: Dict[str, float]) -> bool:
        """Check if weekly pattern shows significant seasonality"""
        values = list(weekly_pattern.values())
        if not values or all(v == 0 for v in values):
            return False

        mean_val = np.mean(values)
        if mean_val == 0:
            return False

        # Coefficient of variation
        cv = np.std(values) / mean_val
        return cv > 0.1  # >10% variation indicates seasonality

    def _calculate_trend(self, y: np.ndarray) -> Tuple[TrendDirection, float]:
        """Calculate trend direction and strength"""
        if len(y) < 7:
            return TrendDirection.STABLE, 0.0

        # Linear regression slope
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)

        # Normalize slope by mean volume
        mean_vol = np.mean(y)
        if mean_vol == 0:
            return TrendDirection.STABLE, 0.0

        normalized_slope = slope / mean_vol

        # Determine direction and strength
        if normalized_slope > 0.01:  # >1% daily increase
            direction = TrendDirection.INCREASING
        elif normalized_slope < -0.01:  # >1% daily decrease
            direction = TrendDirection.DECREASING
        else:
            direction = TrendDirection.STABLE

        # Calculate R-squared as trend strength
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return direction, max(0, min(1, r_squared))

    def _calculate_mape(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """Calculate Mean Absolute Percentage Error"""
        mask = actual > 0
        if not mask.any():
            return 0.0

        mape = np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100
        return min(100, mape)  # Cap at 100%

    def get_anomaly_forecast(
        self,
        forecast_days: int = 7,
        history_days: int = 30
    ) -> Dict:
        """
        Forecast with anomaly probability.

        Returns volume forecast with probability of being anomalously high/low.
        """
        result = self.forecast_volume(forecast_days, history_days)

        # Calculate anomaly thresholds
        upper_threshold = result.historical_avg + 2 * result.historical_std
        lower_threshold = max(0, result.historical_avg - 2 * result.historical_std)

        forecasts_with_anomaly = []
        for f in result.forecasts:
            anomaly_prob = 0.0

            if f.predicted_volume > upper_threshold:
                # Probability increases with distance from threshold
                excess = (f.predicted_volume - upper_threshold) / result.historical_std
                anomaly_prob = min(1.0, 0.3 + 0.1 * excess)
            elif f.predicted_volume < lower_threshold:
                deficit = (lower_threshold - f.predicted_volume) / result.historical_std
                anomaly_prob = min(1.0, 0.3 + 0.1 * deficit)

            forecasts_with_anomaly.append({
                "date": f.date.isoformat(),
                "predicted_volume": f.predicted_volume,
                "lower_bound": f.lower_bound,
                "upper_bound": f.upper_bound,
                "is_weekend": f.is_weekend,
                "anomaly_probability": round(anomaly_prob, 2),
                "anomaly_risk": "high" if anomaly_prob > 0.5 else "medium" if anomaly_prob > 0.2 else "low"
            })

        return {
            "forecasts": forecasts_with_anomaly,
            "trend": {
                "direction": result.trend_direction.value,
                "strength": round(result.trend_strength, 2),
            },
            "seasonality": {
                "detected": result.seasonality_detected,
                "weekly_pattern": {k: round(v) for k, v in result.weekly_pattern.items()},
            },
            "model": {
                "accuracy_mape": round(result.model_accuracy, 1),
                "historical_avg": round(result.historical_avg),
                "historical_std": round(result.historical_std),
            },
            "thresholds": {
                "upper_anomaly": round(upper_threshold),
                "lower_anomaly": round(lower_threshold),
            }
        }

    def get_domain_forecast(
        self,
        domain: str,
        forecast_days: int = 14,
        history_days: int = 60
    ) -> Dict:
        """
        Forecast volume for a specific domain.
        """
        since = datetime.utcnow() - timedelta(days=history_days)

        # Query domain-specific data
        daily_data = self.db.query(
            func.date(Report.date_range_begin).label("date"),
            func.sum(Record.count).label("volume"),
        ).join(Record).filter(
            Report.date_range_begin >= since,
            Report.domain == domain
        ).group_by(
            func.date(Report.date_range_begin)
        ).order_by(
            func.date(Report.date_range_begin)
        ).all()

        if len(daily_data) < 7:
            return {
                "domain": domain,
                "error": "Insufficient data for forecast",
                "data_points": len(daily_data)
            }

        df = pd.DataFrame([
            {"date": row.date, "volume": row.volume or 0}
            for row in daily_data
        ])

        df["date"] = pd.to_datetime(df["date"])
        volumes = df["volume"].values.astype(float)

        # Simple exponential smoothing for domain-level
        alpha = 0.3
        level = np.zeros(len(volumes))
        level[0] = volumes[0]

        for t in range(1, len(volumes)):
            level[t] = alpha * volumes[t] + (1 - alpha) * level[t-1]

        # Forecast
        forecasts = []
        last_date = pd.Timestamp(df["date"].iloc[-1])
        std = np.std(volumes)

        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            predicted = max(0, level[-1])

            forecasts.append({
                "date": forecast_date.isoformat(),
                "predicted_volume": round(predicted),
                "lower_bound": max(0, round(predicted - 1.96 * std)),
                "upper_bound": round(predicted + 1.96 * std),
            })

        return {
            "domain": domain,
            "forecasts": forecasts,
            "historical_avg": round(np.mean(volumes)),
            "historical_std": round(std),
            "data_points": len(volumes),
        }
