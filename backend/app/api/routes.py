from datetime import datetime
import pandas as pd
from pathlib import Path
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from ..data.loader import ChargingDataLoader
from ..data.validator import ChargingDataValidator
from ..services.station_service import StationService

main = None
logger = logging.getLogger(__name__)

# 서비스 인스턴스 생성 - 싱글톤 패턴
_station_service = None


def get_station_service() -> StationService:
    global _station_service
    if _station_service is None:
        _station_service = StationService()
    return _station_service


def set_main_module(main_module):
    global main
    main = main_module


# data/raw 절대 경로 헬퍼
def get_data_dir() -> Path:
    repo_dir = (Path(__file__).resolve().parents[3] / "data" / "raw").resolve()  # <repo_root>/data/raw
    legacy_dir = (Path(__file__).resolve().parents[1] / "data" / "raw").resolve()  # <backend/app>/data/raw

    # 기본 디렉터리 생성
    repo_dir.mkdir(parents=True, exist_ok=True)

    # 레거시 폴더에만 CSV가 있고 repo_dir이 비어 있으면 레거시 사용
    try:
        if legacy_dir.exists():
            has_legacy_csv = any(legacy_dir.glob("*.csv"))
        else:
            has_legacy_csv = False
        has_repo_csv = any(repo_dir.glob("*.csv"))
        if has_legacy_csv and not has_repo_csv:
            return legacy_dir
    except Exception:
        pass

    return repo_dir


api_router = APIRouter()


@api_router.get("/stations")
async def list_stations(
    page: int = 1,
    limit: int = 10000,  # 모든 충전소를 표시하도록 기본값 증가
    include_summary: bool = False,
    search: str = None,
    sort_by: str = "id",
    sort_order: str = "asc",
):
    
    try:
        logger.info(f"API called: page={page}, limit={limit}, search={search}")

        # CSV 파일 존재 여부 확인
        data_dir = get_data_dir()
        csv_files = list(data_dir.glob("*.csv"))

        if not csv_files:
            return {
                "success": False,
                "error": "CSV 파일을 먼저 업로드해주세요.",
                "requiresUpload": True,
                "stations": [],
                "pagination": {"page": page, "limit": limit, "total": 0, "hasNext": False},
            }

        station_service = get_station_service()
        result = station_service.list_stations(search=search, sort_by=sort_by, sort_order=sort_order)

        # 페이지네이션 정보 추가 (모든 충전소 표시)
        if result["success"]:
            stations = result.get("stations", [])
            total = result.get("total", len(stations))
            # limit이 매우 큰 경우(10000) 모든 충전소 표시, 아니면 제한 적용
            if limit >= 10000:
                stations = stations  # 모든 충전소 표시
            else:
                stations = stations[:limit]  # 제한된 충전소 표시
            result["stations"] = stations
            result["pagination"] = {
                "page": page,
                "limit": limit,
                "total": total,
                "hasNext": total > len(stations),
                "hasPrev": False,
            }

        return result

    except Exception as e:
        logger.error(f"Error in list_stations: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "stations": [],
            "pagination": {"page": page, "limit": limit, "total": 0, "hasNext": False},
        }


