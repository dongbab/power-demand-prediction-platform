from typing import Dict, Any, Optional
import logging
from datetime import datetime

from .engine import PredictionEngine
from ..data.repository import ChargingDataRepository
from ..models.entities import AnalysisResult


class PredictionService:
    def __init__(self, prediction_engine: PredictionEngine, data_repository: ChargingDataRepository):
        self.prediction_engine = prediction_engine
        self.data_repository = data_repository
        self.logger = logging.getLogger(__name__)

    def get_station_prediction(self, station_id: str) -> Dict[str, Any]:
        """Get comprehensive prediction for a station"""
        try:
            # Validate station exists
            if not self.data_repository.station_exists(station_id):
                return {"error": f"Station {station_id} not found"}

            # Get hourly prediction
            prediction = self.prediction_engine.predict_next_hour_peak(station_id)

            # Get station metadata
            station_info = self.data_repository.get_station_info(station_id)

            result = prediction.to_dict()
            result["station_name"] = station_info.name if station_info else f"Station {station_id}"

            return result

        except Exception as e:
            self.logger.error(f"Failed to get station prediction for {station_id}: {e}")
            return {"error": str(e)}

    def get_monthly_contract_recommendation(
        self, station_id: str, year: int, month: int, mode: str = "p95", round_kw: int = 5
    ) -> Dict[str, Any]:
        """Get monthly contract recommendation"""
        try:
            # Validate station exists
            if not self.data_repository.station_exists(station_id):
                return {"error": f"Station {station_id} not found"}

            # Get recommendation
            recommendation = self.prediction_engine.predict_monthly_contract(station_id, year, month)

            # Apply rounding if specified
            if round_kw > 1:
                recommendation.recommended_contract = int(
                    (recommendation.recommended_contract // round_kw + 1) * round_kw
                )

            # Get station metadata
            station_info = self.data_repository.get_station_info(station_id)

            result = recommendation.to_dict()
            result["station_name"] = station_info.name if station_info else f"Station {station_id}"
            result["mode"] = mode
            result["horizon_days"] = self._get_month_days(year, month)

            return result

        except Exception as e:
            self.logger.error(f"Failed to get monthly recommendation for {station_id}: {e}")
            return {"error": str(e)}

    def get_station_analysis(self, station_id: str) -> Dict[str, Any]:
        """Get comprehensive station analysis"""
        try:
            # Validate station exists
            if not self.data_repository.station_exists(station_id):
                return {"error": f"Station {station_id} not found"}

            # Get station info
            station_info = self.data_repository.get_station_info(station_id)
            if not station_info:
                return {"error": f"Station {station_id} metadata not found"}

            # Get data summary
            summary = self.data_repository.get_data_summary(station_id)

            # Get charging patterns
            patterns = self.data_repository.analyze_charging_patterns(station_id)

            # Calculate performance metrics
            performance_metrics = self._calculate_performance_metrics(patterns)

            # Generate charts data
            charts_data = self._generate_charts_data(patterns, summary)

            # Get real-time status (if available)
            realtime_status = self.data_repository.get_realtime_status(station_id)

            # Get external factors
            external_factors = self.data_repository.get_external_factors()

            return {
                "station_id": station_id,
                "timestamp": datetime.now().isoformat(),
                "station_info": station_info.__dict__ if hasattr(station_info, "__dict__") else station_info,
                "summary": summary,
                "patterns": patterns,
                "performance_analysis": performance_metrics,
                "charts_data": charts_data,
                "realtime_status": realtime_status,
                "external_factors": external_factors,
            }

        except Exception as e:
            self.logger.error(f"Failed to get station analysis for {station_id}: {e}")
            return {"error": str(e)}

    def get_all_stations_summary(self) -> Dict[str, Any]:
        """Get summary of all available stations"""
        try:
            stations = self.prediction_engine.get_available_stations()

            # Calculate aggregate statistics
            total_stations = len([s for s in stations if s["station_id"] != "ALL"])
            active_stations = len([s for s in stations if s.get("status") == "정상 운영"])
            trained_models = len([s for s in stations if s.get("has_model", False)])

            # Get regional distribution
            regions = {}
            for station in stations:
                if station["station_id"] != "ALL":
                    region = station.get("region", "미상")
                    regions[region] = regions.get(region, 0) + 1

            return {
                "stations": stations,
                "summary": {
                    "total": total_stations,
                    "active": active_stations,
                    "trained_models": trained_models,
                    "regional_distribution": regions,
                },
                "last_updated": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Failed to get stations summary: {e}")
            return {"error": str(e)}

    def refresh_station_model(self, station_id: str) -> Dict[str, Any]:
        """Refresh/retrain model for a specific station"""
        try:
            # Invalidate existing model
            self.prediction_engine.invalidate_model_cache(station_id)

            # Create and train new model
            model = self.prediction_engine.get_or_create_model(station_id)

            return {
                "message": f"Model refreshed successfully for station {station_id}",
                "status": "success",
                "model_info": (
                    model.get_metadata().__dict__ if hasattr(model.get_metadata(), "__dict__") else model.get_metadata()
                ),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Failed to refresh model for {station_id}: {e}")
            return {"error": str(e)}

    def _calculate_performance_metrics(self, patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate performance metrics from patterns"""
        if "power_statistics" not in patterns:
            return {}

        stats = patterns["power_statistics"]
        avg_power = stats.get("mean", 0.0)
        max_power = stats.get("max", 0.0)

        # Assume 100kW rated power for most stations
        rated_power = 100.0
        utilization_rate = (avg_power / rated_power) * 100.0
        peak_utilization = (max_power / rated_power) * 100.0

        # Efficiency grade based on utilization
        if utilization_rate > 50:
            grade = "A"
        elif utilization_rate > 30:
            grade = "B"
        elif utilization_rate > 15:
            grade = "C"
        else:
            grade = "D"

        return {
            "utilization_rate": round(utilization_rate, 1),
            "peak_utilization": round(peak_utilization, 1),
            "average_session_power": round(avg_power, 1),
            "maximum_recorded_power": round(max_power, 1),
            "efficiency_grade": grade,
            "rated_power": rated_power,
        }

    def _generate_charts_data(self, patterns: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, Any]:
        """Generate data for charts visualization"""
        charts_data = {}

        # Hourly pattern chart
        if "hourly_patterns" in patterns:
            hourly_data = [patterns["hourly_patterns"].get(str(h), {}).get("avg_power", 0.0) for h in range(24)]
            charts_data["hourly_pattern"] = hourly_data

        # Monthly predictions (seasonal variation)
        if "power_statistics" in patterns:
            base_power = patterns["power_statistics"].get("percentile_95", 50.0)
            seasonal_factors = [1.20, 1.15, 1.05, 1.0, 1.0, 1.10, 1.15, 1.10, 1.0, 1.05, 1.10, 1.20]

            charts_data["monthly_predictions"] = {
                "data": [round(base_power * factor, 1) for factor in seasonal_factors],
                "labels": ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"],
            }

        return charts_data

    def _get_month_days(self, year: int, month: int) -> int:
        """Get number of days in a month"""
        from calendar import monthrange

        return monthrange(year, month)[1]
