# 시간 특성 추출
from datetime import datetime
import pandas as pd
from typing import Dict


class TemporalFeatureExtractor:
    """시간 기반 특성 추출"""

    def extract_time_features(self, timestamp: datetime) -> Dict:
        """시간 특성 추출"""
        return {
            "hour": timestamp.hour,
            "day_of_week": timestamp.weekday(),
            "month": timestamp.month,
            "is_weekend": timestamp.weekday() >= 5,
            "is_holiday": self._check_holiday(timestamp),
            "season": self._get_season(timestamp.month),
        }

    def _check_holiday(self, timestamp: datetime) -> bool:
        """공휴일 확인"""
        # TODO: 공휴일 데이터베이스 연동
        return False

    def _get_season(self, month: int) -> str:
        """계절 구분"""
        if month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        elif month in [9, 10, 11]:
            return "autumn"
        else:
            return "winter"
