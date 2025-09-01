# 집계 특성
import pandas as pd
import numpy as np
from typing import Dict, Any
import logging


class FeatureAggregator:
    

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def aggregate_session_features(self, df: pd.DataFrame) -> Dict[str, Any]:
        
        if df.empty:
            return {}

        try:
            features = {}

            # 기본 정보
            features["total_sessions"] = len(df)
            features["unique_stations"] = df["충전소ID"].nunique() if "충전소ID" in df.columns else 1
            features["unique_chargers"] = df["충전기ID"].nunique() if "충전기ID" in df.columns else 1

            # 전력 통계 계산
            if "순간최고전력" in df.columns:
                power_data = df["순간최고전력"].dropna()
                if not power_data.empty:
                    features["power_stats"] = {
                        "count": len(power_data),
                        "mean": float(power_data.mean()),
                        "std": float(power_data.std()),
                        "min": float(power_data.min()),
                        "max": float(power_data.max()),
                        "percentile_25": float(power_data.quantile(0.25)),
                        "percentile_50": float(power_data.quantile(0.50)),
                        "percentile_75": float(power_data.quantile(0.75)),
                        "percentile_90": float(power_data.quantile(0.90)),
                        "percentile_95": float(power_data.quantile(0.95)),
                        "percentile_99": float(power_data.quantile(0.99)),
                    }

            # 에너지 통계 계산
            if "충전량(kWh)" in df.columns:
                energy_data = df["충전량(kWh)"].dropna()
                if not energy_data.empty:
                    features["energy_stats"] = {
                        "total_energy": float(energy_data.sum()),
                        "avg_energy": float(energy_data.mean()),
                        "max_energy": float(energy_data.max()),
                        "min_energy": float(energy_data.min()),
                    }

            # 충전 시간 통계
            if "충전시간" in df.columns:
                time_data = df["충전시간"].dropna()
                if not time_data.empty:
                    features["duration_stats"] = {
                        "avg_duration": float(time_data.mean()),
                        "max_duration": float(time_data.max()),
                        "min_duration": float(time_data.min()),
                        "total_duration": float(time_data.sum()),
                    }

            # SOC 통계
            soc_stats = {}
            for soc_col in ["시작SOC(%)", "완료SOC(%)"]:
                if soc_col in df.columns:
                    soc_data = df[soc_col].dropna()
                    if not soc_data.empty:
                        soc_stats[soc_col] = {
                            "avg": float(soc_data.mean()),
                            "min": float(soc_data.min()),
                            "max": float(soc_data.max()),
                        }

            if soc_stats:
                features["soc_stats"] = soc_stats

            # 시간대별 패턴 분석
            features["hourly_patterns"] = self._analyze_hourly_patterns(df)

            # 요일별 패턴 분석
            features["daily_patterns"] = self._analyze_daily_patterns(df)

            # 날짜 범위
            if "충전시작일시" in df.columns:
                start_times = pd.to_datetime(df["충전시작일시"], errors="coerce").dropna()
                if not start_times.empty:
                    features["date_range"] = {
                        "start": start_times.min().isoformat(),
                        "end": start_times.max().isoformat(),
                        "days_covered": (start_times.max() - start_times.min()).days + 1,
                    }

            self.logger.info(f"Session features aggregated: {features['total_sessions']} sessions")
            return features

        except Exception as e:
            self.logger.error(f"Error aggregating session features: {e}", exc_info=True)
            return {}

    def _analyze_hourly_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        
        if "충전시작일시" not in df.columns or "순간최고전력" not in df.columns:
            return {}

        try:
            df_time = df.copy()
            df_time["충전시작일시"] = pd.to_datetime(df_time["충전시작일시"], errors="coerce")
            df_time = df_time.dropna(subset=["충전시작일시", "순간최고전력"])

            if df_time.empty:
                return {}

            df_time["hour"] = df_time["충전시작일시"].dt.hour

            hourly_stats = df_time.groupby("hour")["순간최고전력"].agg(["count", "mean", "max", "std"]).round(2)

            patterns = {}
            for hour in hourly_stats.index:
                patterns[str(hour)] = {
                    "session_count": int(hourly_stats.loc[hour, "count"]),
                    "avg_power": float(hourly_stats.loc[hour, "mean"]),
                    "max_power": float(hourly_stats.loc[hour, "max"]),
                    "std_power": (
                        float(hourly_stats.loc[hour, "std"]) if not pd.isna(hourly_stats.loc[hour, "std"]) else 0.0
                    ),
                }

            return patterns

        except Exception as e:
            self.logger.error(f"Error analyzing hourly patterns: {e}")
            return {}

    def _analyze_daily_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        
        if "충전시작일시" not in df.columns or "순간최고전력" not in df.columns:
            return {}

        try:
            df_time = df.copy()
            df_time["충전시작일시"] = pd.to_datetime(df_time["충전시작일시"], errors="coerce")
            df_time = df_time.dropna(subset=["충전시작일시", "순간최고전력"])

            if df_time.empty:
                return {}

            df_time["day_of_week"] = df_time["충전시작일시"].dt.dayofweek  # 0=Monday

            daily_stats = df_time.groupby("day_of_week")["순간최고전력"].agg(["count", "mean", "max"]).round(2)

            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            patterns = {}

            for day_idx in daily_stats.index:
                patterns[day_names[day_idx]] = {
                    "session_count": int(daily_stats.loc[day_idx, "count"]),
                    "avg_power": float(daily_stats.loc[day_idx, "mean"]),
                    "max_power": float(daily_stats.loc[day_idx, "max"]),
                }

            return patterns

        except Exception as e:
            self.logger.error(f"Error analyzing daily patterns: {e}")
            return {}

    def aggregate_hourly_features(self, df: pd.DataFrame) -> pd.DataFrame:
        
        if df.empty:
            return df

        try:
            if "충전시작일시" not in df.columns:
                return df

            df_hourly = df.copy()
            df_hourly["충전시작일시"] = pd.to_datetime(df_hourly["충전시작일시"], errors="coerce")
            df_hourly = df_hourly.dropna(subset=["충전시작일시"])

            if df_hourly.empty:
                return df

            df_hourly["hour"] = df_hourly["충전시작일시"].dt.hour

            # 시간대별 집계
            numeric_cols = df_hourly.select_dtypes(include=[np.number]).columns
            hourly_features = df_hourly.groupby("hour")[numeric_cols].agg(["mean", "max", "count"]).reset_index()

            return hourly_features

        except Exception as e:
            self.logger.error(f"Error in hourly aggregation: {e}")
            return df

    def aggregate_daily_features(self, df: pd.DataFrame) -> pd.DataFrame:
        
        if df.empty:
            return df

        try:
            if "충전시작일시" not in df.columns:
                return df

            df_daily = df.copy()
            df_daily["충전시작일시"] = pd.to_datetime(df_daily["충전시작일시"], errors="coerce")
            df_daily = df_daily.dropna(subset=["충전시작일시"])

            if df_daily.empty:
                return df

            df_daily["date"] = df_daily["충전시작일시"].dt.date

            # 일별 집계
            numeric_cols = df_daily.select_dtypes(include=[np.number]).columns
            daily_features = df_daily.groupby("date")[numeric_cols].agg(["sum", "mean", "max", "count"]).reset_index()

            return daily_features

        except Exception as e:
            self.logger.error(f"Error in daily aggregation: {e}")
            return df

    def calculate_concurrency_stats(self, df: pd.DataFrame) -> Dict:
        
        if df.empty or "충전시작일시" not in df.columns or "충전종료일시" not in df.columns:
            return {}

        try:
            df_time = df.copy()
            df_time["충전시작일시"] = pd.to_datetime(df_time["충전시작일시"], errors="coerce")
            df_time["충전종료일시"] = pd.to_datetime(df_time["충전종료일시"], errors="coerce")
            df_time = df_time.dropna(subset=["충전시작일시", "충전종료일시"])

            if df_time.empty:
                return {}

            # 동시 충전 분석은 복잡하므로 기본 통계만 제공
            total_sessions = len(df_time)
            avg_duration = (df_time["충전종료일시"] - df_time["충전시작일시"]).dt.total_seconds().mean() / 3600  # hours

            return {
                "total_sessions": total_sessions,
                "avg_session_duration_hours": round(avg_duration, 2),
                "concurrent_analysis": "Basic statistics only",
            }

        except Exception as e:
            self.logger.error(f"Error calculating concurrency stats: {e}")
            return {}
