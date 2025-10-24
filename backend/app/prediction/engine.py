# Re-export from the new modular structure
from .prediction_engine import PredictionEngine
from .models.prediction_types import ModelPrediction, EnsemblePrediction

# Keep the old class name for backwards compatibility
__all__ = ['PredictionEngine', 'ModelPrediction', 'EnsemblePrediction']