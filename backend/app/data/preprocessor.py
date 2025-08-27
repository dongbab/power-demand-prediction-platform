# 데이터 전처리 모듈
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any
from datetime import datetime
import logging


class DataPreprocessor:
    """데이터 전처리 클래스"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def clean_session_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """세션 데이터 정제"""
        if df.empty:
            return df

        df_clean = df.copy()
        original_count = len(df_clean)

        self.logger.info(f"Starting data cleaning for {original_count:,} records")

        # 1. 결측값 처리
        df_clean = self._handle_missing_values(df_clean)

        # 2. 이상치 제거
        df_clean = self._remove_outliers(df_clean)

        # 3. 데이터 유효성 검사
        df_clean = self._validate_data_consistency(df_clean)

        # 4. 중복 제거
        df_clean = self._remove_duplicates(df_clean)

        cleaned_count = len(df_clean)
        removed_count = original_count - cleaned_count

        self.logger.info(
            f"Data cleaning completed: {removed_count:,} records removed "
            f"({removed_count/original_count*100:.1f}%), "
            f"{cleaned_count:,} records remaining"
        )

        return df_clean

    def validate_power_ranges(self, df: pd.DataFrame) -> pd.DataFrame:
        """전력 데이터 범위 검증 및 정제"""
        if df.empty or "순간최고전력" not in df.columns:
            return df

        df_filtered = df.copy()
        original_count = len(df_filtered)

        # 물리적 한계 설정 (EV 충전기 기준)
        min_power = 0.1  # 0.1kW - 최소 충전 전력
        max_power = 350.0  # 350kW - 현재 최고 급속충전기 한계

        # 전력 범위 필터링
        power_mask = (df_filtered["순간최고전력"] >= min_power) & (df_filtered["순간최고전력"] <= max_power)

        invalid_count = (~power_mask).sum()
        df_filtered = df_filtered[power_mask]

        self.logger.info(
            f"Power validation: {invalid_count:,} records removed " f"(outside range {min_power}-{max_power}kW)"
        )

        # 통계적 이상치 제거 (IQR 방법)
        if len(df_filtered) > 100:  # 충분한 데이터가 있을 때만
            Q1 = df_filtered["순간최고전력"].quantile(0.25)
            Q3 = df_filtered["순간최고전력"].quantile(0.75)
            IQR = Q3 - Q1

            lower_bound = Q1 - 3.0 * IQR  # 더 관대한 범위 (보통 1.5 * IQR)
            upper_bound = Q3 + 3.0 * IQR

            outlier_mask = (df_filtered["순간최고전력"] >= max(lower_bound, min_power)) & (
                df_filtered["순간최고전력"] <= min(upper_bound, max_power)
            )

            statistical_outliers = (~outlier_mask).sum()
            df_filtered = df_filtered[outlier_mask]

            self.logger.info(f"Statistical outlier removal: {statistical_outliers:,} records removed")

        final_count = len(df_filtered)
        total_removed = original_count - final_count

        self.logger.info(
            f"Power range validation completed: {total_removed:,} total records removed "
            f"({total_removed/original_count*100:.1f}%)"
        )

        return df_filtered

    def create_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """시간 기반 특성 생성"""
        if df.empty:
            return df

        df_enhanced = df.copy()

        # 날짜 컬럼 찾기
        date_columns = [col for col in df.columns if "일시" in col or "time" in col.lower()]

        if not date_columns:
            self.logger.warning("No datetime columns found for time feature extraction")
            return df_enhanced

        primary_date_col = date_columns[0]

        if not pd.api.types.is_datetime64_any_dtype(df_enhanced[primary_date_col]):
            self.logger.info(f"Converting {primary_date_col} to datetime")
            df_enhanced[primary_date_col] = pd.to_datetime(df_enhanced[primary_date_col], errors="coerce")

        # 시간 기반 특성 생성
        dt_col = df_enhanced[primary_date_col]

        # 기본 시간 특성
        df_enhanced["hour"] = dt_col.dt.hour
        df_enhanced["day_of_week"] = dt_col.dt.dayofweek  # 0=Monday, 6=Sunday
        df_enhanced["day_of_month"] = dt_col.dt.day
        df_enhanced["month"] = dt_col.dt.month
        df_enhanced["quarter"] = dt_col.dt.quarter
        df_enhanced["year"] = dt_col.dt.year

        # 범주형 시간 특성
        df_enhanced["is_weekend"] = (dt_col.dt.dayofweek >= 5).astype(int)
        df_enhanced["is_business_hour"] = ((dt_col.dt.hour >= 9) & (dt_col.dt.hour <= 17)).astype(int)

        # 시간대 분류
        df_enhanced["time_period"] = pd.cut(
            dt_col.dt.hour, bins=[-1, 6, 12, 18, 24], labels=["밤", "오전", "오후", "저녁"]
        ).astype(str)

        # 계절 특성
        df_enhanced["season"] = ((dt_col.dt.month % 12 + 3) // 3).map({1: "겨울", 2: "봄", 3: "여름", 4: "가을"})

        # 공휴일 특성 (단순화된 버전)
        df_enhanced["is_holiday"] = self._identify_holidays(dt_col)

        feature_count = len([col for col in df_enhanced.columns if col not in df.columns])
        self.logger.info(f"Time features created: {feature_count} new features added")

        return df_enhanced

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """결측값 처리"""
        df_clean = df.copy()

        # 필수 컬럼의 결측값 제거
        essential_columns = ["충전시작일시", "순간최고전력"]
        for col in essential_columns:
            if col in df_clean.columns:
                before_count = len(df_clean)
                df_clean = df_clean.dropna(subset=[col])
                removed = before_count - len(df_clean)
                if removed > 0:
                    self.logger.info(f"Removed {removed:,} records with missing {col}")

        return df_clean

    def _remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """이상치 제거"""
        df_clean = df.copy()

        # 충전 시간 이상치 (24시간 초과)
        if "충전시간" in df_clean.columns:
            before = len(df_clean)
            df_clean = df_clean[df_clean["충전시간"] <= 24 * 60]  # 24시간 = 1440분
            removed = before - len(df_clean)
            if removed > 0:
                self.logger.info(f"Removed {removed:,} records with charging time > 24 hours")

        # SOC 이상치
        for soc_col in ["시작SOC(%)", "완료SOC(%)"]:
            if soc_col in df_clean.columns:
                before = len(df_clean)
                df_clean = df_clean[
                    (df_clean[soc_col].isna()) | ((df_clean[soc_col] >= 0) & (df_clean[soc_col] <= 100))
                ]
                removed = before - len(df_clean)
                if removed > 0:
                    self.logger.info(f"Removed {removed:,} records with invalid {soc_col}")

        return df_clean

    def _validate_data_consistency(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터 일관성 검증"""
        df_clean = df.copy()

        # 시작시간 <= 종료시간 확인
        if "충전시작일시" in df_clean.columns and "충전종료일시" in df_clean.columns:
            before = len(df_clean)
            valid_time_mask = (df_clean["충전시작일시"] <= df_clean["충전종료일시"]) | df_clean["충전종료일시"].isna()

            df_clean = df_clean[valid_time_mask]
            removed = before - len(df_clean)
            if removed > 0:
                self.logger.info(f"Removed {removed:,} records with invalid time ranges")

        # 시작SOC <= 완료SOC 확인 (일반적인 경우)
        if "시작SOC(%)" in df_clean.columns and "완료SOC(%)" in df_clean.columns:
            before = len(df_clean)
            valid_soc_mask = (
                (df_clean["시작SOC(%)"] <= df_clean["완료SOC(%)"])
                | df_clean["시작SOC(%)"].isna()
                | df_clean["완료SOC(%)"].isna()
            )
            df_clean = df_clean[valid_soc_mask]
            removed = before - len(df_clean)
            if removed > 0:
                self.logger.info(f"Removed {removed:,} records with invalid SOC ranges")

        return df_clean

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """중복 제거"""
        before = len(df)

        # 시간 기반 중복 제거 (동일 충전소, 동일 시작시간)
        if "충전시작일시" in df.columns and "충전소ID" in df.columns:
            df_clean = df.drop_duplicates(subset=["충전소ID", "충전시작일시"], keep="first")
        else:
            df_clean = df.drop_duplicates()

        removed = before - len(df_clean)
        if removed > 0:
            self.logger.info(f"Removed {removed:,} duplicate records")

        return df_clean

    def _identify_holidays(self, dt_series: pd.Series) -> pd.Series:
        """공휴일 식별 (단순화된 버전)"""
        # 주요 공휴일 (고정)
        holidays = [
            "01-01",  # 신정
            "03-01",  # 삼일절
            "05-05",  # 어린이날
            "06-06",  # 현충일
            "08-15",  # 광복절
            "10-03",  # 개천절
            "10-09",  # 한글날
            "12-25",  # 성탄절
        ]

        month_day = dt_series.dt.strftime("%m-%d")
        is_holiday = month_day.isin(holidays)

        return is_holiday.astype(int)

    def get_preprocessing_summary(self, original_df: pd.DataFrame, processed_df: pd.DataFrame) -> Dict[str, Any]:
        """전처리 요약 정보 생성"""
        original_count = len(original_df)
        processed_count = len(processed_df)
        removed_count = original_count - processed_count

        return {
            "original_records": original_count,
            "processed_records": processed_count,
            "removed_records": removed_count,
            "removal_rate": round(removed_count / original_count * 100, 2) if original_count > 0 else 0,
            "original_columns": len(original_df.columns),
            "processed_columns": len(processed_df.columns),
            "new_features": len(processed_df.columns) - len(original_df.columns),
        }
