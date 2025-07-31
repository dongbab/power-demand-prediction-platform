# 설정 관리
from dataclasses import dataclass
from typing import Dict, Any
import os


@dataclass
class PredictionConfig:
    """예측 시스템 설정"""
    # 데이터 설정
    data_retention_days: int = 90
    feature_update_interval: int = 900  # 15분
    
    # 모델 설정
    model_retrain_frequency: str = "daily"
    prediction_horizon_hours: int = 24
    ensemble_model_weights: Dict[str, float] = None
    
    # 성능 임계값
    max_underprediction_rate: float = 0.1
    max_prediction_error: float = 0.15
    
    # 안전 마진
    safety_margin: float = 1.1
    confidence_level: float = 0.95
    
    # 데이터베이스 설정
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///charging_data.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # API 설정
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    
    def __post_init__(self):
        if self.ensemble_model_weights is None:
            self.ensemble_model_weights = {
                "statistical": 0.4,
                "time_series": 0.4,
                "ensemble": 0.2
            }


class ConfigManager:
    """설정 관리자"""
    
    def __init__(self, config_file: str = None):
        self.config = PredictionConfig()
        if config_file:
            self.load_from_file(config_file)
    
    def load_from_file(self, file_path: str):
        """파일에서 설정 로드"""
        # TODO: YAML/JSON 설정 파일 로드
        pass
    
    def save_to_file(self, file_path: str):
        """파일로 설정 저장"""
        # TODO: 설정 파일 저장
        pass
