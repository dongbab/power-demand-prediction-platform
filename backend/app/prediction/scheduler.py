"""Prediction scheduler for automated model training and updates"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from .engine import PredictionEngine
from ..data.repository import ChargingDataRepository


class PredictionScheduler:
    """Scheduler for automated prediction tasks"""

    def __init__(self, prediction_engine: PredictionEngine, data_repository: ChargingDataRepository):
        self.scheduler = AsyncIOScheduler()
        self.prediction_engine = prediction_engine
        self.data_repository = data_repository
        self.logger = logging.getLogger(__name__)
        self._is_running = False

    def start_scheduled_jobs(self):
        """Start all scheduled jobs"""
        if self._is_running:
            self.logger.warning("Scheduler is already running")
            return

        # Model retraining (daily at 2 AM)
        self.scheduler.add_job(
            self._retrain_models, CronTrigger(hour=2, minute=0), id="model_retrain", max_instances=1, coalesce=True
        )

        # Prediction cache refresh (every hour)
        self.scheduler.add_job(
            self._refresh_prediction_cache, "interval", minutes=60, id="prediction_cache_refresh", max_instances=1
        )

        # Model validation (daily at 3 AM)
        self.scheduler.add_job(
            self._validate_models, CronTrigger(hour=3, minute=0), id="model_validation", max_instances=1
        )

        # Health check (every 30 minutes)
        self.scheduler.add_job(self._health_check, "interval", minutes=30, id="health_check")

        self.scheduler.start()
        self._is_running = True
        self.logger.info("Prediction scheduler started with all jobs")

    async def _retrain_models(self):
        """Retrain all models with fresh data"""
        self.logger.info("Starting automated model retraining")

        try:
            # Get all available stations
            stations = self.prediction_engine.get_available_stations()
            retrain_count = 0
            error_count = 0

            for station in stations:
                station_id = station["station_id"]

                try:
                    # Skip the ALL aggregated station for individual retraining
                    if station_id == "ALL":
                        continue

                    # Invalidate existing model to force retraining
                    self.prediction_engine.invalidate_model_cache(station_id)

                    # Create and train new model
                    self.prediction_engine.get_or_create_model(station_id)
                    retrain_count += 1

                    self.logger.debug(f"Retrained model for station {station_id}")

                except Exception as e:
                    error_count += 1
                    self.logger.error(f"Failed to retrain model for station {station_id}: {e}")

            self.logger.info(f"Model retraining completed: {retrain_count} successful, {error_count} errors")

        except Exception as e:
            self.logger.error(f"Model retraining job failed: {e}")

    async def _refresh_prediction_cache(self):
        """Refresh prediction cache for active stations"""
        self.logger.info("Refreshing prediction cache")

        try:
            # Get stations with trained models
            stations = self.prediction_engine.get_available_stations()
            active_stations = [s for s in stations if s.get("has_model", False)]

            refresh_count = 0
            for station in active_stations[:10]:  # Limit to 10 stations per run
                station_id = station["station_id"]

                try:
                    # Generate fresh predictions to warm the cache
                    self.prediction_engine.predict_next_hour_peak(station_id)
                    refresh_count += 1

                except Exception as e:
                    self.logger.warning(f"Failed to refresh cache for station {station_id}: {e}")

            self.logger.info(f"Refreshed prediction cache for {refresh_count} stations")

        except Exception as e:
            self.logger.error(f"Prediction cache refresh job failed: {e}")

    async def _validate_models(self):
        """Validate model performance and health"""
        self.logger.info("Starting model validation")

        try:
            stations = self.prediction_engine.get_available_stations()
            validation_results = []

            for station in stations:
                station_id = station["station_id"]

                try:
                    status = self.prediction_engine.get_model_status(station_id)

                    if status["status"] == "trained":
                        # Perform basic validation
                        prediction = self.prediction_engine.predict_next_hour_peak(station_id)

                        validation_results.append(
                            {
                                "station_id": station_id,
                                "status": "healthy" if 0 < prediction.predicted_peak < 500 else "suspicious",
                                "predicted_peak": prediction.predicted_peak,
                                "confidence": prediction.confidence,
                            }
                        )

                except Exception as e:
                    validation_results.append({"station_id": station_id, "status": "error", "error": str(e)})

            # Log summary
            healthy_count = sum(1 for r in validation_results if r.get("status") == "healthy")
            suspicious_count = sum(1 for r in validation_results if r.get("status") == "suspicious")
            error_count = sum(1 for r in validation_results if r.get("status") == "error")

            self.logger.info(
                f"Model validation completed: {healthy_count} healthy, "
                f"{suspicious_count} suspicious, {error_count} errors"
            )

            # Log suspicious models
            for result in validation_results:
                if result.get("status") == "suspicious":
                    self.logger.warning(
                        f"Suspicious model for station {result['station_id']}: "
                        f"predicted_peak={result.get('predicted_peak', 'N/A')}"
                    )

        except Exception as e:
            self.logger.error(f"Model validation job failed: {e}")

    async def _health_check(self):
        """Perform system health check"""
        try:
            # Check data repository connectivity
            stations = self.data_repository.get_available_stations()
            station_count = len(stations)

            # Check prediction engine status
            model_count = len(self.prediction_engine._models)

            self.logger.debug(f"Health check: {station_count} stations available, {model_count} models cached")

            # Log warning if no models are cached (might indicate issues)
            if model_count == 0 and station_count > 0:
                self.logger.warning("No models cached despite available stations")

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")

    def stop(self):
        """Stop the scheduler"""
        if not self._is_running:
            self.logger.warning("Scheduler is not running")
            return

        self.scheduler.shutdown(wait=True)
        self._is_running = False
        self.logger.info("Prediction scheduler stopped")

    def get_job_status(self) -> List[dict]:
        """Get status of all scheduled jobs"""
        jobs = []

        for job in self.scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name or job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                }
            )

        return jobs

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self._is_running and self.scheduler.running
