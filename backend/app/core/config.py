# 설정 관리
from dataclasses import dataclass, asdict
from typing import Dict, Any
import os
import json
from pathlib import Path

# yaml 의존성을 선택적으로 만듦
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


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
            self.ensemble_model_weights = {"statistical": 0.4, "time_series": 0.4, "ensemble": 0.2}


class ConfigManager:
    """설정 관리자"""

    def __init__(self, config_file: str = None):
        self.config = PredictionConfig()
        if config_file:
            self.load_from_file(config_file)

    def load_from_file(self, file_path: str):
        """파일에서 설정 로드"""
        try:
            path = Path(file_path)

            if not path.exists():
                raise FileNotFoundError(f"Config file not found: {file_path}")

            with open(path, "r", encoding="utf-8") as f:
                if (path.suffix.lower() == ".yaml" or path.suffix.lower() == ".yml") and YAML_AVAILABLE:
                    data = yaml.safe_load(f)
                elif path.suffix.lower() == ".json":
                    data = json.load(f)
                else:
                    if not YAML_AVAILABLE and (path.suffix.lower() in [".yaml", ".yml"]):
                        raise ValueError("YAML support not available. Install PyYAML: pip install pyyaml")
                    raise ValueError(f"Unsupported config file format: {path.suffix}")

            # Update config attributes with loaded data
            for key, value in data.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)

        except Exception as e:
            print(f"Failed to load config from {file_path}: {e}")
            raise

    def save_to_file(self, file_path: str):
        """파일로 설정 저장"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            config_dict = asdict(self.config)

            with open(path, "w", encoding="utf-8") as f:
                if (path.suffix.lower() == ".yaml" or path.suffix.lower() == ".yml") and YAML_AVAILABLE:
                    yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
                elif path.suffix.lower() == ".json":
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
                else:
                    if not YAML_AVAILABLE and (path.suffix.lower() in [".yaml", ".yml"]):
                        raise ValueError("YAML support not available. Install PyYAML: pip install pyyaml")
                    raise ValueError(f"Unsupported config file format: {path.suffix}")

        except Exception as e:
            print(f"Failed to save config to {file_path}: {e}")
            raise

    def get_config_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 반환"""
        return asdict(self.config)

    def update_config(self, **kwargs):
        """설정 업데이트"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                print(f"Warning: Unknown config key '{key}' ignored")
