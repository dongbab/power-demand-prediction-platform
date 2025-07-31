# 테스트 설정
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture
def sample_charging_data():
    """테스트용 충전 데이터"""
    dates = pd.date_range(start='2024-01-01', end='2024-01-31', freq='H')
    n_sessions = len(dates)
    
    data = {
        '충전시작일시': dates,
        '충전종료일시': dates + pd.Timedelta(hours=1),
        '순간최고전력': np.random.normal(75, 15, n_sessions),
        '시작SOC(%)': np.random.uniform(10, 80, n_sessions),
        '완료SOC(%)': np.random.uniform(50, 100, n_sessions),
        '충전소ID': ['TEST_STATION'] * n_sessions,
        '충전기ID': [f'CHG_{i%4:02d}' for i in range(n_sessions)]
    }
    
    return pd.DataFrame(data)


@pytest.fixture
def mock_config():
    """테스트용 설정"""
    from utils.config import PredictionConfig
    return PredictionConfig(
        data_retention_days=30,
        prediction_horizon_hours=1,
        safety_margin=1.05
    )
