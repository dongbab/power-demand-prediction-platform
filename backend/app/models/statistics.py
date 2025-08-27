"""Statistical prediction model"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from calendar import monthrange

from .base import BaseModel
from .entities import PredictionResult, ContractRecommendation
from .validators import ChargingDataValidator


class StatisticalPredictor(BaseModel):
    """Statistical-based power prediction model"""

    def __init__(self, station_id: str):
        super().__init__(station_id)
        self.validator = ChargingDataValidator()
        self._hourly_profiles: Optional[Dict] = None
        self._seasonal_factors: Optional[Dict[int, float]] = None
        self._training_data: Optional[pd.DataFrame] = None

    def train(self, data: pd.DataFrame) -> None:
        """Train the statistical model"""
        if not self.validate_data(data):
            raise ValueError("Invalid training data format")

        # Clean and validate data
        clean_data = self.validator.clean_data(data)
        if clean_data.empty:
            raise ValueError("No valid data after cleaning")

        self._training_data = clean_data
        self._build_hourly_profiles(clean_data)
        self._calculate_seasonal_factors(clean_data)
        self._is_trained = True

        # Update metadata
        self.metadata.last_trained = datetime.now()
        self.metadata.training_data_size = len(clean_data)

    def predict_hourly_peak(self, hours_ahead: int = 24) -> PredictionResult:
        """Predict peak power for next hour"""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")

        current_time = datetime.now()
        target_time = current_time + timedelta(hours=1)
        target_time = target_time.replace(minute=0, second=0, microsecond=0)

        # Get base prediction from hourly profiles
        hour = target_time.hour
        weekday = target_time.weekday()
        month = target_time.month

        base_power = self._get_hourly_base_power(hour, weekday)
        seasonal_factor = self._seasonal_factors.get(month, 1.0)
        weekend_factor = 0.85 if weekday >= 5 else 1.0

        predicted_power = base_power * seasonal_factor * weekend_factor

        # Calculate confidence based on data availability
        confidence = self._calculate_confidence(hour, weekday)

        # Calculate confidence interval
        std_dev = self._get_prediction_std(hour, weekday)
        confidence_interval = {
            "lower": max(0, predicted_power - 1.96 * std_dev),
            "upper": predicted_power + 1.96 * std_dev,
        }

        return PredictionResult(
            station_id=self.station_id,
            predicted_peak=predicted_power,
            prediction_time=current_time,
            target_time=target_time,
            confidence=confidence,
            confidence_interval=confidence_interval,
            method="statistical_p95",
            factors={
                "base_power": base_power,
                "seasonal_factor": seasonal_factor,
                "weekend_factor": weekend_factor,
                "hour": hour,
                "is_weekend": weekday >= 5,
            },
        )

    def predict_monthly_peak(self, year: int, month: int) -> ContractRecommendation:
        """Predict monthly peak and recommend contract power"""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")

        # Calculate number of days in the month
        days_in_month = monthrange(year, month)[1]

        # Generate hourly predictions for the entire month
        monthly_predictions = []
        seasonal_factor = self._seasonal_factors.get(month, 1.0)

        for day in range(1, days_in_month + 1):
            for hour in range(24):
                date = datetime(year, month, day, hour)
                weekday = date.weekday()

                base_power = self._get_hourly_base_power(hour, weekday)
                weekend_factor = 0.85 if weekday >= 5 else 1.0

                predicted_power = base_power * seasonal_factor * weekend_factor
                monthly_predictions.append(predicted_power)

        # Calculate monthly peak (95th percentile for safety)
        predicted_peak = np.percentile(monthly_predictions, 95)

        # Apply safety margin and round to nearest 5kW
        safety_margin = 1.1
        recommended_contract = int(np.ceil(predicted_peak * safety_margin / 5) * 5)

        # Calculate confidence interval
        confidence_lower = predicted_peak * 0.85
        confidence_upper = predicted_peak * 1.15

        reasoning = self._generate_contract_reasoning(predicted_peak, recommended_contract, seasonal_factor, month)

        return ContractRecommendation(
            station_id=self.station_id,
            year=year,
            month=month,
            predicted_peak=predicted_peak,
            recommended_contract=recommended_contract,
            confidence_interval={"lower": confidence_lower, "upper": confidence_upper},
            seasonal_factor=seasonal_factor,
            safety_margin=safety_margin,
            method="statistical_monthly",
            reasoning=reasoning,
        )

    def forecast_peak(self, days: int = 1, agg: str = "hourly", mode: str = "p95") -> pd.DataFrame:
        """Forecast peak power for given number of days"""
        if not self.is_trained:
            # Try to train with available data
            from ..data.loader import ChargingDataLoader

            try:
                loader = ChargingDataLoader(self.station_id)
                training_data = loader.load_historical_sessions(days=90)
                if not training_data.empty:
                    self.train(training_data)
                else:
                    return pd.DataFrame()
            except Exception:
                return pd.DataFrame()

        current_time = datetime.now()
        predictions = []

        for day in range(days):
            for hour in range(24):
                target_time = current_time + timedelta(days=day, hours=hour)
                target_time = target_time.replace(minute=0, second=0, microsecond=0)

                hour_of_day = target_time.hour
                weekday = target_time.weekday()
                month = target_time.month

                base_power = self._get_hourly_base_power(hour_of_day, weekday)
                seasonal_factor = self._seasonal_factors.get(month, 1.0) if self._seasonal_factors else 1.0
                weekend_factor = 0.85 if weekday >= 5 else 1.0

                if mode == "p95":
                    predicted_power = base_power * seasonal_factor * weekend_factor
                else:  # mean
                    # For mean mode, use mean instead of p95
                    if self._hourly_profiles:
                        profile = self._hourly_profiles.get(hour_of_day, {}).get(weekday, {})
                        base_power = profile.get("mean", base_power)
                    predicted_power = base_power * seasonal_factor * weekend_factor

                predictions.append(
                    {
                        "start_dt": target_time,
                        "yhat": predicted_power,
                        "hour": hour_of_day,
                        "weekday": weekday,
                        "seasonal_factor": seasonal_factor,
                    }
                )

        return pd.DataFrame(predictions)

    def _build_hourly_profiles(self, data: pd.DataFrame) -> None:
        """Build hourly power profiles from training data"""
        data = data.copy()
        data["hour"] = data["충전시작일시"].dt.hour
        data["weekday"] = data["충전시작일시"].dt.weekday

        # Group by hour and weekday to get average power patterns
        profiles = {}

        for hour in range(24):
            profiles[hour] = {}
            for weekday in range(7):
                subset = data[(data["hour"] == hour) & (data["weekday"] == weekday)]

                if not subset.empty:
                    profiles[hour][weekday] = {
                        "mean": subset["순간최고전력"].mean(),
                        "std": subset["순간최고전력"].std(),
                        "count": len(subset),
                        "p95": subset["순간최고전력"].quantile(0.95),
                    }
                else:
                    # Use overall average as fallback
                    overall_mean = data["순간최고전력"].mean()
                    profiles[hour][weekday] = {
                        "mean": overall_mean,
                        "std": data["순간최고전력"].std(),
                        "count": 0,
                        "p95": data["순간최고전력"].quantile(0.95),
                    }

        self._hourly_profiles = profiles

    def _calculate_seasonal_factors(self, data: pd.DataFrame) -> None:
        """Calculate seasonal adjustment factors"""
        data = data.copy()
        data["month"] = data["충전시작일시"].dt.month

        monthly_averages = data.groupby("month")["순간최고전력"].mean()
        overall_average = data["순간최고전력"].mean()

        seasonal_factors = {}
        for month in range(1, 13):
            if month in monthly_averages.index:
                factor = monthly_averages[month] / overall_average
            else:
                # Default seasonal factors based on EV charging patterns
                seasonal_defaults = {
                    12: 1.15,
                    1: 1.15,
                    2: 1.10,  # Winter: higher due to battery efficiency
                    3: 1.0,
                    4: 1.0,
                    5: 1.0,  # Spring: baseline
                    6: 1.05,
                    7: 1.10,
                    8: 1.05,  # Summer: slightly higher due to AC usage
                    9: 1.0,
                    10: 1.0,
                    11: 1.05,  # Fall: baseline to slightly higher
                }
                factor = seasonal_defaults.get(month, 1.0)

            seasonal_factors[month] = factor

        self._seasonal_factors = seasonal_factors

    def _get_hourly_base_power(self, hour: int, weekday: int) -> float:
        """Get base power prediction for given hour and weekday"""
        if not self._hourly_profiles:
            return 33.5  # Default fallback

        profile = self._hourly_profiles.get(hour, {}).get(weekday, {})

        # Use p95 for conservative prediction, fallback to mean
        return profile.get("p95", profile.get("mean", 33.5))

    def _get_prediction_std(self, hour: int, weekday: int) -> float:
        """Get standard deviation for confidence interval calculation"""
        if not self._hourly_profiles:
            return 10.0  # Default fallback

        profile = self._hourly_profiles.get(hour, {}).get(weekday, {})
        return profile.get("std", 10.0)

    def _calculate_confidence(self, hour: int, weekday: int) -> float:
        """Calculate prediction confidence based on data availability"""
        if not self._hourly_profiles:
            return 0.7

        profile = self._hourly_profiles.get(hour, {}).get(weekday, {})
        count = profile.get("count", 0)

        # Confidence based on sample size
        if count >= 100:
            return 0.9
        elif count >= 30:
            return 0.8
        elif count >= 10:
            return 0.7
        else:
            return 0.6

    def _generate_contract_reasoning(
        self, predicted_peak: float, recommended_contract: int, seasonal_factor: float, month: int
    ) -> str:
        """Generate reasoning for contract recommendation"""
        reasons = []

        # Historical data analysis
        if self._training_data is not None:
            historical_max = self._training_data["순간최고전력"].max()
            if predicted_peak <= historical_max * 1.1:
                reasons.append("과거 최대값 기준 안정적 예측")

        # Seasonal adjustment
        if seasonal_factor > 1.05:
            season_name = {12: "겨울", 1: "겨울", 2: "겨울", 6: "여름", 7: "여름", 8: "여름"}.get(month, "계절성")
            reasons.append(f"{season_name} 계절 특성 반영")

        # Safety margin
        margin_percent = (recommended_contract - predicted_peak) / predicted_peak * 100
        reasons.append(f"{margin_percent:.0f}% 안전마진 적용")

        return " | ".join(reasons) if reasons else "통계 기반 보수적 추정"
