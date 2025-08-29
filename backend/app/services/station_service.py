from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from ..data.loader import ChargingDataLoader
from ..features.aggregator import FeatureAggregator


class StationService:
    """충전소 데이터 서비스 - 모든 데이터 처리 중앙화"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._cached_data = {}
        self._cache_timestamp = {}
        self._cache_ttl = 300  # 5분 캐시

    def _is_cache_valid(self, key: str) -> bool:
        """캐시 유효성 검사"""
        if key not in self._cache_timestamp:
            return False
        return (datetime.now() - self._cache_timestamp[key]).total_seconds() < self._cache_ttl

    def _set_cache(self, key: str, data: Any) -> None:
        """캐시 설정"""
        self._cached_data[key] = data
        self._cache_timestamp[key] = datetime.now()

    def _get_cache(self, key: str) -> Optional[Any]:
        """캐시 조회"""
        if self._is_cache_valid(key):
            return self._cached_data.get(key)
        return None

    def clear_cache(self) -> None:
        """모든 캐시 클리어"""
        self._cached_data.clear()
        self._cache_timestamp.clear()

    def _clean_for_json(self, obj: Any) -> Any:
        """JSON 직렬화를 위해 데이터를 정리"""
        if obj is None:
            return None
        elif isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.float64, np.float32)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._clean_for_json(item) for item in obj]
        elif pd.isna(obj):
            return None
        else:
            return obj

    def list_stations(self, search: str = None, sort_by: str = "id", sort_order: str = "asc") -> Dict[str, Any]:
        """충전소 목록 조회 - 완전 처리된 데이터 반환"""
        cache_key = f"stations_{search}_{sort_by}_{sort_order}"
        cached_result = self._get_cache(cache_key)
        if cached_result:
            return cached_result

        try:
            loader = ChargingDataLoader("ALL")
            file_info = loader.list_available_files()

            if file_info["total_files"] == 0:
                return {"success": False, "message": "CSV 파일이 없습니다.", "stations": [], "total": 0}

            # 전체 데이터 로드
            df = loader.load_historical_sessions(days=9999)
            if df.empty:
                return {"success": False, "message": "데이터가 없습니다.", "stations": [], "total": 0}

            # 충전소별 집계 데이터 생성
            stations = self._process_station_list(df, search, sort_by, sort_order)

            result = {
                "success": True,
                "stations": self._clean_for_json(stations),
                "total": len(stations),
                "last_updated": datetime.now().isoformat(),
            }

            self._set_cache(cache_key, result)
            return result

        except Exception as e:
            self.logger.error(f"Error listing stations: {e}", exc_info=True)
            return {"success": False, "error": str(e), "stations": [], "total": 0}

    def _process_station_list(
        self, df: pd.DataFrame, search: str = None, sort_by: str = "id", sort_order: str = "asc"
    ) -> List[Dict[str, Any]]:
        """충전소 목록 데이터 처리"""

        # 충전소 ID 컬럼 찾기
        station_col = self._find_station_column(df)
        if not station_col:
            return []

        # 충전소별 집계 - 모든 충전소 처리 (필요시 페이지네이션으로 제한)
        stations = []
        unique_stations = df[station_col].dropna().unique()

        # 데이터량이 많은 경우 세션 수 기준으로 정렬하여 처리 (상한선 제거)
        if len(unique_stations) > 50:
            station_counts = df[station_col].value_counts()
            unique_stations = station_counts.index.tolist()  # 모든 충전소 포함

        for station_id in unique_stations:
            station_data = df[df[station_col] == station_id].copy()
            if station_data.empty:
                continue

            # 기본 정보
            station_info = {
                "id": str(station_id),
                "name": self._get_station_name(station_data, station_id),
                "location": self._get_station_location(station_data),
                "region": self._get_station_region(station_data),
                "city": self._get_station_city(station_data),
                "charger_type": self._get_charger_type(station_data),
                "connector_type": self._get_connector_type(station_data),
            }

            # 집계된 메트릭 - 백엔드에서 모든 계산 완료
            metrics = self._calculate_station_metrics(station_data)
            station_info.update(metrics)

            # 검색 필터 적용
            if search and not self._matches_search(station_info, search):
                continue

            stations.append(station_info)

        # 정렬
        stations = self._sort_stations(stations, sort_by, sort_order)

        return stations

    def _find_station_column(self, df: pd.DataFrame) -> Optional[str]:
        """충전소 ID 컬럼 찾기"""
        station_id_cols = ["충전소ID", "station_id", "충전소명", "STATION_ID"]
        for col in station_id_cols:
            if col in df.columns:
                return col
        return None

    def _get_station_name(self, station_data: pd.DataFrame, station_id: str) -> str:
        """충전소명 추출"""
        name_cols = ["충전소명", "station_name", "name"]
        for col in name_cols:
            if col in station_data.columns:
                name = station_data[col].iloc[0] if not station_data[col].isna().all() else None
                if name:
                    return str(name)
        return f"충전소 {station_id}"

    def _get_station_location(self, station_data: pd.DataFrame) -> str:
        """위치 정보 추출"""
        location_cols = ["충전소주소", "주소", "location", "위치", "address"]
        for col in location_cols:
            if col in station_data.columns:
                location = station_data[col].iloc[0] if not station_data[col].isna().all() else None
                if location:
                    return str(location)
        return "위치 미상"

    def _get_station_region(self, station_data: pd.DataFrame) -> str:
        """권역 정보 추출"""
        region_cols = ["권역", "region", "시도"]
        for col in region_cols:
            if col in station_data.columns:
                region = station_data[col].iloc[0] if not station_data[col].isna().all() else None
                if region:
                    return str(region)
        return "미상"

    def _get_station_city(self, station_data: pd.DataFrame) -> str:
        """시군구 정보 추출"""
        city_cols = ["시군구", "city", "구", "시"]
        for col in city_cols:
            if col in station_data.columns:
                city = station_data[col].iloc[0] if not station_data[col].isna().all() else None
                if city:
                    return str(city)
        return "미상"

    def _get_charger_type(self, station_data: pd.DataFrame) -> str:
        """충전기 타입 추출"""
        # 전력 기반 추정
        power_cols = ["순간최고전력", "max_power", "전력"]
        for col in power_cols:
            if col in station_data.columns:
                max_power = station_data[col].max()
                if pd.notna(max_power):
                    if max_power >= 50:
                        return "급속충전기 (DC)"
                    else:
                        return "완속충전기 (AC)"
        return "미상"
        
    def _is_fast_charger(self, station_data: pd.DataFrame) -> bool:
        """급속충전기 여부 판단"""
        charger_type = self._get_charger_type(station_data)
        return "급속" in charger_type or "DC" in charger_type
        
    def _get_charger_max_contract(self, station_data: pd.DataFrame) -> int:
        """충전기 타입별 최대 계약전력 반환"""
        if self._is_fast_charger(station_data):
            return 100  # 급속충전기: 100kW
        else:
            return 7    # 완속충전기: 7kW
            
    def _calculate_optimal_contract_power(self, station_data: pd.DataFrame, percentile_95: float) -> dict:
        """실제 데이터를 기반으로 최적 계약전력 계산 - 예측값과 계약권고값 분리"""
        is_fast_charger = self._is_fast_charger(station_data)
        max_limit = self._get_charger_max_contract(station_data)
        
        # 실제 데이터 기반 계산 - 더 정확한 예측을 위해 개선
        if is_fast_charger:
            # 급속충전기: 데이터 품질에 따른 적응형 안전마진
            data_count = len(station_data) if station_data is not None and not station_data.empty else 0
            
            if data_count > 1000:
                # 충분한 데이터: 낮은 안전마진
                safety_margin = 0.12 if percentile_95 > 80 else 0.08
            elif data_count > 500:
                # 보통 데이터: 중간 안전마진
                safety_margin = 0.15 if percentile_95 > 60 else 0.12
            else:
                # 부족한 데이터: 높은 안전마진
                safety_margin = 0.20 if percentile_95 > 60 else 0.15
            
            # 실제 전력 패턴에 기반한 예측값 계산
            raw_prediction = percentile_95 * (1 + safety_margin)
            
            # 5kW 단위로 반올림하되, 실제 데이터 패턴 고려
            raw_prediction = round(raw_prediction / 5) * 5
            raw_prediction = max(50, raw_prediction)  # 최소 50kW
            
            # 계약전력은 제한 적용
            contract_recommendation = min(max_limit, raw_prediction)
        else:
            # 완속충전기: 데이터 품질에 따른 적응형 안전마진
            data_count = len(station_data) if station_data is not None and not station_data.empty else 0
            
            if data_count > 500:
                safety_margin = 0.08 if percentile_95 > 5 else 0.05
            else:
                safety_margin = 0.12 if percentile_95 > 5 else 0.08
            
            raw_prediction = percentile_95 * (1 + safety_margin)
            raw_prediction = round(raw_prediction)  # 1kW 단위
            raw_prediction = max(3, raw_prediction)  # 최소 3kW
            
            # 계약전력은 제한 적용
            contract_recommendation = min(max_limit, raw_prediction)
            
        # 로깅으로 계산 과정 추적
        self.logger.info(f"Contract calculation: percentile_95={percentile_95:.1f}kW, "
                        f"raw_prediction={raw_prediction:.1f}kW, "
                        f"contract_recommendation={contract_recommendation:.1f}kW, "
                        f"max_limit={max_limit}kW, is_fast={is_fast_charger}, data_count={data_count if 'data_count' in locals() else 0}")
        
        return {
            "raw_prediction": raw_prediction,
            "contract_recommendation": contract_recommendation,
            "is_capped": raw_prediction > contract_recommendation,
            "max_limit": max_limit,
            "charger_type": "fast" if is_fast_charger else "slow"
        }

    def _get_connector_type(self, station_data: pd.DataFrame) -> str:
        """커넥터 타입 추출"""
        connector_cols = ["커넥터타입", "connector_type"]
        for col in connector_cols:
            if col in station_data.columns:
                connector = station_data[col].iloc[0] if not station_data[col].isna().all() else None
                if connector:
                    return str(connector)
        return "DC콤보"

    def _get_station_name_by_id(self, station_id: str) -> str:
        """충전소 ID로 충전소명 조회"""
        try:
            loader = ChargingDataLoader(station_id)
            df = loader.load_csv_file()
            if df.empty:
                return station_id
            
            station_col = self._find_station_column(df)
            if not station_col:
                return station_id
                
            station_data = df[df[station_col] == station_id].copy()
            if station_data.empty:
                return station_id
                
            return self._get_station_name(station_data, station_id)
        except Exception:
            return station_id

    def _calculate_station_metrics(self, station_data: pd.DataFrame) -> Dict[str, Any]:
        """충전소 메트릭 계산 - 모든 계산을 백엔드에서 수행"""
        metrics = {"data_sessions": len(station_data), "utilization": "N/A", "last_activity": None}

        # 전력 통계
        power_cols = ["순간최고전력", "max_power", "전력"]
        power_col = None
        for col in power_cols:
            if col in station_data.columns:
                power_col = col
                break

        if power_col:
            power_data = station_data[power_col].dropna()
            if not power_data.empty:
                metrics.update(
                    {
                        "avg_power": round(power_data.mean(), 1),
                        "max_power": round(power_data.max(), 1),
                        "min_power": round(power_data.min(), 1),
                        "power_std": round(power_data.std(), 1),
                        "utilization": f"{min(100, round(power_data.mean() / 100 * 100, 1))}%",
                    }
                )

        # 시간 정보
        date_cols = ["충전시작일시", "start_time", "시작시간"]
        date_col = None
        for col in date_cols:
            if col in station_data.columns:
                date_col = col
                break

        if date_col:
            dates = pd.to_datetime(station_data[date_col], errors="coerce").dropna()
            if not dates.empty:
                metrics["last_activity"] = dates.max().strftime("%Y-%m-%d %H:%M")
                metrics["first_activity"] = dates.min().strftime("%Y-%m-%d %H:%M")
                metrics["active_days"] = (dates.max() - dates.min()).days + 1

        return metrics

    def _matches_search(self, station_info: Dict[str, Any], search: str) -> bool:
        """검색 조건 매칭"""
        search_lower = search.lower()
        searchable_fields = [
            str(station_info.get("id", "")),
            str(station_info.get("name", "")),
            str(station_info.get("location", "")),
        ]

        return any(search_lower in field.lower() for field in searchable_fields)

    def _sort_stations(self, stations: List[Dict[str, Any]], sort_by: str, sort_order: str) -> List[Dict[str, Any]]:
        """충전소 목록 정렬"""
        reverse = sort_order.lower() == "desc"

        sort_key_map = {
            "id": lambda x: x.get("id", ""),
            "name": lambda x: x.get("name", ""),
            "location": lambda x: x.get("location", ""),
            "region": lambda x: x.get("region", ""),
            "city": lambda x: x.get("city", ""),
            "sessions": lambda x: x.get("data_sessions", 0),
            "last_activity": lambda x: x.get("last_activity", ""),
            "avg_power": lambda x: x.get("avg_power", 0),
            "max_power": lambda x: x.get("max_power", 0),
            "utilization": lambda x: float(x.get("utilization", "0").rstrip("%")) if x.get("utilization") != "N/A" else 0,
            "charger_type": lambda x: x.get("charger_type", ""),
        }

        sort_func = sort_key_map.get(sort_by, sort_key_map["id"])

        try:
            return sorted(stations, key=sort_func, reverse=reverse)
        except Exception as e:
            self.logger.warning(f"Sort failed: {e}, using default")
            return stations

    def get_station_timeseries(self, station_id: str, days: int = 3650) -> Dict[str, Any]:
        """충전소 시계열 데이터 - 완전 가공된 데이터 반환"""
        cache_key = f"timeseries_{station_id}_{days}"
        cached_result = self._get_cache(cache_key)
        if cached_result:
            return cached_result

        try:
            loader = ChargingDataLoader(station_id)
            df = loader.load_historical_sessions(days=days)

            if df.empty:
                return {"success": False, "message": "데이터가 없습니다.", "data": [], "station_id": station_id}

            # 완전 가공된 시계열 데이터 생성
            timeseries_data, monthly_peaks, data_info = self._process_timeseries_data(df)

            result = {
                "success": True,
                "station_id": station_id,
                "data": timeseries_data,
                "monthly_peaks": monthly_peaks,
                "data_info": data_info,
                "timestamp": datetime.now().isoformat(),
            }

            self._set_cache(cache_key, result)
            return result

        except Exception as e:
            self.logger.error(f"Error getting timeseries for {station_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e), "station_id": station_id}

    def _process_timeseries_data(self, df: pd.DataFrame):
        """시계열 데이터 가공 - 모든 계산을 백엔드에서 완료"""

        # 날짜와 전력 컬럼 찾기
        date_columns = [
            col for col in df.columns if any(keyword in col for keyword in ["일시", "date", "time", "시작"])
        ]
        power_columns = [col for col in df.columns if "전력" in col or "power" in col.lower()]

        if not date_columns or not power_columns:
            return [], [], {}

        date_col = date_columns[0]
        power_col = power_columns[0]

        # 데이터 정리
        df_clean = df[[date_col, power_col]].copy()
        df_clean = df_clean.dropna()
        df_clean[date_col] = pd.to_datetime(df_clean[date_col], errors="coerce")
        df_clean[power_col] = pd.to_numeric(df_clean[power_col], errors="coerce")
        df_clean = df_clean.dropna()

        if df_clean.empty:
            return [], [], {}

        # 시계열 데이터 생성
        timeseries_data = []
        for _, row in df_clean.iterrows():
            timeseries_data.append({"timestamp": row[date_col].isoformat(), "power": round(float(row[power_col]), 2)})

        # 월별 최대값 계산 - 백엔드에서 완료
        df_clean["year_month"] = df_clean[date_col].dt.to_period("M")
        monthly_max = df_clean.groupby("year_month")[power_col].max().reset_index()

        monthly_peaks = []
        for _, row in monthly_max.iterrows():
            period = row["year_month"]
            monthly_peaks.append(
                {
                    "month": f"{period.year}-{period.month:02d}",
                    "peak_power": round(float(row[power_col]), 2),
                    "label": f"{period.year}.{period.month:02d}",
                }
            )

        # 데이터 정보
        data_info = {
            "total_records": len(timeseries_data),
            "date_range": {"start": df_clean[date_col].min().isoformat(), "end": df_clean[date_col].max().isoformat()},
            "power_stats": {
                "min": round(float(df_clean[power_col].min()), 2),
                "max": round(float(df_clean[power_col].max()), 2),
                "mean": round(float(df_clean[power_col].mean()), 2),
                "std": round(float(df_clean[power_col].std()), 2),
            },
        }

        return timeseries_data, monthly_peaks, data_info

    def get_station_prediction(self, station_id: str) -> Dict[str, Any]:
        """충전소 예측 데이터 - 완전 가공된 예측 결과"""
        cache_key = f"prediction_{station_id}"
        cached_result = self._get_cache(cache_key)
        if cached_result:
            return cached_result

        try:
            loader = ChargingDataLoader(station_id)
            patterns = loader.analyze_charging_patterns()

            if not patterns or "power_statistics" not in patterns:
                return {"success": False, "message": "예측을 위한 충분한 데이터가 없습니다.", "station_id": station_id}

            # 예측 계산 - 백엔드에서 모든 비즈니스 로직 수행
            prediction_result = self._calculate_predictions(patterns, station_id)
            prediction_result["station_id"] = station_id
            prediction_result["station_name"] = self._get_station_name_by_id(station_id)

            self._set_cache(cache_key, prediction_result)
            return self._clean_for_json(prediction_result)

        except Exception as e:
            self.logger.error(f"Error getting prediction for {station_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e), "station_id": station_id}

    def _calculate_predictions(self, patterns: Dict[str, Any], station_id: str) -> Dict[str, Any]:
        """고급 통계 모델을 사용한 예측 계산"""
        from ..prediction.advanced_engine import AdvancedPredictionEngine
        
        # 고급 예측 엔진 초기화
        prediction_engine = AdvancedPredictionEngine()
        
        # 원본 데이터 가져오기 (station_id 매개변수 유지)
        try:
            loader = ChargingDataLoader(station_id)
            raw_data = loader.load_historical_sessions(days=365, merge_all=True)
            
            # 고급 모델로 예측 수행
            ensemble_result = prediction_engine.predict_contract_power(raw_data, station_id)
            
            # 기존 통계 정보도 유지
            power_stats = patterns["power_statistics"]
            
            # 실제 raw_data에서 95백분위수 직접 계산 (더 정확함)
            if not raw_data.empty:
                power_columns = [col for col in raw_data.columns if "전력" in col and "최고" in col]
                if power_columns:
                    power_data = raw_data[power_columns[0]].dropna()
                    if not power_data.empty:
                        current_peak = power_data.quantile(0.95)
                    else:
                        current_peak = power_stats.get("percentile_95", 45.0)
                else:
                    current_peak = power_stats.get("percentile_95", 45.0)
            else:
                current_peak = power_stats.get("percentile_95", 45.0)
                
            confidence = min(0.95, max(0.4, power_stats.get("count", 0) / 1000))
            
            # 실제 데이터로부터 월별 차트 데이터 생성
            chart_data = self._generate_monthly_chart_data(patterns)
            
            # 데이터 범위 정보
            data_start_date = patterns.get("date_range", {}).get("start", datetime.now() - timedelta(days=365))
            data_end_date = patterns.get("date_range", {}).get("end", datetime.now())
            
            # 마지막달 최고 전력 (실제 데이터 기준)
            last_month_peak = current_peak
            if chart_data:
                # 실제 데이터가 있는 마지막 달 찾기
                for item in reversed(chart_data):
                    if item.get("actual") is not None:
                        last_month_peak = item["actual"]
                        break
            
            # 충전기 타입별 제한을 적용한 고급 모델 예측 결과
            try:
                # 충전기 타입 판별을 위해 더 많은 데이터 사용 (기존 raw_data 재활용)
                if not raw_data.empty:
                    max_contract_advanced = self._get_charger_max_contract(raw_data)
                    is_fast_charger_advanced = self._is_fast_charger(raw_data)
                else:
                    # 데이터가 없으면 별도 로드
                    loader_temp = ChargingDataLoader(station_id)
                    station_df_temp = loader_temp.load_historical_sessions(days=90)
                    max_contract_advanced = self._get_charger_max_contract(station_df_temp)
                    is_fast_charger_advanced = self._is_fast_charger(station_df_temp)
                self.logger.info(f"Station {station_id}: max_contract={max_contract_advanced}kW, fast_charger={is_fast_charger_advanced}")
            except Exception as e:
                self.logger.warning(f"Failed to determine charger type for {station_id}: {e}")
                max_contract_advanced = 100
                is_fast_charger_advanced = True
            
            # 실제 데이터 기반 최적 계약전력 계산
            raw_prediction = ensemble_result.raw_prediction  # 제한 없는 원본 예측값
            self.logger.info(f"Station {station_id}: current_peak={current_peak:.1f}kW (used for contract calculation)")
            optimal_result = self._calculate_optimal_contract_power(raw_data, current_peak)
            
            # 고급 모델 예측과 실제 데이터 기반 계산 중 적절한 값 선택
            if abs(raw_prediction - optimal_result["raw_prediction"]) / optimal_result["raw_prediction"] < 0.2:  # 20% 이내 차이면 고급 모델 사용
                # 고급 모델 사용하지만 계약전력 제한은 적용
                algorithm_prediction = raw_prediction
                recommended_contract_kw = min(max_contract_advanced, raw_prediction)
            else:
                # 실제 데이터 기반 사용
                algorithm_prediction = optimal_result["raw_prediction"]
                recommended_contract_kw = optimal_result["contract_recommendation"]
            
            # 예측값이 제한을 넘는지 확인
            prediction_exceeds_limit = algorithm_prediction > recommended_contract_kw
            
            self.logger.info(f"Advanced prediction for {station_id}: algorithm={algorithm_prediction}kW, contract={recommended_contract_kw}kW, capped={prediction_exceeds_limit}")
            
            # 신뢰도 계산 (불확실성 기반)
            model_confidence = max(0.4, 1.0 - (ensemble_result.uncertainty / 100.0))
            final_confidence = min(0.95, (confidence + model_confidence) / 2)
            
        except Exception as e:
            self.logger.warning(f"Advanced prediction failed for {station_id}: {e}, using fallback")
            # 폴백: 기존 방식
            power_stats = patterns["power_statistics"]
            current_peak = power_stats.get("percentile_95", 45.0)
            confidence = min(0.95, max(0.4, power_stats.get("count", 0) / 1000))
            
            chart_data = self._generate_monthly_chart_data(patterns)
            data_start_date = patterns.get("date_range", {}).get("start", datetime.now() - timedelta(days=365))
            data_end_date = patterns.get("date_range", {}).get("end", datetime.now())
            
            last_month_peak = current_peak
            if chart_data:
                for item in reversed(chart_data):
                    if item.get("actual") is not None:
                        last_month_peak = item["actual"]
                        break
            
            # 충전기 타입별 제한 적용
            try:
                loader = ChargingDataLoader(station_id)
                station_df = loader.load_historical_sessions(days=30)
                max_contract = self._get_charger_max_contract(station_df)
                is_fast_charger_fallback = self._is_fast_charger(station_df)
                self.logger.info(f"Fallback for {station_id}: max_contract={max_contract}kW, fast_charger={is_fast_charger_fallback}")
            except Exception as e:
                self.logger.warning(f"Failed to determine charger type for {station_id}: {e}")
                max_contract = 100  # 기본값
                is_fast_charger_fallback = True
            
            # 실제 데이터 기반 최적 계약전력 계산
            optimal_result = self._calculate_optimal_contract_power(station_df, current_peak)
            algorithm_prediction = optimal_result["raw_prediction"]
            recommended_contract_kw = optimal_result["contract_recommendation"]
            prediction_exceeds_limit = optimal_result["is_capped"]
            
            self.logger.info(f"Fallback prediction for {station_id}: percentile_95={current_peak}kW, algorithm={algorithm_prediction}kW -> contract={recommended_contract_kw}kW, capped={prediction_exceeds_limit}")
            final_confidence = confidence
            ensemble_result = None

        # 결과 준비
        result = {
            "success": True,
            "station_id": "",  # Will be set by caller
            "station_name": "",  # Will be set by caller
            "predicted_peak": current_peak,  # Frontend expects this field
            "confidence": final_confidence if 'final_confidence' in locals() else confidence,
            "predicted_hour": self._get_peak_hour(patterns),
            "method": "advanced_ensemble_models" if ensemble_result else "percentile_95_seasonal",
            "timestamp": datetime.now().isoformat(),
            # Additional data for charts
            "current_peak": current_peak,
            "chart_data": chart_data,
            "last_month_peak": last_month_peak,
            "recommended_contract_kw": recommended_contract_kw,
            # 알고리즘 예측값 (제한 없는 원본 예측)
            "algorithm_prediction_kw": algorithm_prediction if 'algorithm_prediction' in locals() else recommended_contract_kw,
            "prediction_exceeds_limit": prediction_exceeds_limit if 'prediction_exceeds_limit' in locals() else False,
            "data_start_date": (
                data_start_date.isoformat() if hasattr(data_start_date, "isoformat") else str(data_start_date)
            ),
            "data_end_date": data_end_date.isoformat() if hasattr(data_end_date, "isoformat") else str(data_end_date),
            "record_count": power_stats.get("count", 0),
        }
        
        # 고급 모델 결과가 있으면 추가 정보 포함
        if ensemble_result:
            result.update({
                "advanced_prediction": {
                    "final_prediction": ensemble_result.final_prediction,
                    "ensemble_method": ensemble_result.ensemble_method,
                    "model_count": len(ensemble_result.model_predictions),
                    "uncertainty": ensemble_result.uncertainty,
                    "model_weights": ensemble_result.weights,
                    "models": [
                        {
                            "name": pred.model_name,
                            "prediction": round(pred.predicted_value, 1),
                            "confidence": round(pred.confidence_score, 2),
                            "method": pred.method_details.get("description", pred.model_name)
                        }
                        for pred in ensemble_result.model_predictions
                    ]
                },
                "visualization_data": ensemble_result.visualization_data
            })
        
        return result

    def _generate_monthly_chart_data(self, patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """월별 차트 데이터 생성 - 실제 데이터 기반"""
        power_stats = patterns["power_statistics"]
        
        # 실제 월별 데이터 추출 시도
        monthly_patterns = patterns.get("monthly_patterns", {})
        
        chart_data = []
        
        # 데이터 범위 확인
        date_range = patterns.get("date_range", {})
        start_date = date_range.get("start")
        end_date = date_range.get("end")
        
        if start_date and end_date and monthly_patterns:
            # 실제 데이터가 있는 경우 - 실제 데이터 사용
            try:
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                # 실제 데이터 기간에 맞춰 동적으로 월별 데이터 생성
                current_date = start_date.replace(day=1)
                end_date_month = end_date.replace(day=1)
                
                # 현재 날짜까지만 실제 데이터 생성
                now = datetime.now()
                current_month = now.replace(day=1)
                
                while current_date <= end_date_month:
                    month_key = current_date.strftime("%Y-%m")  # YYYY-MM 형식
                    month_label = f"{str(current_date.year)[-2:]}.{current_date.month:02d}"
                    
                    # 현재 월보다 미래는 예측 데이터로 처리
                    is_future = current_date > current_month
                    
                    if not is_future and month_key in monthly_patterns:
                        # 과거/현재 데이터: 실제 월별 데이터에서 평균 전력 추출
                        actual_power = monthly_patterns[month_key].get("avg_power", 0)
                        predicted_power = None
                    elif is_future:
                        # 미래 데이터: 예측값으로 처리
                        base_power = power_stats.get("percentile_95", 50)
                        actual_power = None
                        predicted_power = base_power * (1.0 + (current_date.month % 12) * 0.02)  # 계절적 변동
                    else:
                        # 데이터가 없는 과거 월
                        actual_power = None
                        predicted_power = None
                    
                    chart_data.append({
                        "month": f"{current_date.year}-{current_date.month:02d}",
                        "label": month_label,
                        "actual": actual_power,
                        "predicted": predicted_power
                    })
                    
                    # 다음 달로
                    if current_date.month == 12:
                        current_date = current_date.replace(year=current_date.year + 1, month=1)
                    else:
                        current_date = current_date.replace(month=current_date.month + 1)
                        
                # 미래 3개월 예측 데이터 추가
                base_power = min(power_stats.get("percentile_95", 45.0), 80.0)  # 현실적인 기준값
                for i in range(3):
                    if current_date.month == 12:
                        next_month = current_date.replace(year=current_date.year + 1, month=1)
                    else:
                        next_month = current_date.replace(month=current_date.month + 1)
                    
                    month_label = f"{str(next_month.year)[-2:]}.{next_month.month:02d}"
                    predicted_power = base_power * (1.0 + i * 0.01)  # 소폭 증가
                    
                    chart_data.append({
                        "month": f"{next_month.year}-{next_month.month:02d}",
                        "label": month_label,
                        "actual": None,
                        "predicted": predicted_power
                    })
                    
                    current_date = next_month
                    
            except Exception as e:
                self.logger.warning(f"Failed to parse date range: {e}")
                # 데이터 파싱 실패시에도 빈 차트 데이터 반환
                chart_data = []
        else:
            # 데이터가 없는 경우 빈 차트 데이터 반환
            self.logger.warning(f"No real data available for chart generation - returning empty chart data")
            chart_data = []
        
        return chart_data
    
    def _generate_fallback_chart_data(self, power_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """폴백 차트 데이터 생성"""
        base_power = min(power_stats.get("percentile_95", 45.0), 60.0)  # 현실적인 기준
        now = datetime.now()
        chart_data = []
        
        # 최근 6개월 데이터
        for i in range(6):
            target_month = now.month - 5 + i
            target_year = now.year
            
            while target_month < 1:
                target_month += 12
                target_year -= 1
            while target_month > 12:
                target_month -= 12
                target_year += 1
                
            month_date = datetime(target_year, target_month, 1)
            month_label = f"{str(month_date.year)[-2:]}.{month_date.month:02d}"
            
            # 현실적인 변동
            actual_power = base_power * (0.9 + (i % 3) * 0.1)
            
            chart_data.append({
                "month": f"{month_date.year}-{month_date.month:02d}",
                "label": month_label,
                "actual": actual_power,
                "predicted": None
            })
        
        return chart_data

    def _get_peak_hour(self, patterns: Dict[str, Any]) -> str:
        """피크 시간대 추출"""
        hourly_patterns = patterns.get("hourly_patterns", {})
        if not hourly_patterns:
            return "14:00"  # 기본값
            
        # 가장 높은 평균 전력을 가진 시간대 찾기
        max_hour = "14"
        max_power = 0
        for hour, data in hourly_patterns.items():
            if data.get("avg_power", 0) > max_power:
                max_power = data.get("avg_power", 0)
                max_hour = hour
                
        return f"{max_hour}:00"

    def get_monthly_contract_recommendation(
        self, 
        station_id: str, 
        year: int = None, 
        month: int = None, 
        mode: str = "p95", 
        round_kw: int = 1
    ) -> Dict[str, Any]:
        """월별 계약전력 추천 - 완전 계산된 추천값"""
        # Default to current year/month if not provided
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
            
        cache_key = f"contract_{station_id}_{year}_{month}_{mode}"
        cached_result = self._get_cache(cache_key)
        if cached_result:
            return cached_result

        try:
            loader = ChargingDataLoader(station_id)
            patterns = loader.analyze_charging_patterns()

            power_stats = patterns.get("power_statistics", {})

            if not power_stats:
                recommended_kw = 50.0
                safety_margin = 10
            else:
                # 95% 백분위수 + 안전 마진
                percentile_95 = power_stats.get("percentile_95", 45.0)
                peak_variation = power_stats.get("std", 5.0)

                # 안전 마진을 동적으로 계산 (변동성이 클수록 마진 증가)
                if peak_variation > 20:
                    safety_margin = 20
                elif peak_variation > 10:
                    safety_margin = 15
                else:
                    safety_margin = 10

                recommended_kw = percentile_95 * (1 + safety_margin / 100)

            # 충전기 타입별 제한 적용
            try:
                loader = ChargingDataLoader(station_id)
                station_df = loader.load_historical_sessions(days=30)
                max_contract = self._get_charger_max_contract(station_df)
                is_fast_charger = self._is_fast_charger(station_df)
            except Exception:
                max_contract = 100
                is_fast_charger = True

            # 충전기 타입별 최소값 설정
            if is_fast_charger:
                min_kw = 50  # 급속충전기 최소 50kW
                round_unit = 5  # 5kW 단위
            else:
                min_kw = 3   # 완속충전기 최소 3kW
                round_unit = 1  # 1kW 단위

            # 실제 데이터 기반 최적 계약전력 계산 사용
            optimal_result = self._calculate_optimal_contract_power(station_df, percentile_95)
            
            # Apply round_kw parameter to contract recommendation
            final_kw = round(optimal_result["contract_recommendation"] / round_kw) * round_kw
            algorithm_prediction = optimal_result["raw_prediction"]
            prediction_exceeds_limit = optimal_result["is_capped"]
            final_kw = max(min_kw, min(max_contract, final_kw))
            
            # 로깅 추가
            self.logger.info(f"Monthly contract for {station_id}: charger_type={'fast' if is_fast_charger else 'slow'}, "
                           f"percentile_95={percentile_95:.1f}kW, algorithm={algorithm_prediction:.1f}kW, "
                           f"contract={final_kw:.1f}kW, max_limit={max_contract}kW, capped={prediction_exceeds_limit}")
            
            result = {
                "success": True,
                "station_id": station_id,
                "station_name": self._get_station_name_by_id(station_id),
                "year": year,
                "month": month,
                "horizon_days": 30,  # Default 30-day horizon
                "mode": mode,
                "predicted_peak_kw": int(percentile_95 if power_stats else 45.0),
                "recommended_contract_kw": int(final_kw),
                "charger_type": "fast" if is_fast_charger else "slow",
                "actual_peak_power": float(percentile_95),
                "calculation_method": "percentile_95_dynamic_margin",
                "safety_margin_percent": safety_margin,
                "data_quality": "high" if power_stats.get("count", 0) > 100 else "medium",
                "timestamp": datetime.now().isoformat(),
                # 알고리즘 예측값 추가
                "algorithm_prediction_kw": int(algorithm_prediction),
                "prediction_exceeds_limit": prediction_exceeds_limit,
            }

            self._set_cache(cache_key, result)
            return result

        except Exception as e:
            self.logger.error(f"Error getting contract recommendation for {station_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e), "station_id": station_id}

    def get_energy_demand_forecast(self, station_id: str, days: int = 90) -> Dict[str, Any]:
        """에너지 수요 예측 - kWh 기반 분석"""
        cache_key = f"energy_demand_{station_id}_{days}"
        cached_result = self._get_cache(cache_key)
        if cached_result:
            return cached_result

        try:
            loader = ChargingDataLoader(station_id)
            df = loader.load_historical_sessions(days=days)

            if df.empty:
                return {"success": False, "message": "에너지 데이터가 없습니다.", "station_id": station_id}

            # 에너지 컬럼 찾기
            energy_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ["에너지", "energy", "kwh", "충전량"])]
            
            if not energy_cols:
                return {"success": False, "message": "에너지 데이터 컬럼을 찾을 수 없습니다.", "station_id": station_id}

            energy_col = energy_cols[0]
            
            # 날짜 컬럼 찾기
            date_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ["일시", "date", "time", "시작", "종료"])]
            
            if not date_cols:
                return {"success": False, "message": "날짜 컬럼을 찾을 수 없습니다.", "station_id": station_id}

            date_col = date_cols[0]

            # 데이터 정리
            df_clean = df[[date_col, energy_col]].copy()
            df_clean = df_clean.dropna()
            df_clean[date_col] = pd.to_datetime(df_clean[date_col], errors="coerce")
            df_clean[energy_col] = pd.to_numeric(df_clean[energy_col], errors="coerce")
            df_clean = df_clean.dropna()

            if df_clean.empty:
                return {"success": False, "message": "유효한 에너지 데이터가 없습니다.", "station_id": station_id}

            # 일별 에너지 소비량 집계
            df_clean['date'] = df_clean[date_col].dt.date
            daily_energy = df_clean.groupby('date')[energy_col].sum().reset_index()
            daily_energy['date'] = pd.to_datetime(daily_energy['date'])

            # 실제 데이터와 예측 데이터 생성
            result = self._generate_energy_forecast(daily_energy, energy_col, station_id)
            result["station_id"] = station_id
            result["station_name"] = self._get_station_name_by_id(station_id)

            self._set_cache(cache_key, result)
            return result

        except Exception as e:
            self.logger.error(f"Error getting energy demand forecast for {station_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e), "station_id": station_id}

    def _generate_energy_forecast(self, daily_energy: pd.DataFrame, energy_col: str, station_id: str) -> Dict[str, Any]:
        """에너지 소비 패턴 분석 및 예측"""
        
        # 기본 통계
        energy_stats = {
            "total_energy": float(daily_energy[energy_col].sum()),
            "avg_daily": float(daily_energy[energy_col].mean()),
            "min_daily": float(daily_energy[energy_col].min()),
            "max_daily": float(daily_energy[energy_col].max()),
            "std_daily": float(daily_energy[energy_col].std())
        }

        # 시계열 데이터 생성 (실제 데이터)
        actual_data = []
        for _, row in daily_energy.iterrows():
            actual_data.append({
                "date": row['date'].strftime("%Y-%m-%d"),
                "energy": round(float(row[energy_col]), 2),
                "type": "actual"
            })

        # 예측 데이터 생성 (향후 30일)
        last_date = daily_energy['date'].max()
        avg_energy = daily_energy[energy_col].mean()
        std_energy = daily_energy[energy_col].std()
        
        # 계절성 및 트렌드 고려한 간단한 예측
        predicted_data = []
        for i in range(1, 31):  # 30일 예측
            future_date = last_date + pd.Timedelta(days=i)
            
            # 계절성 패턴 (월별)
            month = future_date.month
            seasonal_factor = 1.0 + 0.1 * np.sin(2 * np.pi * (month - 1) / 12)
            
            # 주간 패턴 (주말 vs 주중)
            weekday = future_date.weekday()
            weekly_factor = 0.8 if weekday >= 5 else 1.0  # 주말은 80%
            
            # 노이즈 추가
            noise_factor = 1.0 + np.random.normal(0, 0.1)
            
            predicted_energy = avg_energy * seasonal_factor * weekly_factor * noise_factor
            predicted_energy = max(0, predicted_energy)  # 음수 방지
            
            predicted_data.append({
                "date": future_date.strftime("%Y-%m-%d"),
                "energy": round(predicted_energy, 2),
                "type": "predicted"
            })

        # 월별 집계 (실제 + 예측)
        monthly_summary = self._generate_monthly_energy_summary(daily_energy, energy_col)

        # 성장률 계산
        if len(daily_energy) >= 30:
            recent_avg = daily_energy[energy_col].tail(30).mean()
            older_avg = daily_energy[energy_col].head(30).mean() if len(daily_energy) >= 60 else recent_avg
            growth_rate = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        else:
            growth_rate = 0

        return {
            "success": True,
            "energy_statistics": energy_stats,
            "timeseries_data": actual_data + predicted_data,
            "actual_data": actual_data,
            "predicted_data": predicted_data,
            "monthly_summary": monthly_summary,
            "growth_rate": round(growth_rate, 1),
            "data_range": {
                "start_date": daily_energy['date'].min().strftime("%Y-%m-%d"),
                "end_date": daily_energy['date'].max().strftime("%Y-%m-%d"),
                "prediction_start": predicted_data[0]["date"] if predicted_data else None,
                "prediction_end": predicted_data[-1]["date"] if predicted_data else None
            },
            "insights": self._generate_energy_insights(energy_stats, growth_rate),
            "timestamp": datetime.now().isoformat()
        }

    def _generate_monthly_energy_summary(self, daily_energy: pd.DataFrame, energy_col: str) -> List[Dict[str, Any]]:
        """월별 에너지 소비 요약"""
        daily_energy['year_month'] = daily_energy['date'].dt.to_period('M')
        monthly_data = daily_energy.groupby('year_month')[energy_col].agg(['sum', 'mean', 'count']).reset_index()
        
        monthly_summary = []
        for _, row in monthly_data.iterrows():
            period = row['year_month']
            monthly_summary.append({
                "month": f"{period.year}-{period.month:02d}",
                "month_label": f"{period.year}.{period.month:02d}",
                "total_energy": round(float(row['sum']), 2),
                "avg_daily": round(float(row['mean']), 2),
                "active_days": int(row['count'])
            })
        
        return monthly_summary

    def _generate_energy_insights(self, stats: Dict[str, Any], growth_rate: float) -> List[str]:
        """에너지 소비 인사이트 생성"""
        insights = []
        
        # 일평균 소비량 분석
        avg_daily = stats["avg_daily"]
        if avg_daily > 50:
            insights.append(f"일평균 {avg_daily:.1f}kWh로 높은 에너지 소비량을 보입니다")
        elif avg_daily > 20:
            insights.append(f"일평균 {avg_daily:.1f}kWh로 보통 수준의 에너지 소비량을 보입니다")
        else:
            insights.append(f"일평균 {avg_daily:.1f}kWh로 낮은 에너지 소비량을 보입니다")
        
        # 변동성 분석
        cv = stats["std_daily"] / stats["avg_daily"] if stats["avg_daily"] > 0 else 0
        if cv > 0.5:
            insights.append("에너지 소비 패턴이 불규칙합니다")
        elif cv > 0.3:
            insights.append("에너지 소비 패턴이 보통 수준의 변동성을 보입니다")
        else:
            insights.append("에너지 소비 패턴이 안정적입니다")
        
        # 성장률 분석
        if growth_rate > 10:
            insights.append(f"에너지 소비가 {growth_rate:.1f}% 증가 추세입니다")
        elif growth_rate < -10:
            insights.append(f"에너지 소비가 {abs(growth_rate):.1f}% 감소 추세입니다")
        else:
            insights.append("에너지 소비가 안정적인 추세를 보입니다")
        
        return insights

    def clear_cache(self, station_id: str = None) -> Dict[str, Any]:
        """캐시 클리어"""
        if station_id:
            # 특정 충전소 캐시 클리어
            keys_to_remove = [key for key in self._cached_data.keys() if station_id in key]
            for key in keys_to_remove:
                self._cached_data.pop(key, None)
                self._cache_timestamp.pop(key, None)
            return {"message": f"Cache cleared for station {station_id}", "cleared_keys": len(keys_to_remove)}
        else:
            # 전체 캐시 클리어
            cleared_keys = len(self._cached_data)
            self._cached_data.clear()
            self._cache_timestamp.clear()
            return {"message": "All cache cleared", "cleared_keys": cleared_keys}
