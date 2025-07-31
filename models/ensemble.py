# 앙상블 모델
from typing import List, Dict, Any
import numpy as np


class EnsembleModel:
    """앙상블 예측 모델"""
    
    def __init__(self, models: List[Any]):
        self.models = models
        self.weights = None
        self.is_fitted = False
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """앙상블 모델 훈련"""
        # 각 개별 모델 훈련
        for model in self.models:
            model.fit(X, y)
        
        # 가중치 계산
        self._calculate_weights(X, y)
        self.is_fitted = True
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """앙상블 예측"""
        if not self.is_fitted:
            raise ValueError("모델이 훈련되지 않았습니다.")
        
        predictions = []
        for model in self.models:
            pred = model.predict(X)
            predictions.append(pred)
        
        # 가중 평균
        ensemble_pred = np.average(predictions, weights=self.weights, axis=0)
        return ensemble_pred
    
    def _calculate_weights(self, X: np.ndarray, y: np.ndarray) -> None:
        """모델별 가중치 계산"""
        # TODO: 교차검증 기반 가중치 계산
        self.weights = np.ones(len(self.models)) / len(self.models)
