# 데이터 로더 테스트
import pytest
import pandas as pd
from data.loader import ChargingDataLoader


def test_data_loader_init():
    """데이터 로더 초기화 테스트"""
    loader = ChargingDataLoader("TEST_STATION")
    assert loader.station_id == "TEST_STATION"


def test_load_historical_sessions(sample_charging_data):
    """과거 세션 데이터 로드 테스트"""
    loader = ChargingDataLoader("TEST_STATION")
    # TODO: 실제 로딩 로직 테스트
    # result = loader.load_historical_sessions(30)
    # assert isinstance(result, pd.DataFrame)
    pass


def test_load_realtime_status():
    """실시간 상태 로드 테스트"""
    loader = ChargingDataLoader("TEST_STATION")
    # TODO: 실시간 상태 로딩 테스트
    # result = loader.load_realtime_status()
    # assert isinstance(result, dict)
    pass