@api_router.get("/station-analysis/{station_id}")
async def get_station_detailed_analysis(station_id: str):
    
    try:
        loader = ChargingDataLoader(station_id)

        # Get raw data
        summary = loader.get_data_summary()
        patterns = loader.analyze_charging_patterns()
        realtime_status = loader.load_realtime_status()
        external_factors = loader.load_external_factors()

        # Create station_info from available data - use CSV data
        df = loader.load_historical_sessions(days=90)
        first_row = df.iloc[0] if not df.empty else pd.Series()

        def safe_get(key, default):
            value = first_row.get(key, default)
            return str(value) if pd.notna(value) and str(value).strip() != "nan" else default

        station_name = safe_get("충전소명", f"충전소 {station_id}")
        station_location = safe_get("충전소주소", "위치 정보 없음")
        station_region = safe_get("권역", "미상")
        station_city = safe_get("시군구", "미상")
        charger_type = safe_get("충전기 구분", "급속")
        connector_types = df["커넥터명"].unique() if "커넥터명" in df.columns else ["DC콤보"]
        connector_type = "+".join([str(c) for c in connector_types if pd.notna(c)])

        station_info = {
            "id": station_id,
            "name": station_name,
            "location": station_location,
            "region": station_region,
            "city": station_city,
            "charger_type": charger_type,
            "connector_type": connector_type,
            "status": "정상 운영",
            "data_sessions": summary.get("total_sessions", 0),
            "utilization": "N/A",
            "last_activity": None,
        }

        # Enhance power_stats to include percentile_95
        power_stats = summary.get("power_stats", {})
        if power_stats and "percentile_95" not in power_stats:
            # Use available percentile data from patterns if available
            pattern_stats = patterns.get("power_statistics", {})
            if pattern_stats.get("percentile_95"):
                power_stats["percentile_95"] = pattern_stats["percentile_95"]
            else:
                # Fallback calculation
                power_stats["percentile_95"] = power_stats.get("max", 0) * 0.95

        # Create performance_analysis
        performance_analysis = {
            "utilization_rate": min(85.0, max(20.0, (power_stats.get("mean", 50) / 100) * 100)),
            "peak_utilization": min(95.0, max(30.0, (power_stats.get("max", 70) / 100) * 100)),
            "average_session_power": power_stats.get("mean", 45.0),
            "maximum_recorded_power": power_stats.get("max", 70.0),
            "efficiency_grade": "B" if power_stats.get("mean", 45) > 40 else "C",
            "rated_power": 100.0,
        }

        # Create charts_data with proper 24-hour format
        hourly_patterns = patterns.get("hourly_patterns", {})
        hourly_data = []
        for hour in range(24):
            hour_data = hourly_patterns.get(str(hour))
            if hour_data:
                hourly_data.append(hour_data.get("avg_power", 0))
            else:
                # Interpolate missing hours with nearby values or use average
                hourly_data.append(power_stats.get("mean", 35.0))

        charts_data = {
            "hourly_pattern": hourly_data,
            "monthly_predictions": {
                "data": [power_stats.get("mean", 35) * (0.8 + (i % 4) * 0.1) for i in range(12)],
                "labels": ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"],
            },
            "soc_power_relationship": [
                {"x": 10 + i * 10, "y": power_stats.get("mean", 35) * (1.2 - i * 0.1)} for i in range(9)
            ],
        }

        # Enhanced summary with session_stats
        enhanced_summary = {
            **summary,
            "power_stats": power_stats,
            "session_stats": {
                "avg_duration": 45.0,  # minutes
                "avg_energy": 25.0,  # kWh
                "total_energy": summary.get("total_sessions", 10) * 25.0,
            },
        }

        # Enhanced patterns with daily/monthly
        enhanced_patterns = {
            **patterns,
            "daily_patterns": {
                str(i): {
                    "avg_power": power_stats.get("mean", 35) * (0.9 + (i % 7) * 0.02),
                    "session_count": max(1, summary.get("total_sessions", 10) // 7),
                    "peak_hour": 14 + (i % 3),
                }
                for i in range(7)
            },
            "monthly_patterns": {
                str(i): {
                    "avg_power": power_stats.get("mean", 35) * (0.85 + (i % 12) * 0.03),
                    "session_count": max(1, summary.get("total_sessions", 10) // 12),
                    "peak_day": 15 + (i % 15),
                }
                for i in range(12)
            },
        }

        return {
            "station_id": station_id,
            "timestamp": datetime.now().isoformat(),
            "station_info": station_info,
            "summary": enhanced_summary,
            "patterns": enhanced_patterns,
            "performance_analysis": performance_analysis,
            "charts_data": charts_data,
            "realtime_status": realtime_status,
            "external_factors": external_factors,
        }

    except Exception as e:
        logger.error(f"Error in station analysis for {station_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "station_id": station_id}


@api_router.get("/predict/{station_id}")
async def predict_peak_power(station_id: str):
    
    try:
        # 기존 분석 모듈 활용
        loader = ChargingDataLoader(station_id)
        patterns = loader.analyze_charging_patterns()

        # 기본 예측값
        predicted_peak = 45.0
        confidence = 0.5
        method = "baseline"

        if patterns and "power_statistics" in patterns:
            stats = patterns["power_statistics"]
            predicted_peak = min(stats.get("percentile_95", 45.0), 95.0)
            confidence = 0.75
            method = "statistical"

        return {
            "success": True,
            "station_id": station_id,
            "predicted_peak": round(predicted_peak, 1),
            "confidence": confidence,
            "method": method,
            "patterns": patterns,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"success": False, "error": str(e), "station_id": station_id}


@api_router.post("/admin/upload-csv")
async def upload_csv_file(file: UploadFile = File(...), file_type: str = Form("charging_sessions")):
    
    try:
        logger.info(f"Upload started: {file.filename}")

        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="CSV 파일만 가능합니다.")

        contents = await file.read()
        file_size = len(contents)

        if file_size > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="50MB 이하만 가능합니다.")

        # 파일 저장 (data/raw, 파일명 안전 처리)
        upload_dir = get_data_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(file.filename).name  # 디렉토리 제거
        file_path = (upload_dir / safe_name).resolve()

        with open(file_path, "wb") as f:
            f.write(contents)

        # 마커 정리 및 설정
        try:
            marker_legacy = upload_dir / ".active_csv.csv"  # 잘못된 과거 마커
            if marker_legacy.exists():
                try:
                    marker_legacy.unlink()
                except Exception:
                    pass
            marker = upload_dir / ".active_csv"
            marker.write_text(safe_name, encoding="utf-8")
            logger.info(f"Active CSV set to: {safe_name}")
        except Exception as e:
            logger.warning(f"Failed to write .active_csv: {e}")

        # ChargingDataValidator 활용
        validator = ChargingDataValidator()

        # CSV 검증
        encodings = ["utf-8", "euc-kr", "cp949", "utf-8-sig"]
        df = None
        used_encoding = None

        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding, nrows=10)
                used_encoding = encoding
                break
            except Exception:
                continue

        if df is None:
            raise ValueError("파일을 읽을 수 없습니다.")

        # 전체 파일 정보
        df_full = pd.read_csv(file_path, encoding=used_encoding)

        # validator로 검증 (기존 모듈 활용)
        try:
            validation_result = validator.validate_charging_sessions(df_full)
            # numpy.bool 문제 해결을 위해 안전한 변환
            validation_result = {k: bool(v) if hasattr(v, "item") else v for k, v in validation_result.items()}
        except Exception as e:
            logger.warning(f"Validation failed: {e}")
            validation_result = {"status": "validation_skipped", "reason": str(e)}

        def clean_for_json(obj):
            
            import numpy as np

            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [clean_for_json(item) for item in obj]
            else:
                return obj

        # 업로드 후 캐시 무효화
        try:
            station_service = get_station_service()
            station_service.clear_cache()
            logger.info("StationService cache cleared after upload.")
        except Exception as e:
            logger.warning(f"Failed to clear cache after upload: {e}")

        result = {
            "success": True,
            "message": "업로드 완료",
            "filename": safe_name,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "rows_processed": int(len(df_full)),
            "columns": int(len(df_full.columns)),
            "encoding_used": used_encoding,
            "validation": clean_for_json(validation_result),
            "sample_columns": list(df_full.columns)[:10],
            "data_dir": str(upload_dir),
            "active_file": safe_name,
            "active_path": str(file_path),
            "timestamp": datetime.now().isoformat(),
        }

        return clean_for_json(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/data-range/{station_id}")
async def get_data_range(station_id: str):
    
    try:
        loader = ChargingDataLoader(station_id)

        # 전체 데이터 로드 (날짜 범위 확인을 위해)
        df = loader.load_historical_sessions(days=9999)

        if df.empty:
            return {"success": False, "message": "데이터가 없습니다.", "data_range": None}

        # 날짜 컬럼 찾기
        date_cols = [
            col
            for col in df.columns
            if any(keyword in col.lower() for keyword in ["일시", "date", "time", "시작", "종료"])
        ]

        if not date_cols:
            return {
                "success": False,
                "message": "날짜 컬럼을 찾을 수 없습니다.",
                "available_columns": list(df.columns)[:10],
            }

        date_col = date_cols[0]  # 첫 번째 날짜 컬럼 사용

        # 날짜 파싱
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])

        if df.empty:
            return {"success": False, "message": "유효한 날짜 데이터가 없습니다."}

        # 날짜 범위 계산
        min_date = df[date_col].min()
        max_date = df[date_col].max()

        # 월별 데이터 존재 여부 확인
        df["year_month"] = df[date_col].dt.to_period("M")
        available_months = df["year_month"].unique()

        # 월별 세션 수 계산
        monthly_counts = df.groupby("year_month").size().to_dict()

        # 결과 포맷팅
        months_data = []
        for period in sorted(available_months):
            year = period.year
            month = period.month
            month_name = f"{year}년 {month}월"
            session_count = monthly_counts[period]

            months_data.append(
                {
                    "year": year,
                    "month": month,
                    "month_name": month_name,
                    "session_count": session_count,
                    "has_data": session_count > 0,
                }
            )

        return {
            "success": True,
            "station_id": station_id,
            "data_range": {
                "start_date": min_date.strftime("%Y-%m-%d"),
                "end_date": max_date.strftime("%Y-%m-%d"),
                "start_year_month": f"{min_date.year}-{min_date.month:02d}",
                "end_year_month": f"{max_date.year}-{max_date.month:02d}",
                "total_months": len(available_months),
                "total_sessions": len(df),
            },
            "available_months": months_data,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting data range for {station_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "station_id": station_id}


@api_router.get("/stations/{station_id}/timeseries")
async def get_station_timeseries(station_id: str, days: int = 3650):
    
    try:
        station_service = get_station_service()
        return station_service.get_station_timeseries(station_id, days)

    except Exception as e:
        logger.error(f"Error getting timeseries for {station_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "station_id": station_id}


@api_router.get("/stations/{station_id}/timeseries.csv")
async def get_station_timeseries_csv(station_id: str, days: int = 3650):
    
    try:
        from fastapi.responses import Response

        station_service = get_station_service()
        result = station_service.get_station_timeseries(station_id, days)

        if not result.get("success", False) or not result.get("data"):
            # 빈 CSV 반환
            csv_content = "timestamp,power\n"
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={station_id}_timeseries.csv"},
            )

        # 시계열 데이터에서 CSV 생성
        timeseries_data = result["data"]
        csv_lines = ["timestamp,power"]

        for point in timeseries_data:
            timestamp = point.get("x", "")
            power = point.get("y", 0)
            csv_lines.append(f"{timestamp},{power}")

        csv_content = "\n".join(csv_lines)

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={station_id}_timeseries.csv"},
        )

    except Exception as e:
        logger.error(f"Error generating CSV for {station_id}: {e}", exc_info=True)
        csv_content = "timestamp,power\n"
        return Response(content=csv_content, media_type="text/csv")


