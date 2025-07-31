# 데이터 검증 모듈
import pandas as pd
from typing import Dict, List


class DataValidator:
    """데이터 품질 검증"""
    
    def validate_power_data(self, df: pd.DataFrame) -> Dict[str, bool]:
        """전력 데이터 검증"""
        validation_results = {
            "has_required_columns": self._check_required_columns(df),
            "power_ranges_valid": self._check_power_ranges(df),
            "timestamps_valid": self._check_timestamps(df)
        }
        return validation_results
    
    def _check_required_columns(self, df: pd.DataFrame) -> bool:
        """필수 컬럼 존재 확인"""
        required_cols = ["충전시작일시", "충전종료일시", "순간최고전력"]
        return all(col in df.columns for col in required_cols)
    
    def _check_power_ranges(self, df: pd.DataFrame) -> bool:
        """전력 데이터 범위 확인"""
        # TODO: 전력값이 합리적인 범위 내에 있는지 확인
        return True
    
    def _check_timestamps(self, df: pd.DataFrame) -> bool:
        """타임스탬프 유효성 확인"""
        # TODO: 시작시간 < 종료시간 등 확인
        return True
