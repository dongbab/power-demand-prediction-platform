from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from pathlib import Path

MARKER_CANDIDATES = [".active_csv", ".active_csv.csv"]


class ChargingDataLoader:
    def __init__(self, station_id: str, data_dir: str = None):
        self.station_id = station_id

        if data_dir:
            self.data_dir = Path(data_dir).resolve()
        else:
            repo_dir = (Path(__file__).resolve().parents[3] / "data" / "raw").resolve()  # <repo_root>/data/raw
            legacy_dir = (Path(__file__).resolve().parent / "raw").resolve()  # <backend/app/data>/raw
            repo_dir.mkdir(parents=True, exist_ok=True)

            # 레거시 폴더에만 CSV가 있고 repo_dir 비어있으면 레거시 사용
            try:
                has_repo_csv = any(repo_dir.glob("*.csv"))
                has_legacy_csv = legacy_dir.exists() and any(legacy_dir.glob("*.csv"))
                self.data_dir = legacy_dir if (has_legacy_csv and not has_repo_csv) else repo_dir
            except Exception:
                self.data_dir = repo_dir

        self.data_dir.mkdir(parents=True, exist_ok=True)
        print(f"데이터 디렉토리: {self.data_dir.absolute()}")

    def _is_marker(self, p: Path) -> bool:
        return p.name in MARKER_CANDIDATES

    def get_active_csv_file(self) -> Optional[Path]:
        """활성 CSV 선택: .active_csv(.csv) 파일(파일명만 허용)"""
        for marker_name in MARKER_CANDIDATES:
            marker = self.data_dir / marker_name
            if marker.exists():
                try:
                    # 다양한 인코딩으로 마커 파일 읽기 시도
                    for encoding in ["utf-8", "cp949", "euc-kr", "utf-8-sig"]:
                        try:
                            first_line = marker.read_text(encoding=encoding).splitlines()[0].strip()
                            if first_line:
                                p = (self.data_dir / Path(first_line).name).resolve()
                                if p.exists():
                                    return p
                            break  # 성공하면 다른 인코딩 시도하지 않음
                        except (UnicodeDecodeError, UnicodeError):
                            continue
                except Exception:
                    continue
        return None

    def get_latest_csv_file(self) -> Optional[Path]:
        """수정시간 기준 최신 CSV 파일 반환"""
        files = self.find_csv_files()
        if not files:
            return None
        files_sorted = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
        return files_sorted[0]

    def find_csv_files(self) -> List[Path]:
        """사용 가능한 CSV 파일들 찾기(마커 파일 제외)"""
        csv_files = []
        patterns = [
            "충전이력*.csv",
            "charging_sessions*.csv",
            "sessions*.csv",
            "*sessions*.csv",
            "*.csv",
        ]
        for pattern in patterns:
            files = list(self.data_dir.glob(pattern))
            # 마커 제외
            files = [f for f in files if not self._is_marker(f)]
            csv_files.extend(files)
            if files:
                print(f"패턴 '{pattern}'으로 발견된 파일: {len(files)}개")
                break

        csv_files = list(set(csv_files))
        try:
            csv_files = sorted(csv_files, key=lambda f: f.stat().st_mtime, reverse=True)
        except Exception:
            pass

        if csv_files:
            print("발견된 CSV 파일들:")
            for i, file in enumerate(csv_files):
                file_size = file.stat().st_size / (1024 * 1024)
                print(f"  {i + 1}. {file.name} ({file_size:.1f}MB)")
        else:
            print(f"CSV 파일을 찾을 수 없습니다. 검색 경로: {self.data_dir}")

        return csv_files

    def load_csv_file(self, csv_file: Path = None, encoding: str = "utf-8", max_rows: int = None) -> pd.DataFrame:
        """지정된 CSV 파일 로드 (인코딩 자동 감지) - 메모리 효율성 개선"""
        if csv_file is None:
            # 활성 파일 > 최신 파일 순서로 선택 (항상 data/raw 내부)
            csv_file = self.get_active_csv_file() or self.get_latest_csv_file()
            if not csv_file:
                print("로드할 CSV 파일이 없습니다.")
                return pd.DataFrame()
            print(f"자동 선택된 최신/활성 파일: {csv_file.name}")

        # data/raw 내부 강제
        csv_file = (self.data_dir / Path(csv_file).name).resolve()
        if not csv_file.exists():
            print(f"파일을 찾을 수 없습니다: {csv_file}")
            return pd.DataFrame()

        # 파일 크기 체크
        file_size_mb = csv_file.stat().st_size / (1024 * 1024)
        if file_size_mb > 500:  # 500MB 이상
            print(f"⚠️ 대용량 파일 ({file_size_mb:.1f}MB) - 샘플링 모드로 로드")
            max_rows = max_rows or 50000  # 5만개 행 제한

        print(f"CSV 파일 로딩 시작: {csv_file.name}")

        # 다양한 인코딩 시도
        encodings = [encoding, "utf-8", "euc-kr", "cp949", "utf-8-sig"]

        for enc in encodings:
            try:
                print(f"인코딩 '{enc}' 시도 중...")

                # 먼저 샘플로 테스트
                sample_df = pd.read_csv(csv_file, nrows=5, encoding=enc)
                print(f"  샘플 로드 성공 - 컬럼 수: {len(sample_df.columns)}")

                # 전체 데이터 로드 (메모리 효율성을 위해 청크 읽기)
                if max_rows and file_size_mb > 100:
                    # 대용량 파일은 청크로 읽기
                    chunks = []
                    for chunk in pd.read_csv(csv_file, dtype=str, low_memory=True, encoding=enc, chunksize=10000):
                        chunks.append(chunk)
                        if len(pd.concat(chunks, ignore_index=True)) >= max_rows:
                            break
                    df = pd.concat(chunks, ignore_index=True)[:max_rows]
                else:
                    df = pd.read_csv(csv_file, dtype=str, low_memory=True, encoding=enc, nrows=max_rows)

                print(f"  전체 로드 성공: {len(df):,}개 행, {len(df.columns)}개 컬럼")
                return df

            except UnicodeDecodeError:
                print(f"  인코딩 '{enc}' 실패")
                continue
            except Exception as e:
                print(f"  인코딩 '{enc}'에서 오류 발생: {e}")
                continue

        print("모든 인코딩 시도 실패")
        return pd.DataFrame()

    def load_historical_sessions(self, days: int = 90, csv_file: str = None, merge_all: bool = False) -> pd.DataFrame:
        """개선된 히스토리 세션 로드"""

        # CSV 파일 지정
        if csv_file:
            target_file = (self.data_dir / Path(csv_file).name).resolve()
            df = self.load_csv_file(target_file)
        else:
            csv_files = self.find_csv_files()
            if not csv_files:
                print("CSV 파일을 찾을 수 없습니다.")
                return pd.DataFrame()
            if merge_all:
                dfs = []
                for f in csv_files:
                    df_i = self.load_csv_file((self.data_dir / f.name).resolve())
                    if not df_i.empty:
                        dfs.append(df_i)
                if not dfs:
                    print("읽을 수 있는 CSV가 없습니다.")
                    return pd.DataFrame()
                df = pd.concat(dfs, ignore_index=True)
            else:
                # 활성 파일 > 최신 파일 사용
                target_file = self.get_active_csv_file() or self.get_latest_csv_file()
                if target_file is None:
                    print("읽을 수 있는 CSV가 없습니다.")
                    return pd.DataFrame()
                df = self.load_csv_file(target_file)

        try:
            # CSV 파일 로드
            if df.empty:
                print("CSV 파일이 비어있습니다.")
                return pd.DataFrame()

            # 데이터 처리 파이프라인
            df = self._normalize_column_names(df)
            df = self._convert_data_types(df)
            df = self._clean_data(df)

            # 특정 충전소 필터링
            if self.station_id != "ALL":
                df = self._filter_by_station(df)

            # 날짜 필터링
            df = self._filter_by_days(df, days)
            print(f"최종 데이터: {len(df):,}개 세션")

            return df

        except Exception as e:
            print(f"CSV 로딩 중 오류 발생: {e}")
            return pd.DataFrame()

    def _filter_by_station(self, df: pd.DataFrame) -> pd.DataFrame:
        """충전소별 필터링"""
        station_columns = ["충전소ID", "충전소명", "station_id", "station_name"]
        station_col = None

        for col in station_columns:
            if col in df.columns:
                station_col = col
                break

        if station_col:
            original_count = len(df)
            # 디버깅: 실제 데이터에서 고유값 확인 (필터링 전)
            unique_stations = df[station_col].unique()
            print(f"전체 충전소 수: {len(unique_stations)}")
            print(f"사용 가능한 충전소 ID (처음 10개): {list(unique_stations[:10])}")
            
            # 실제 필터링 수행
            df_filtered = df[df[station_col] == self.station_id]
            filtered_count = len(df_filtered)
            print(f"충전소 '{self.station_id}' 필터링: {original_count:,} → {filtered_count:,}개 세션")

            if filtered_count == 0:
                print(f"경고: 충전소 '{self.station_id}'에 대한 데이터가 없습니다.")
                # 유사한 충전소 ID가 있는지 확인
                similar_stations = [sid for sid in unique_stations if self.station_id.lower() in sid.lower() or sid.lower() in self.station_id.lower()]
                if similar_stations:
                    print(f"유사한 충전소 ID 발견: {similar_stations}")
                
                # 공백이나 특수문자 문제 확인
                station_id_variants = df[station_col].str.strip().unique()
                if self.station_id.strip() in station_id_variants:
                    print(f"공백 문제 감지: 원본='{self.station_id}', 공백제거 후 재시도")
                    df_filtered = df[df[station_col].str.strip() == self.station_id.strip()]
                    print(f"공백 제거 후 결과: {len(df_filtered)}개 세션")
            
            return df_filtered
        else:
            print("경고: 충전소 ID 컬럼을 찾을 수 없습니다.")
            print(f"사용 가능한 컬럼: {list(df.columns)}")
            return df


    def list_available_files(self) -> Dict:
        """사용 가능한 CSV 파일 목록과 정보 반환"""
        csv_files = self.find_csv_files()

        active = self.get_active_csv_file() or (csv_files[0] if csv_files else None)
        file_info = []
        for file in csv_files:
            try:
                # 파일 기본 정보
                stat = file.stat()
                info = {
                    "filename": file.name,
                    "path": str(file.absolute()),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }

                # CSV 구조 정보 (처음 5행만 읽어서)
                try:
                    sample_df = pd.read_csv(file, nrows=5)
                    info["columns"] = len(sample_df.columns)
                    info["sample_columns"] = list(sample_df.columns)[:10]  # 처음 10개 컬럼만
                except Exception:
                    info["columns"] = "unknown"
                    info["sample_columns"] = []

                file_info.append(info)

            except Exception as e:
                file_info.append({"filename": file.name, "error": str(e)})

        return {
            "data_directory": str(self.data_dir.absolute()),
            "total_files": len(csv_files),
            "files": file_info,
            "active_file": ({"filename": active.name, "path": str(active.absolute())} if active else None),
        }

    # 기존 메서드들은 그대로 유지 (_normalize_column_names, _convert_data_types, etc.)
    def _normalize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """컬럼명 정규화"""
        print("컬럼명 정규화 중...")

        # 컬럼명 공백 제거 및 정리
        df.columns = df.columns.str.strip()

        # 원본 컬럼명 출력 (처음 20개만)
        print(f"컬럼명 ({len(df.columns)}개):")
        for i, col in enumerate(df.columns[:20]):
            print(f"  {i:2d}: '{col}'")
        if len(df.columns) > 20:
            print(f"  ... (총 {len(df.columns)}개)")

        return df

    def _convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터 타입 변환 (안전한 방식)"""
        print("데이터 타입 변환 중...")

        # 날짜 컬럼 찾기 및 변환
        date_patterns = ["일시", "date", "time", "시간"]
        date_columns = [col for col in df.columns if any(pattern in col for pattern in date_patterns)]

        for col in date_columns:
            try:
                # 먼저 샘플 데이터를 확인하여 형식을 추론
                sample_data = df[col].dropna().head(10)
                if len(sample_data) > 0:
                    # 일반적인 한국 날짜 형식들을 시도
                    date_formats = [
                        "%Y-%m-%d %H:%M:%S",  # ISO format
                        "%Y-%m-%d %H:%M:%S.%f",  # ISO with microseconds
                        "%Y/%m/%d %H:%M:%S",  # Slash separated
                        "%d/%m/%Y %H:%M:%S",  # Day first
                        "mixed",  # Let pandas infer but with proper handling
                    ]

                    parsed_successfully = False
                    for fmt in date_formats:
                        try:
                            if fmt == "mixed":
                                # Use pandas default inference for mixed formats
                                df[col] = pd.to_datetime(df[col], errors="coerce")
                            else:
                                df[col] = pd.to_datetime(df[col], format=fmt, errors="coerce")

                            # Check if parsing was successful
                            if df[col].notna().sum() > 0:
                                parsed_successfully = True
                                break
                        except Exception:
                            continue

                    if not parsed_successfully:
                        # Fallback to pandas default
                        df[col] = pd.to_datetime(df[col], errors="coerce")
                else:
                    df[col] = pd.to_datetime(df[col], errors="coerce")

                valid_dates = df[col].notna().sum()
                print(f"  {col}: {valid_dates:,}개 유효한 날짜")
            except Exception as e:
                print(f"  {col} 날짜 변환 실패: {e}")

        # 숫자 컬럼 찾기 및 변환 (전력 관련 컬럼 우선 처리)
        numeric_patterns = ["전력", "전압", "전류", "kWh", "SOC", "시간", "금액", "량"]
        numeric_columns = [col for col in df.columns if any(pattern in col for pattern in numeric_patterns)]

        for col in numeric_columns:
            try:
                # 문자열에서 숫자가 아닌 문자 제거 (쉼표, 공백 등)
                df[col] = df[col].astype(str).str.replace(",", "", regex=False)
                df[col] = df[col].str.replace(" ", "", regex=False)  # 공백 제거
                df[col] = pd.to_numeric(df[col], errors="coerce")
                valid_numbers = df[col].notna().sum()
                print(f"  {col}: {valid_numbers:,}개 유효한 숫자")
                
                # 전력 데이터 범위 확인
                if "전력" in col:
                    power_data = df[col].dropna()
                    if not power_data.empty:
                        print(f"    전력 범위: {power_data.min():.1f} ~ {power_data.max():.1f}kW (평균: {power_data.mean():.1f}kW)")
                        
            except Exception as e:
                print(f"  {col} 숫자 변환 실패: {e}")

        return df

    def _filter_by_days(self, df: pd.DataFrame, days: int) -> pd.DataFrame:
        """최근 N일 데이터 필터링"""
        date_columns = [col for col in df.columns if "시작일시" in col or "start" in col.lower()]

        if not date_columns:
            print("날짜 필터링 불가: 적절한 날짜 컬럼을 찾을 수 없음")
            return df

        date_col = date_columns[0]

        if df[date_col].isna().all():
            print(f"날짜 필터링 불가: {date_col} 컬럼의 모든 값이 null")
            return df

        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            original_count = len(df)
            df = df[df[date_col] >= cutoff_date]
            print(f"날짜 필터링: {original_count:,} → {len(df):,}개 ({cutoff_date.date()} 이후)")
            return df
        except Exception as e:
            print(f"날짜 필터링 중 오류: {e}")
            return df

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터 정제"""
        print("데이터 정제 중...")
        original_size = len(df)

        # 전력 컬럼 찾기
        power_columns = [col for col in df.columns if "전력" in col]
        if power_columns:
            power_col = power_columns[0]
            before = len(df)
            df = df[(df[power_col] > 0) & (df[power_col] < 1000)]
            removed = before - len(df)
            if removed > 0:
                print(f"  {power_col} 이상치 제거: {removed:,}개 행")

        retention_rate = (len(df) / original_size * 100) if original_size > 0 else 0
        print(f"데이터 정제 완료: {original_size:,} → {len(df):,}개 ({retention_rate:.1f}% 보존)")
        return df

    # 기존 다른 메서드들도 그대로 유지...
    def load_realtime_status(self) -> Dict:
        return {
            "station_id": self.station_id,
            "active_chargers": 2,
            "total_chargers": 4,
            "current_power_usage": 85.3,
            "charger_status": {
                "CHG_01": {"status": "charging", "power": 42.1},
                "CHG_02": {"status": "charging", "power": 43.2},
                "CHG_03": {"status": "idle", "power": 0.0},
                "CHG_04": {"status": "maintenance", "power": 0.0},
            },
            "timestamp": datetime.now().isoformat(),
        }

    def load_external_factors(self) -> Dict:
        """외부 요인 로드"""
        current_date = datetime.now()

        holidays = [
            "2025-01-01",
            "2025-03-01",
            "2025-05-05",
            "2025-06-06",
            "2025-08-15",
            "2025-10-03",
            "2025-12-25",
        ]
        is_holiday = current_date.strftime("%Y-%m-%d") in holidays

        return {
            "date": current_date.date().isoformat(),
            "is_holiday": is_holiday,
            "is_weekend": current_date.weekday() >= 5,
            "season": self._get_season(current_date.month),
            "weather": {
                "temperature": np.random.uniform(-5, 35),
                "condition": np.random.choice(["맑음", "흐림", "비", "눈"]),
            },
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
                "unique_chargers": None,
                "data_source": "CSV file" if len(df) > 100 else "Sample data",
            }

            # 날짜 범위 (날짜 컬럼 자동 탐지)
            date_columns = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
            if date_columns:
                date_col = date_columns[0]
                summary["date_range"] = {
                    "start": df[date_col].min().isoformat() if pd.notna(df[date_col].min()) else None,
                    "end": df[date_col].max().isoformat() if pd.notna(df[date_col].max()) else None,
                }

            # 전력 통계 (전력 컬럼 자동 탐지)
            power_columns = [col for col in df.columns if "전력" in col]
            if power_columns:
                power_col = power_columns[0]
                power_data = df[power_col].dropna()
                if not power_data.empty:
                    summary["power_stats"] = {
                        "mean": round(power_data.mean(), 2),
                        "max": round(power_data.max(), 2),
                        "min": round(power_data.min(), 2),
                        "std": round(power_data.std(), 2),
                        "count": len(power_data),
                    }

            # 고유값 개수 (ID 컬럼 자동 탐지)
            id_columns = [col for col in df.columns if "ID" in col or "id" in col]
            for col in id_columns:
                if "충전소" in col:
                    summary["unique_stations"] = df[col].nunique()
                elif "충전기" in col:
                    summary["unique_chargers"] = df[col].nunique()

            return summary

        except Exception as e:
            return {"error": f"데이터 요약 생성 실패: {str(e)}"}

    def analyze_charging_patterns(self) -> Dict:
        """충전 패턴 분석 (개선된 버전)"""
        try:
            # 차트와 패턴 분석을 위해 전체 데이터를 로드 (1년치)
            df = self.load_historical_sessions(365)
            if df.empty:
                return {"error": "분석할 데이터가 없습니다"}
            analysis = {
                "data_info": {
                    "total_sessions": len(df),
                    "columns": list(df.columns),
                    "station_id": self.station_id,
                }
            }

            # 전력 통계 (전력 컬럼 자동 탐지)
            power_columns = [col for col in df.columns if "전력" in col]
            if power_columns:
                power_col = power_columns[0]
                power_data = df[power_col].dropna()
                if not power_data.empty:
                    power_stats = power_data.describe()
                    analysis["power_statistics"] = {
                        "column_name": power_col,
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

            # 시간대별 패턴 (날짜 컬럼 자동 탐지)
            date_columns = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
            if date_columns and power_columns:
                date_col = date_columns[0]
                power_col = power_columns[0]

                try:
                    df["hour"] = df[date_col].dt.hour
                    hourly_stats = df.groupby("hour")[power_col].agg(["mean", "max", "count"]).round(2)

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

            # 월별 패턴 생성 (차트 데이터용)
            if date_columns and power_columns:
                try:
                    date_col = date_columns[0]
                    power_col = power_columns[0]
                    
                    # 년-월 조합으로 그룹핑 (정확한 시계열 데이터)
                    df["year_month"] = df[date_col].dt.strftime("%Y-%m")
                    monthly_stats = df.groupby("year_month")[power_col].agg(["mean", "max", "count"]).round(2)
                    
                    if not monthly_stats.empty:
                        analysis["monthly_patterns"] = {
                            year_month: {
                                "avg_power": float(row["mean"]) if pd.notna(row["mean"]) else 0,
                                "max_power": float(row["max"]) if pd.notna(row["max"]) else 0,
                                "session_count": int(row["count"]),
                            }
                            for year_month, row in monthly_stats.iterrows()
                        }
                        
                    # 날짜 범위 정보 추가
                    analysis["date_range"] = {
                        "start": df[date_col].min(),
                        "end": df[date_col].max()
                    }
                    
                except Exception as e:
                    print(f"월별 패턴 분석 오류: {e}")

            return analysis
        except Exception as e:
            return {"error": f"패턴 분석 실패: {str(e)}"}


def test_enhanced_loader():
    # 1. 사용 가능한 파일 목록
    loader = ChargingDataLoader("BNS0791")
    print("1. 사용 가능한 CSV 파일:")
    file_info = loader.list_available_files()
    print(f"   데이터 디렉토리: {file_info['data_directory']}")
    print(f"   총 {file_info['total_files']}개 파일 발견")

    for file in file_info["files"]:
        if "error" not in file:
            print(f"   - {file['filename']} ({file['size_mb']}MB, {file['columns']}개 컬럼)")

    # 2. 데이터 로드 및 요약
    print("\n2. 데이터 로드 및 요약:")
    summary = loader.get_data_summary()
    print(f"   총 세션: {summary.get('total_sessions', 0):,}개")
    print(f"   데이터 소스: {summary.get('data_source', 'unknown')}")

    if "power_stats" in summary and summary["power_stats"]:
        stats = summary["power_stats"]
        print(f"   전력 통계: 평균 {stats['mean']}kW, 최대 {stats['max']}kW")

    # 3. 패턴 분석
    print("\n3. 충전 패턴 분석:")
    patterns = loader.analyze_charging_patterns()
    if "power_statistics" in patterns:
        stats = patterns["power_statistics"]
        print(f"   전력 분석 ({stats['column_name']}): 평균 {stats['mean']}kW, 95% {stats['percentile_95']}kW")

    if "peak_hour" in patterns:
        peak = patterns["peak_hour"]
        print(f"   피크 시간: {peak['hour']}시 (평균 {peak['avg_power']}kW)")


if __name__ == "__main__":
    test_enhanced_loader()