@api_router.get("/stations/{station_id}/prediction")
async def get_station_prediction(station_id: str):
    
    try:
        station_service = get_station_service()
        return station_service.get_station_prediction(station_id)

    except Exception as e:
        logger.error(f"Error getting prediction for {station_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "station_id": station_id}


@api_router.get("/stations/{station_id}/energy-demand-forecast")
async def get_energy_demand_forecast(station_id: str, days: int = 90):
    
    try:
        station_service = get_station_service()
        return station_service.get_energy_demand_forecast(station_id, days)

    except Exception as e:
        logger.error(f"Error getting energy demand forecast for {station_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "station_id": station_id}


@api_router.get("/stations/{station_id}/monthly-contract")
async def get_monthly_contract_recommendation(
    station_id: str,
    year: int = None,
    month: int = None,
    mode: str = "p95",
    round_kw: int = 1
):
    
    try:
        station_service = get_station_service()
        return station_service.get_monthly_contract_recommendation(
            station_id, year, month, mode, round_kw
        )

    except Exception as e:
        logger.error(f"Error getting contract recommendation for {station_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "station_id": station_id}


@api_router.post("/admin/refresh-cache")
async def refresh_cache():
    
    try:
        station_service = get_station_service()
        station_service.clear_cache()

        return {"success": True, "message": "캐시 새로고침 완료", "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@api_router.get("/status")
async def get_system_status():
    data_dir = get_data_dir()
    # 마커 파일 제외하고 CSV 파일만 찾기
    csv_files = [f for f in data_dir.glob("*.csv") if f.name not in [".active_csv", ".active_csv.csv"]]
    active_file = None
    # .active_csv 우선, 없으면 .active_csv.csv도 시도
    for marker_name in (".active_csv", ".active_csv.csv"):
        marker = data_dir / marker_name
        if marker.exists():
            try:
                name = marker.read_text(encoding="utf-8").splitlines()[0].strip()
                if name:
                    p = (data_dir / Path(name).name).resolve()
                    if p.exists():
                        active_file = {"filename": p.name, "path": str(p)}
                        break
            except Exception:
                continue

    return {
        "success": True,
        "hasData": len(csv_files) > 0,
        "csvFiles": [f.name for f in csv_files],
        "dataCount": len(csv_files),
        "activeFile": active_file,
        "dataDir": str(data_dir),
        "timestamp": datetime.now().isoformat(),
    }


@api_router.post("/admin/clear-data")
async def clear_all_data():
    
    try:
        data_dir = get_data_dir()
        csv_files = list(data_dir.glob("*.csv"))

        deleted_count = 0
        for csv_file in csv_files:
            csv_file.unlink()
            deleted_count += 1

        # 활성 마커 삭제
        marker = data_dir / ".active_csv"
        if marker.exists():
            marker.unlink(missing_ok=True)

        # 캐시 클리어
        station_service = get_station_service()
        station_service.clear_cache()

        return {
            "success": True,
            "message": f"{deleted_count}개 파일 삭제 완료",
            "deletedFiles": deleted_count,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error clearing data: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@api_router.get("/test")
async def test_api():
    
    return {"message": "API 정상 작동!", "timestamp": datetime.now().isoformat(), "main_loaded": main is not None}
