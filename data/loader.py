from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime, timedelta
import os
import numpy as np


class ChargingDataLoader:
    def __init__(self, station_id: str):
        self.station_id = station_id

    def load_historical_sessions(self, days: int = 90) -> pd.DataFrame:
        csv_file = "충전이력리스트_급속_202409_202505.csv"

        if os.path.exists(csv_file):
            print(f"데이터 파일 로딩: {csv_file}")
            
            try:
                # 1단계: 먼저 dtype 없이 로드해서 구조 파악
                print("파일 구조 분석 중...")
                sample_df = pd.read_csv(csv_file, nrows=5)
                print(f"컬럼 정보: {list(sample_df.columns)}")
                print(f"첫 번째 행 샘플:")
                print(sample_df.iloc[0].to_dict())

                # 2단계: 전체 데이터를 string으로 먼저 로드
                print("전체 데이터 로딩...")
                df = pd.read_csv(csv_file, dtype=str, low_memory=False)
                print(f"전체 데이터 로드: {len(df):,}개 세션")
                
                # 3단계: 데이터 타입 변환 및 정규화
                df = self._normalize_column_names(df)
                df = self._convert_data_types(df)
                df = self._clean_data(df)

                # 특정 충전소 필터링 (필요시)
                if self.station_id != "ALL":
                    if '충전소ID' in df.columns:
                        original_count = len(df)
                        df = df[df["충전소ID"] == self.station_id]
                        print(f"충전소 {self.station_id} 필터링: {original_count:,} → {len(df):,}개 세션")
                    else:
                        print("경고: '충전소ID' 컬럼을 찾을 수 없습니다.")

                # 날짜 필터링
                df = self._filter_by_days(df, days)
                print(f"최근 {days}일 필터링 후: {len(df):,}개 세션")

                return df
                
            except Exception as e:
                print(f"CSV 로딩 중 오류 발생: {e}")
                print("샘플 데이터를 생성합니다...")
                return self._generate_sample_data(days)
        else:
            print(f"파일을 찾을 수 없습니다: {csv_file}")
            return self._generate_sample_data(days)

    def _normalize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """컬럼명 정규화"""
        print("컬럼명 정규화 중...")
        
        # 컬럼명 공백 제거 및 정리
        df.columns = df.columns.str.strip()
        
        # 원본 컬럼명 출력
        print(f"원본 컬럼명 ({len(df.columns)}개):")
        for i, col in enumerate(df.columns):
            print(f"  {i:2d}: '{col}'")
        
        # 필수 컬럼 확인
        required_columns = ['충전시작일시', '충전종료일시', '순간최고전력']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"경고: 누락된 필수 컬럼: {missing_columns}")
            
            # 유사한 컬럼명 찾기 시도
            for missing_col in missing_columns:
                similar_cols = [col for col in df.columns if missing_col[:3] in col]
                if similar_cols:
                    print(f"  '{missing_col}'와 유사한 컬럼: {similar_cols}")
        
        return df

    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터 타입 변환 (안전한 방식)"""
        print("데이터 타입 변환 중...")
        
        # 날짜 컬럼 변환
        date_columns = ['충전시작일시', '충전종료일시']
        for col in date_columns:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    valid_dates = df[col].notna().sum()
                    print(f"  {col}: {valid_dates:,}개 유효한 날짜")
                except Exception as e:
                    print(f"  {col} 날짜 변환 실패: {e}")

        # 숫자 컬럼 변환 (안전한 방식)
        numeric_columns = [
            '순간최고전력', '충전량(kWh)', '시작SOC(%)', '완료SOC(%)', 
            '순간최고전압', '순간최고전류', '충전시간', '충전금액'
        ]
        
        for col in numeric_columns:
            if col in df.columns:
                try:
                    # 문자열에서 숫자가 아닌 문자 제거
                    df[col] = df[col].astype(str).str.replace(',', '')  # 쉼표 제거
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    valid_numbers = df[col].notna().sum()
                    print(f"  {col}: {valid_numbers:,}개 유효한 숫자")
                except Exception as e:
                    print(f"  {col} 숫자 변환 실패: {e}")

        return df

    def _filter_by_days(self, df: pd.DataFrame, days: int) -> pd.DataFrame:
        """최근 N일 데이터 필터링"""
        if '충전시작일시' not in df.columns or df['충전시작일시'].isna().all():
            print("날짜 필터링 불가: 충전시작일시 컬럼이 없거나 모든 값이 null")
            return df
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            original_count = len(df)
            df = df[df['충전시작일시'] >= cutoff_date]
            print(f"날짜 필터링: {original_count:,} → {len(df):,}개 ({cutoff_date.date()} 이후)")
            return df
        except Exception as e:
            print(f"날짜 필터링 중 오류: {e}")
            return df

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        print("데이터 정제 중...")
        original_size = len(df)

        # 1. 필수 컬럼 결측치 제거
        essential_columns = ["충전시작일시", "충전종료일시", "순간최고전력"]
        for col in essential_columns:
            if col in df.columns:
                before = len(df)
                df = df.dropna(subset=[col])
                removed = before - len(df)
                if removed > 0:
                    print(f"  {col} 결측치 제거: {removed:,}개 행")

        # 2. 순간최고전력 이상치 제거
        if "순간최고전력" in df.columns:
            before = len(df)
            # 0보다 크고 1000kW 미만 (더 관대한 범위)
            df = df[(df["순간최고전력"] > 0) & (df["순간최고전력"] < 1000)]
            removed = before - len(df)
            if removed > 0:
                print(f"  순간최고전력 이상치 제거: {removed:,}개 행")

        # 3. SOC 범위 검증 (0-100%)
        soc_columns = ["시작SOC(%)", "완료SOC(%)"]
        for col in soc_columns:
            if col in df.columns:
                before = len(df)
                df = df[(df[col] >= 0) & (df[col] <= 100)]
                removed = before - len(df)
                if removed > 0:
                    print(f"  {col} 범위 오류 제거: {removed:,}개 행")

        retention_rate = (len(df) / original_size * 100) if original_size > 0 else 0
        print(f"데이터 정제 완료: {original_size:,} → {len(df):,}개 ({retention_rate:.1f}% 보존)")
        return df

    # def _generate_sample_data(self, days: int) -> pd.DataFrame:
    #     print(f"샘플 데이터 생성: {days}일간")
        
    #     # 더 현실적인 시간 간격 (2-4시간마다 충전)
    #     end_date = datetime.now()
    #     start_date = end_date - timedelta(days=days)
        
    #     # 랜덤한 시간 간격으로 충전 세션 생성
    #     sessions = []
    #     current_date = start_date
        
    #     while current_date < end_date:
    #         # 2-6시간 간격으로 충전 세션 생성
    #         interval_hours = np.random.uniform(2, 6)
    #         current_date += timedelta(hours=interval_hours)
            
    #         if current_date < end_date:
    #             sessions.append(current_date)
        
    #     n_sessions = len(sessions)
    #     print(f"생성된 세션 수: {n_sessions}개")

    #     # 시간대별 전력 패턴 적용
    #     base_power = []
    #     for dt in sessions:
    #         hour = dt.hour
    #         if 0 <= hour < 6:    # 심야
    #             base = 25
    #         elif 6 <= hour < 9:  # 출근시간
    #             base = 45
    #         elif 9 <= hour < 12: # 오전
    #             base = 35
    #         elif 12 <= hour < 14: # 점심
    #             base = 40
    #         elif 14 <= hour < 18: # 오후
    #             base = 38
    #         elif 18 <= hour < 21: # 퇴근시간
    #             base = 50
    #         else:                # 저녁
    #             base = 35
            
    #         # 랜덤 변동 추가 (±30%)
    #         power = np.random.normal(base, base * 0.3)
    #         base_power.append(max(10, min(100, power)))

    #     sample_data = {
    #         '권역': ['수도권'] * n_sessions,
    #         '시군구': ['서울시'] * n_sessions,
    #         '충전소ID': [self.station_id] * n_sessions,
    #         '충전소명': [f'{self.station_id}_충전소'] * n_sessions,
    #         '충전소주소': ['서울시 강남구 테헤란로 123'] * n_sessions,
    #         '운영사명': ['한국전력공사'] * n_sessions,
    #         '충전기ID': [f'CHG_{i%4+1:02d}' for i in range(n_sessions)],
    #         '충전기구분': ['급속'] * n_sessions,
    #         '커넥터명': ['DC콤보'] * n_sessions,
    #         '충전시작일시': sessions,
    #         '충전종료일시': [dt + timedelta(minutes=np.random.uniform(30, 120)) for dt in sessions],
    #         '충전시간': np.random.uniform(30, 120, n_sessions),
    #         '개인/법인': np.random.choice(['개인', '법인'], n_sessions, p=[0.7, 0.3]),
    #         '충전량(kWh)': np.random.uniform(15, 60, n_sessions),
    #         '시작SOC(%)': np.random.uniform(10, 70, n_sessions),
    #         '완료SOC(%)': np.random.uniform(60, 95, n_sessions),
    #         '순간최고전력': base_power,
    #         '순간최고전압': np.random.uniform(380, 420, n_sessions),
    #         '순간최고전류': np.random.uniform(50, 150, n_sessions),
    #         '충전단가': [350] * n_sessions,
    #         '충전금액': np.random.uniform(10000, 35000, n_sessions)
    #     }
        
    #     return pd.DataFrame(sample_data)

    def debug_csv_structure(self):
        """CSV 파일 구조 디버깅"""
        csv_file = "충전이력리스트_급속_202409_202505.csv"
        
        if not os.path.exists(csv_file):
            print(f"파일을 찾을 수 없습니다: {csv_file}")
            return
        
        print("=== CSV 파일 구조 분석 ===")
        
        try:
            # 첫 10줄만 읽어서 구조 확인
            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = [f.readline().strip() for _ in range(10)]
            
            print(f"파일 인코딩: UTF-8")
            print(f"첫 10줄:")
            for i, line in enumerate(lines):
                print(f"  {i+1:2d}: {line[:100]}{'...' if len(line) > 100 else ''}")
            
            # pandas로 샘플 읽기
            sample_df = pd.read_csv(csv_file, nrows=3, dtype=str)
            print(f"\nPandas 샘플 읽기 성공")
            print(f"컬럼 수: {len(sample_df.columns)}")
            print(f"행 수: {len(sample_df)}")
            
        except UnicodeDecodeError:
            print("UTF-8 인코딩 실패, EUC-KR 시도...")
            try:
                sample_df = pd.read_csv(csv_file, nrows=3, dtype=str, encoding='euc-kr')
                print("EUC-KR 인코딩 성공")
            except Exception as e:
                print(f"인코딩 오류: {e}")
        except Exception as e:
            print(f"파일 읽기 실패: {e}")

    def load_realtime_status(self) -> Dict:
        return {
            'station_id': self.station_id,
            'active_chargers': 2,
            'total_chargers': 4,
            'current_power_usage': 85.3,
            'charger_status': {
                'CHG_01': {'status': 'charging', 'power': 42.1},
                'CHG_02': {'status': 'charging', 'power': 43.2},
                'CHG_03': {'status': 'idle', 'power': 0.0},
                'CHG_04': {'status': 'maintenance', 'power': 0.0}
            },
            'timestamp': datetime.now().isoformat()
        }

    def load_external_factors(self) -> Dict:
        """외부 요인 로드"""
        current_date = datetime.now()
        
        holidays = [
            '2025-01-01', '2025-03-01', '2025-05-05', 
            '2025-06-06', '2025-08-15', '2025-10-03', '2025-12-25'
        ]
        is_holiday = current_date.strftime('%Y-%m-%d') in holidays
        
        return {
            'date': current_date.date().isoformat(),
            'is_holiday': is_holiday,
            'is_weekend': current_date.weekday() >= 5,
            'season': self._get_season(current_date.month),
            'weather': {
                'temperature': np.random.uniform(-5, 35),
                'condition': np.random.choice(['맑음', '흐림', '비', '눈'])
            }
        }

    def _get_season(self, month: int) -> str:
        """계절 구분"""
        if month in [3, 4, 5]:
            return "봄"
        elif month in [6, 7, 8]:
            return "여름"
        elif month in [9, 10, 11]:
            return "가을"
        else:
            return "겨울"

    def get_data_summary(self) -> Dict:
        """데이터 요약 정보"""
        try:
            df = self.load_historical_sessions()
            
            if df.empty:
                return {"error": "데이터가 없습니다"}
            
            summary = {
                "total_sessions": len(df),
                "columns": list(df.columns),
                "date_range": {},
                "power_stats": {},
                "unique_stations": None,
                "unique_chargers": None
            }
            
            # 날짜 범위
            if '충전시작일시' in df.columns:
                summary["date_range"] = {
                    "start": df['충전시작일시'].min().isoformat() if pd.notna(df['충전시작일시'].min()) else None,
                    "end": df['충전시작일시'].max().isoformat() if pd.notna(df['충전시작일시'].max()) else None
                }
            
            # 전력 통계
            if '순간최고전력' in df.columns:
                power_data = df['순간최고전력'].dropna()
                if not power_data.empty:
                    summary["power_stats"] = {
                        "mean": round(power_data.mean(), 2),
                        "max": round(power_data.max(), 2),
                        "min": round(power_data.min(), 2),
                        "std": round(power_data.std(), 2),
                        "count": len(power_data)
                    }
            
            # 고유값 개수
            if '충전소ID' in df.columns:
                summary["unique_stations"] = df['충전소ID'].nunique()
            if '충전기ID' in df.columns:
                summary["unique_chargers"] = df['충전기ID'].nunique()
            
            return summary
            
        except Exception as e:
            return {"error": f"데이터 요약 생성 실패: {str(e)}"}

    def analyze_charging_patterns(self) -> Dict:
        """충전 패턴 분석 (오류 처리 강화)"""
        try:
            df = self.load_historical_sessions(90)

            if df.empty:
                return {"error": "분석할 데이터가 없습니다"}

            analysis = {"data_info": {"total_sessions": len(df), "columns": list(df.columns)}}

            # 전력 통계
            if "순간최고전력" in df.columns:
                power_data = df["순간최고전력"].dropna()
                if not power_data.empty:
                    power_stats = power_data.describe()
                    analysis["power_statistics"] = {
                        "count": int(power_stats["count"]),
                        "mean": round(power_stats["mean"], 2),
                        "std": round(power_stats["std"], 2),
                        "min": round(power_stats["min"], 2),
                        "max": round(power_stats["max"], 2),
                        "percentile_50": round(power_stats["50%"], 2),
                        "percentile_75": round(power_stats["75%"], 2),
                        "percentile_90": round(power_data.quantile(0.90), 2),
                        "percentile_95": round(power_data.quantile(0.95), 2),
                        "percentile_99": round(power_data.quantile(0.99), 2),
                    }

            # 시간대별 패턴
            if "충전시작일시" in df.columns and not df["충전시작일시"].isna().all():
                try:
                    df["hour"] = df["충전시작일시"].dt.hour
                    hourly_stats = df.groupby("hour")["순간최고전력"].agg(["mean", "max", "count"]).round(2)
                    
                    if not hourly_stats.empty:
                        analysis["hourly_patterns"] = {
                            int(hour): {
                                "avg_power": float(row["mean"]) if pd.notna(row["mean"]) else 0,
                                "max_power": float(row["max"]) if pd.notna(row["max"]) else 0,
                                "session_count": int(row["count"]),
                            }
                            for hour, row in hourly_stats.iterrows()
                        }

                        # 피크 시간대
                        peak_hour_idx = hourly_stats["mean"].idxmax()
                        peak_hour_data = hourly_stats.loc[peak_hour_idx]
                        analysis["peak_hour"] = {
                            "hour": int(peak_hour_idx),
                            "avg_power": float(peak_hour_data["mean"]),
                            "max_power": float(peak_hour_data["max"]),
                        }
                except Exception as e:
                    print(f"시간대별 패턴 분석 오류: {e}")

            return analysis

        except Exception as e:
            return {"error": f"패턴 분석 실패: {str(e)}"}


def test_robust_loader():
    loader = ChargingDataLoader("BNS0791")
    
    # CSV 구조 확인
    print("\n1. CSV 파일 구조 분석:")
    loader.debug_csv_structure()
    
    # 데이터 요약
    print("\n2. 데이터 요약:")
    summary = loader.get_data_summary()
    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    
    # 패턴 분석
    print("\n3. 충전 패턴 분석:")
    patterns = loader.analyze_charging_patterns()
    if "power_statistics" in patterns:
        stats = patterns["power_statistics"]
        print(f"  전력 통계: 평균 {stats['mean']}kW, 최대 {stats['max']}kW")


if __name__ == "__main__":
    test_robust_loader()