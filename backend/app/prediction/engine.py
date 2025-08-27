from typing import Dict, Any, Optional, List
import pandas as pd
from datetime import datetime
import logging
import math

from ..models.statistics import StatisticalPredictor
from ..models.entities import PredictionResult, ContractRecommendation
from ..data.repository import ChargingDataRepository
from .stats_extreme import estimate_extremes_from_df


class PredictionEngine:
    """Core prediction engine that manages models and predictions"""

    def __init__(self, data_repository: ChargingDataRepository):
        self.data_repository = data_repository
        self.logger = logging.getLogger(__name__)
        self._models: Dict[str, StatisticalPredictor] = {}
        self._model_cache_time: Dict[str, datetime] = {}

    def get_or_create_model(self, station_id: str) -> StatisticalPredictor:
        """Get existing model or create and train new one"""
        current_time = datetime.now()

        # Check if model exists and is recent (within 24 hours)
        if (
            station_id in self._models
            and station_id in self._model_cache_time
            and (current_time - self._model_cache_time[station_id]).total_seconds() < 86400
        ):
            return self._models[station_id]

        # Create and train new model
        model = StatisticalPredictor(station_id)

        try:
            # Load training data
            training_data = self.data_repository.get_historical_sessions(
                station_id=station_id if station_id != "ALL" else None, days=90
            )

            if training_data.empty:
                raise ValueError(f"No training data available for station {station_id}")

            # Train the model
            model.train(training_data)

            # Cache the model
            self._models[station_id] = model
            self._model_cache_time[station_id] = current_time

            self.logger.info(f"Model trained for station {station_id} with {len(training_data)} records")

        except Exception as e:
            self.logger.error(f"Failed to train model for station {station_id}: {e}")
            raise

        return model

    def predict_next_hour_peak(self, station_id: str) -> PredictionResult:
        """Predict peak power for the next hour"""
        try:
            model = self.get_or_create_model(station_id)
            prediction = model.predict_hourly_peak()

            self.logger.info(f"Generated hourly prediction for station {station_id}: {prediction.predicted_peak}kW")
            return prediction

        except Exception as e:
            self.logger.error(f"Hourly prediction failed for station {station_id}: {e}")
            return self._fallback_hourly_prediction(station_id)

    def predict_monthly_contract(self, station_id: str, year: int, month: int) -> ContractRecommendation:
        """Predict monthly peak and recommend contract power"""
        try:
            model = self.get_or_create_model(station_id)
            recommendation = model.predict_monthly_peak(year, month)

            # EVT 기반 상향 보정 (최근 12~18개월 정도 권장)
            try:
                hist_df = self.data_repository.get_historical_sessions(
                    station_id=station_id if station_id != "ALL" else None, days=540  # 약 18개월
                )
            except Exception as _:
                hist_df = pd.DataFrame()

            extreme = estimate_extremes_from_df(hist_df, p_target=0.98, q_high=0.99)
            evt_rl = extreme.get("return_level")

            # 기존 추천 vs EVT 재현수준 중 더 보수적인 값 선택 + 안전마진
            safety_margin = getattr(recommendation, "safety_margin", 1.10)
            base_peak = max(
                float(getattr(recommendation, "predicted_peak", 0.0) or 0.0),
                float(evt_rl or 0.0),
            )
            adjusted_contract = self._round_up_to_step(base_peak * safety_margin, step=5)

            # 기존 추천보다 낮아지지 않도록 보장
            final_contract = max(int(getattr(recommendation, "recommended_contract", 0) or 0), adjusted_contract)

            new_reasoning = (
                f"{getattr(recommendation, 'reasoning', '')} | "
                f"EVT({extreme.get('method')}) 기반 재현수준 p={extreme.get('p_target', 0.98):.2f}"
                f" 반영, RL≈{(evt_rl or 0):.1f}kW"
            ).strip(" |")

            rec = ContractRecommendation(
                station_id=station_id,
                year=year,
                month=month,
                predicted_peak=float(max(getattr(recommendation, "predicted_peak", 0.0) or 0.0, float(evt_rl or 0.0))),
                recommended_contract=int(final_contract),
                confidence_interval=getattr(recommendation, "confidence_interval", None),
                seasonal_factor=getattr(recommendation, "seasonal_factor", 1.0),
                safety_margin=float(safety_margin),
                method="model+evt_block_maxima" if evt_rl is not None else getattr(recommendation, "method", "model"),
                reasoning=new_reasoning,
            )

            self.logger.info(
                f"Monthly recommendation with EVT for station {station_id} "
                f"({year}-{month:02d}): {rec.recommended_contract}kW "
                f"(EVT RL: {evt_rl if evt_rl is not None else 'NA'})"
            )
            return rec

        except Exception as e:
            self.logger.error(f"Monthly prediction failed for station {station_id}: {e}")
            # Fallback에서도 EVT 적용 시도
            fb = self._fallback_monthly_prediction(station_id, year, month)
            try:
                hist_df = self.data_repository.get_historical_sessions(
                    station_id=station_id if station_id != "ALL" else None, days=540
                )
            except Exception:
                hist_df = pd.DataFrame()
            extreme = estimate_extremes_from_df(hist_df, p_target=0.98, q_high=0.99)
            evt_rl = extreme.get("return_level")
            if evt_rl:
                peak_base = max(float(getattr(fb, "predicted_peak", 0.0) or 0.0), float(evt_rl))
                safety_margin = getattr(fb, "safety_margin", 1.20)
                adj = self._round_up_to_step(peak_base * safety_margin, step=5)
                final_contract = max(int(getattr(fb, "recommended_contract", 0) or 0), adj)
                fb = ContractRecommendation(
                    station_id=station_id,
                    year=year,
                    month=month,
                    predicted_peak=float(peak_base),
                    recommended_contract=int(final_contract),
                    confidence_interval=getattr(fb, "confidence_interval", None),
                    seasonal_factor=getattr(fb, "seasonal_factor", 1.0),
                    safety_margin=float(safety_margin),
                    method="fallback_conservative_evt",
                    reasoning=f"{getattr(fb, 'reasoning', '')} | EVT 기반 RL≈{evt_rl:.1f}kW 반영",
                )
            return fb

    def get_model_status(self, station_id: str) -> Dict[str, Any]:
        """Get status information about a model"""
        if station_id not in self._models:
            return {"status": "not_trained", "message": "Model not yet created"}

        model = self._models[station_id]
        cache_time = self._model_cache_time.get(station_id)

        return {
            "status": "trained" if model.is_trained else "not_trained",
            "metadata": model.get_metadata(),
            "last_updated": cache_time.isoformat() if cache_time else None,
            "station_id": station_id,
        }

    def invalidate_model_cache(self, station_id: Optional[str] = None) -> None:
        """Invalidate model cache for specific station or all stations"""
        if station_id:
            self._models.pop(station_id, None)
            self._model_cache_time.pop(station_id, None)
            self.logger.info(f"Invalidated model cache for station {station_id}")
        else:
            self._models.clear()
            self._model_cache_time.clear()
            self.logger.info("Invalidated all model caches")

    def get_available_stations(self) -> List[Dict[str, Any]]:
        """Get list of stations with available data"""
        try:
            stations = self.data_repository.get_available_stations()
            return [
                {
                    "station_id": station.station_id,
                    "name": station.name,
                    "location": station.location,
                    "region": station.region,
                    "city": station.city,
                    "status": station.status,
                    "has_model": station.station_id in self._models,
                }
                for station in stations
            ]
        except Exception as e:
            self.logger.error(f"Failed to get available stations: {e}")
            return []

    def _fallback_hourly_prediction(self, station_id: str) -> PredictionResult:
        """Generate fallback prediction when model fails"""
        current_time = datetime.now()
        target_time = current_time.replace(minute=0, second=0, microsecond=0)

        # Time-based fallback prediction
        hour = current_time.hour
        if 6 <= hour <= 9:  # Morning peak
            predicted_power = 45.0
        elif 11 <= hour <= 13:  # Lunch peak
            predicted_power = 49.0
        elif 18 <= hour <= 20:  # Evening peak
            predicted_power = 40.0
        else:
            predicted_power = 33.5

        return PredictionResult(
            station_id=station_id,
            predicted_peak=predicted_power,
            prediction_time=current_time,
            target_time=target_time,
            confidence=0.6,  # Lower confidence for fallback
            confidence_interval={"lower": predicted_power * 0.8, "upper": predicted_power * 1.2},
            method="fallback_time_based",
            factors={"fallback_reason": "Model training failed", "time_based_estimate": True, "hour": hour},
        )

    def _fallback_monthly_prediction(self, station_id: str, year: int, month: int) -> ContractRecommendation:
        """Generate fallback monthly recommendation when model fails"""
        # Conservative estimate based on typical EV charging patterns
        base_power = 49.0

        # Seasonal adjustment
        seasonal_factors = {
            12: 1.15,
            1: 1.15,
            2: 1.10,  # Winter
            3: 1.0,
            4: 1.0,
            5: 1.0,  # Spring
            6: 1.05,
            7: 1.10,
            8: 1.05,  # Summer
            9: 1.0,
            10: 1.0,
            11: 1.05,  # Fall
        }

        seasonal_factor = seasonal_factors.get(month, 1.0)
        predicted_peak = base_power * seasonal_factor

        # Conservative contract recommendation
        safety_margin = 1.2  # Higher safety margin for fallback
        recommended_contract = int((predicted_peak * safety_margin // 5 + 1) * 5)

        return ContractRecommendation(
            station_id=station_id,
            year=year,
            month=month,
            predicted_peak=predicted_peak,
            recommended_contract=recommended_contract,
            confidence_interval={"lower": predicted_peak * 0.8, "upper": predicted_peak * 1.3},
            seasonal_factor=seasonal_factor,
            safety_margin=safety_margin,
            method="fallback_conservative",
            reasoning="모델 훈련 실패로 보수적 추정 적용",
        )

    @staticmethod
    def _round_up_to_step(value: float, step: int = 5) -> int:
        if not math.isfinite(value):
            return 0
        if step <= 0:
            step = 1
        return int((int(value + step - 1) // step + (1 if (value + step - 1) % step else 0)) * step)
