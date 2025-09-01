import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class ChargingDataValidator:
    def __init__(self):
        self.required_columns = ["충전시작일시", "충전소ID", "순간최고전력"]
        self.optional_columns = [
            "충전종료일시",
            "충전량(kWh)",
            "시작SOC(%)",
            "완료SOC(%)",
            "충전시간",
            "충전기ID",
            "충전소명",
            "충전소주소",
        ]

    def validate_schema(self, df: pd.DataFrame) -> Dict[str, Any]:
        report = {
            "is_valid": True,
            "missing_required": [],
            "missing_optional": [],
            "total_columns": len(df.columns),
            "total_rows": len(df),
        }

        # Check required columns
        for col in self.required_columns:
            if col not in df.columns:
                report["missing_required"].append(col)
                report["is_valid"] = False

        # Check optional columns
        for col in self.optional_columns:
            if col not in df.columns:
                report["missing_optional"].append(col)

        return report

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df_clean = df.copy()

        # Convert data types
        df_clean = self._convert_data_types(df_clean)

        # Remove invalid records
        df_clean = self._remove_invalid_records(df_clean)

        # Handle outliers
        df_clean = self._handle_outliers(df_clean)

        # Fill missing values
        df_clean = self._fill_missing_values(df_clean)

        return df_clean

    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Date columns
        date_columns = ["충전시작일시", "충전종료일시"]
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # Numeric columns
        numeric_columns = [
            "순간최고전력",
            "충전량(kWh)",
            "시작SOC(%)",
            "완료SOC(%)",
            "순간최고전압",
            "순간최고전류",
            "충전시간",
            "충전금액",
        ]

        for col in numeric_columns:
            if col in df.columns:
                # Clean numeric strings
                if df[col].dtype == "object":
                    df[col] = (
                        df[col].astype(str).str.replace(",", "").str.replace(" ", "")
                    )
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def _remove_invalid_records(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        original_count = len(df)

        # Remove records with missing essential data
        essential_columns = ["충전시작일시", "순간최고전력"]
        for col in essential_columns:
            if col in df.columns:
                df = df.dropna(subset=[col])

        # Remove records with invalid power values
        if "순간최고전력" in df.columns:
            df = df[
                (df["순간최고전력"] > 0) & (df["순간최고전력"] <= 1000)
            ]  # Reasonable upper bound

        # Remove records with invalid SOC values
        soc_columns = ["시작SOC(%)", "완료SOC(%)"]
        for col in soc_columns:
            if col in df.columns:
                df = df[(df[col].isna()) | ((df[col] >= 0) & (df[col] <= 100))]

        # Remove records with invalid date ranges
        if "충전시작일시" in df.columns and "충전종료일시" in df.columns:
            valid_dates = (
                (df["충전시작일시"].notna())
                & (df["충전종료일시"].notna())
                & (df["충전시작일시"] <= df["충전종료일시"])
            )
            df = df[valid_dates | df["충전종료일시"].isna()]

        removed_count = original_count - len(df)
        if removed_count > 0:
            print(
                f"데이터 정제: {removed_count:,}개 행 제거 ({removed_count / original_count * 100:.1f}%)"
            )

        return df

    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        outlier_columns = ["순간최고전력", "충전량(kWh)"]

        for col in outlier_columns:
            if col in df.columns and df[col].notna().sum() > 0:
                # Use 1st and 99th percentiles for winsorization
                lower_bound = df[col].quantile(0.01)
                upper_bound = df[col].quantile(0.99)

                original_outliers = (
                    (df[col] < lower_bound) | (df[col] > upper_bound)
                ).sum()

                df[col] = df[col].clip(lower_bound, upper_bound)

                if original_outliers > 0:
                    print(f"{col} 이상치 조정: {original_outliers}개")

        return df

    def _fill_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Fill missing charging time based on start/end times
        if (
            ("충전시간" not in df.columns or df["충전시간"].isna().all())
            and "충전시작일시" in df.columns
            and "충전종료일시" in df.columns
        ):
            time_diff = (
                df["충전종료일시"] - df["충전시작일시"]
            ).dt.total_seconds() / 60
            df["충전시간"] = df.get("충전시간", time_diff).fillna(time_diff)

        # Fill missing energy based on power and time
        if (
            ("충전량(kWh)" not in df.columns or df["충전량(kWh)"].isna().any())
            and "순간최고전력" in df.columns
            and "충전시간" in df.columns
        ):
            estimated_energy = df["순간최고전력"] * df["충전시간"] / 60  # kWh
            df["충전량(kWh)"] = df.get("충전량(kWh)", estimated_energy).fillna(
                estimated_energy
            )

        return df

    def get_data_quality_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty:
            return {"error": "No data to analyze"}

        report = {
            "total_records": len(df),
            "date_range": self._get_date_range(df),
            "completeness": self._calculate_completeness(df),
            "power_statistics": self._get_power_statistics(df),
            "data_issues": self._identify_data_issues(df),
        }

        return report

    def _get_date_range(self, df: pd.DataFrame) -> Dict[str, str]:
        if "충전시작일시" not in df.columns:
            return {"start": None, "end": None}

        start_date = df["충전시작일시"].min()
        end_date = df["충전시작일시"].max()

        return {
            "start": start_date.isoformat() if pd.notna(start_date) else None,
            "end": end_date.isoformat() if pd.notna(end_date) else None,
        }

    def _calculate_completeness(self, df: pd.DataFrame) -> Dict[str, float]:
        completeness = {}

        for col in df.columns:
            completeness[col] = (df[col].notna().sum() / len(df)) * 100

        return completeness

    def _get_power_statistics(self, df: pd.DataFrame) -> Dict[str, float]:
        if "순간최고전력" not in df.columns:
            return {}

        power_data = df["순간최고전력"].dropna()

        if power_data.empty:
            return {}

        return {
            "count": len(power_data),
            "mean": round(power_data.mean(), 2),
            "std": round(power_data.std(), 2),
            "min": round(power_data.min(), 2),
            "max": round(power_data.max(), 2),
            "p50": round(power_data.quantile(0.5), 2),
            "p95": round(power_data.quantile(0.95), 2),
            "p99": round(power_data.quantile(0.99), 2),
        }

    def _identify_data_issues(self, df: pd.DataFrame) -> List[str]:
        issues = []

        # Check for missing essential data
        for col in self.required_columns:
            if col not in df.columns:
                issues.append(f"Missing required column: {col}")
            elif df[col].isna().sum() > 0:
                missing_pct = (df[col].isna().sum() / len(df)) * 100
                issues.append(f"{col} has {missing_pct:.1f}% missing values")

        # Check for suspicious power values
        if "순간최고전력" in df.columns:
            zero_power = (df["순간최고전력"] == 0).sum()
            if zero_power > 0:
                issues.append(f"{zero_power} records with zero power")

            high_power = (df["순간최고전력"] > 200).sum()
            if high_power > 0:
                issues.append(
                    f"{high_power} records with unusually high power (>200kW)"
                )

        # Check date consistency
        if "충전시작일시" in df.columns and "충전종료일시" in df.columns:
            invalid_dates = (df["충전시작일시"] > df["충전종료일시"]).sum()
            if invalid_dates > 0:
                issues.append(f"{invalid_dates} records with invalid date ranges")

        return issues
