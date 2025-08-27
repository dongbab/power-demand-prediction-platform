"""Base model classes and interfaces"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd

from .entities import PredictionResult, ContractRecommendation


@dataclass
class ModelMetadata:
    """Model metadata information"""

    name: str
    version: str
    created_at: datetime
    last_trained: Optional[datetime] = None
    training_data_size: Optional[int] = None
    accuracy_metrics: Optional[Dict[str, float]] = None


class BaseModel(ABC):
    """Base class for all prediction models"""

    def __init__(self, station_id: str):
        self.station_id = station_id
        self.metadata = ModelMetadata(name=self.__class__.__name__, version="1.0.0", created_at=datetime.now())
        self._is_trained = False

    @abstractmethod
    def train(self, data: pd.DataFrame) -> None:
        """Train the model with historical data"""
        pass

    @abstractmethod
    def predict_hourly_peak(self, hours_ahead: int = 24) -> PredictionResult:
        """Predict peak power for the next N hours"""
        pass

    @abstractmethod
    def predict_monthly_peak(self, year: int, month: int) -> ContractRecommendation:
        """Predict monthly peak and recommend contract power"""
        pass

    @property
    def is_trained(self) -> bool:
        """Check if model has been trained"""
        return self._is_trained

    def get_metadata(self) -> ModelMetadata:
        """Get model metadata"""
        return self.metadata

    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate input data format"""
        required_columns = ["충전시작일시", "충전소ID", "순간최고전력"]
        return all(col in data.columns for col in required_columns)
