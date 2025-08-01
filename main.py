import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import logging
import os
import pandas as pd
from functools import lru_cache
from typing import Dict, Any, List, Optional

from prediction.predictor import RealTimePowerPredictor
from prediction.scheduler import PredictionScheduler
from utils.config import PredictionConfig, ConfigManager
from utils.logger import setup_logger
from data.loader import ChargingDataLoader

# 전역 변수
predictor = None
scheduler = None
logger = None

# 캐시 설정
CACHE_EXPIRE_MINUTES = 10
_stations_cache = None
_cache_timestamp = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global predictor, scheduler, logger
    
    config = ConfigManager().config
    logger = setup_logger("main", "logs/main.log")
    
    predictor = RealTimePowerPredictor("DEFAULT_STATION")
    scheduler = PredictionScheduler()
    
    logger.info("100kW 급속충전소 전력 예측 시스템 시작")
    scheduler.start_scheduled_jobs()
    
    yield
    
    if scheduler:
        scheduler.stop()
    logger.info("시스템 종료")


# FastAPI 앱 생성
app = FastAPI(
    title="100kW 급속충전소 전력 예측 API",
    description="CSV 데이터 기반 전력 수요 예측 및 계약 최적화 시스템",
    version="2.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# 정적 파일 및 템플릿 설정
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

if os.path.exists("templates"):
    templates = Jinja2Templates(directory="templates")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === 핵심 데이터 로직 ===
def extract_stations_from_csv() -> Dict[str, Dict[str, Any]]:
    """CSV에서 충전소 정보 추출"""
    try:
        logger.info("CSV에서 충전소 정보 추출 시작...")
        
        # 전체 데이터 로드
        loader = ChargingDataLoader("ALL")
        df = loader.load_historical_sessions(90)  # 3개월 데이터
        
        if df.empty:
            logger.warning("CSV 데이터가 비어있습니다.")
            return {}
        
        stations = {}
        
        # 충전소ID별로 그룹화
        if '충전소ID' in df.columns:
            station_ids = df['충전소ID'].unique()
            logger.info(f"발견된 충전소: {len(station_ids)}개")
            
            for station_id in station_ids:
                station_df = df[df['충전소ID'] == station_id]
                
                # 기본 정보
                station_info = {
                    "id": station_id,
                    "name": extract_station_name(station_df),
                    "location": extract_station_location(station_df),
                    "charger_type": extract_charger_type(station_df),
                    "connector_type": extract_connector_type(station_df),
                    "region": extract_region(station_df),
                    "city": extract_city(station_df),
                    "status": determine_station_status(station_df),
                    "data_sessions": len(station_df),
                    "date_range": get_date_range(station_df),
                    "last_activity": get_last_activity(station_df)
                }
                
                stations[station_id] = station_info
            
            # 전체 분석 옵션 추가
            if stations:
                stations["ALL"] = {
                    "id": "ALL",
                    "name": "전체 충전소 통합 분석",
                    "location": f"전국 ({len(station_ids)}개 충전소)",
                    "charger_type": "100kW 급속충전기",
                    "connector_type": "DC콤보",
                    "region": "전국",
                    "city": "전체",
                    "status": "정상 운영",
                    "data_sessions": len(df),
                    "date_range": get_date_range(df),
                    "last_activity": get_last_activity(df)
                }
        
        logger.info(f"✅ {len(stations)}개 충전소 정보 추출 완료")
        return stations
        
    except Exception as e:
        logger.error(f"CSV 충전소 정보 추출 실패: {e}")
        return {}


# 데이터 추출 헬퍼 함수들
def extract_station_name(station_df: pd.DataFrame) -> str:
    """충전소명 추출"""
    if '충전소명' in station_df.columns and not station_df['충전소명'].empty:
        return station_df['충전소명'].iloc[0]
    
    station_id = station_df['충전소ID'].iloc[0] if '충전소ID' in station_df.columns else "Unknown"
    return f"충전소 {station_id}"


def extract_station_location(station_df: pd.DataFrame) -> str:
    """충전소 주소 추출"""
    if '충전소주소' in station_df.columns and not station_df['충전소주소'].empty:
        return station_df['충전소주소'].iloc[0]
    return "주소 정보 없음"


def extract_charger_type(station_df: pd.DataFrame) -> str:
    """충전기 타입 추출"""
    if '충전기 구분' in station_df.columns and not station_df['충전기 구분'].empty:
        charger_type = station_df['충전기 구분'].iloc[0]
        return f"{charger_type}"
    return "100kW 급속충전기"


def extract_connector_type(station_df: pd.DataFrame) -> str:
    """커넥터 타입 추출"""
    if '커넥터명' in station_df.columns and not station_df['커넥터명'].empty:
        return station_df['커넥터명'].iloc[0]
    return "DC콤보"


def extract_region(station_df: pd.DataFrame) -> str:
    """지역 정보 추출"""
    location = extract_station_location(station_df)
    if location and location != "주소 정보 없음":
        parts = location.split()
        if parts:
            return parts[0]  # 첫 번째 부분 (예: 서울시, 경기도)
    return "미상"


def extract_city(station_df: pd.DataFrame) -> str:
    """도시 정보 추출"""
    location = extract_station_location(station_df)
    if location and location != "주소 정보 없음":
        parts = location.split()
        if len(parts) >= 2:
            return parts[1]  # 두 번째 부분 (예: 강남구, 수원시)
    return "미상"


def determine_station_status(station_df: pd.DataFrame) -> str:
    """충전소 상태 판단"""
    if '충전시작일시' not in station_df.columns:
        return "상태 불명"
    
    try:
        latest_session = station_df['충전시작일시'].max()
        if pd.isna(latest_session):
            return "상태 불명"
        
        days_ago = (datetime.now() - latest_session).days
        
        if days_ago <= 7:
            return "정상 운영"
        elif days_ago <= 30:
            return "주의 필요"
        else:
            return "점검 필요"
            
    except Exception:
        return "상태 불명"


def get_date_range(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """데이터 날짜 범위"""
    if '충전시작일시' not in df.columns:
        return {"start": None, "end": None}
    
    try:
        start_date = df['충전시작일시'].min()
        end_date = df['충전시작일시'].max()
        
        return {
            "start": start_date.isoformat() if pd.notna(start_date) else None,
            "end": end_date.isoformat() if pd.notna(end_date) else None
        }
    except Exception:
        return {"start": None, "end": None}


def get_last_activity(df: pd.DataFrame) -> Optional[str]:
    """마지막 활동 일시"""
    if '충전시작일시' not in df.columns:
        return None
    
    try:
        latest = df['충전시작일시'].max()
        return latest.isoformat() if pd.notna(latest) else None
    except Exception:
        return None


# 캐싱 로직
def get_stations_with_cache() -> Dict[str, Dict[str, Any]]:
    """캐시를 활용한 충전소 정보 조회"""
    global _stations_cache, _cache_timestamp
    
    # 캐시 유효성 검사
    if (_stations_cache is not None and _cache_timestamp is not None and 
        datetime.now() - _cache_timestamp < timedelta(minutes=CACHE_EXPIRE_MINUTES)):
        logger.debug("캐시된 충전소 정보 사용")
        return _stations_cache
    
    # 새로 로드
    logger.info("새로운 충전소 정보 로딩...")
    stations = extract_stations_from_csv()
    
    # 캐시 업데이트
    _stations_cache = stations
    _cache_timestamp = datetime.now()
    
    return stations


def invalidate_cache():
    """캐시 무효화"""
    global _stations_cache, _cache_timestamp
    _stations_cache = None
    _cache_timestamp = None
    logger.info("충전소 캐시 무효화")


# === 기본 엔드포인트 ===
@app.get("/")
async def root():
    """루트 엔드포인트"""
    try:
        stations = get_stations_with_cache()
        active_stations = len([s for s in stations.values() if s["status"] == "정상 운영"])
        total_sessions = sum(s.get("data_sessions", 0) for s in stations.values() if s["id"] != "ALL")
        
        return {
            "message": "⚡ 100kW 급속충전소 전력 예측 시스템",
            "version": "2.2.0",
            "status": "running",
            "data_driven": True,
            "stations": {
                "total": len(stations) - 1 if "ALL" in stations else len(stations),
                "active": active_stations - 1 if "ALL" in stations else active_stations,
                "total_sessions": total_sessions
            },
            "features": [
                "CSV 데이터 기반 분석",
                "실시간 전력 예측", 
                "월별 계약 권고",
                "시각화 대시보드",
                "동적 충전소 관리"
            ],
            "endpoints": {
                "station_selector": "/station-selector",
                "dashboard": "/dashboard/{station_id}",
                "api_docs": "/api/docs",
                "stations_list": "/api/stations",
                "predict": "/predict/{station_id}",
                "analysis": "/api/station-analysis/{station_id}"
            },
            "cache_info": {
                "enabled": True,
                "expire_minutes": CACHE_EXPIRE_MINUTES,
                "last_updated": _cache_timestamp.isoformat() if _cache_timestamp else None
            }
        }
    except Exception as e:
        logger.error(f"루트 엔드포인트 오류: {e}")
        return {"error": "시스템 초기화 중", "message": str(e)}


@app.get("/health")
async def health_check():
    """헬스 체크"""
    try:
        stations = get_stations_with_cache()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "stations_loaded": len(stations),
            "cache_active": _stations_cache is not None,
            "csv_accessible": True
        }
    except Exception as e:
        return {
            "status": "degraded",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


# === 페이지 라우트 ===
@app.get("/station-selector", response_class=HTMLResponse)
async def station_selector(request: Request):
    """충전소 선택 페이지"""
    try:
        stations = get_stations_with_cache()
        
        if not stations:
            raise HTTPException(status_code=503, detail="충전소 데이터를 로드할 수 없습니다. CSV 파일을 확인해주세요.")
        
        if 'templates' in globals():
            return templates.TemplateResponse("station_selector.html", {
                "request": request,
                "stations": stations,
                "total_stations": len(stations)
            })
        else:
            raise HTTPException(status_code=404, detail="템플릿 파일을 찾을 수 없습니다.")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"station-selector 페이지 오류: {e}")
        raise HTTPException(status_code=500, detail=f"페이지 로드 실패: {str(e)}")


@app.get("/dashboard/{station_id}", response_class=HTMLResponse)
async def dashboard(request: Request, station_id: str):
    """충전소별 대시보드"""
    try:
        stations = get_stations_with_cache()
        
        if station_id not in stations:
            available_ids = list(stations.keys())
            raise HTTPException(
                status_code=404, 
                detail=f"충전소 '{station_id}'를 찾을 수 없습니다. 사용 가능한 ID: {available_ids}"
            )
        
        station_info = stations[station_id]
        
        if 'templates' in globals():
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "station_id": station_id,
                "station_info": station_info
            })
        else:
            raise HTTPException(status_code=404, detail="템플릿 파일을 찾을 수 없습니다.")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"대시보드 페이지 오류: {e}")
        raise HTTPException(status_code=500, detail=f"대시보드 로드 실패: {str(e)}")


# === API 엔드포인트 ===
@app.get("/api/stations")
async def list_stations():
    """충전소 목록 API"""
    try:
        stations = get_stations_with_cache()
        
        stations_list = []
        for station_id, station in stations.items():
            if station_id == "ALL":
                continue
            
            # 간단한 이용률 계산
            try:
                loader = ChargingDataLoader(station_id)
                summary = loader.get_data_summary()
                utilization = "N/A"
                if 'power_stats' in summary and summary['power_stats']:
                    utilization = round((summary['power_stats']['mean'] / 100) * 100, 1)
            except:
                utilization = "N/A"
            
            stations_list.append({
                "id": station_id,
                "name": station["name"],
                "location": station["location"],
                "charger_type": station["charger_type"],
                "connector_type": station["connector_type"],
                "status": station["status"],
                "region": station["region"],
                "city": station["city"],
                "data_sessions": station["data_sessions"],
                "utilization": f"{utilization}%" if utilization != "N/A" else "N/A",
                "last_activity": station["last_activity"]
            })
        
        return {
            "stations": stations_list,
            "total": len(stations_list),
            "active": len([s for s in stations_list if s["status"] == "정상 운영"]),
            "regions": list(set(s["region"] for s in stations_list)),
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"충전소 목록 API 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predict/{station_id}")
async def predict_peak_power(station_id: str):
    """실시간 전력 예측"""
    try:
        stations = get_stations_with_cache()
        
        if station_id not in stations:
            raise HTTPException(status_code=404, detail=f"충전소 '{station_id}'를 찾을 수 없습니다.")
        
        station_predictor = RealTimePowerPredictor(station_id)
        result = await station_predictor.predict_next_hour_peak()
        
        if result is None:
            # 기본 예측값 생성
            loader = ChargingDataLoader(station_id)
            patterns = loader.analyze_charging_patterns()
            
            predicted_peak = 45.0
            if 'power_statistics' in patterns:
                stats = patterns['power_statistics']
                predicted_peak = min(stats.get('percentile_95', 50), 95)
            
            result = {
                "station_id": station_id,
                "station_name": stations[station_id]["name"],
                "predicted_peak": round(predicted_peak, 1),
                "confidence": 0.75,
                "timestamp": datetime.now().isoformat(),
                "method": "statistical_baseline"
            }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"예측 API 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monthly-contract/{station_id}")
async def get_monthly_contract_recommendation(station_id: str, year: int, month: int):
    """월별 계약 전력 권고"""
    try:
        stations = get_stations_with_cache()
        
        if station_id not in stations:
            raise HTTPException(status_code=404, detail=f"충전소 '{station_id}'를 찾을 수 없습니다.")
        
        loader = ChargingDataLoader(station_id)
        patterns = loader.analyze_charging_patterns()
        
        if 'power_statistics' in patterns:
            stats = patterns['power_statistics']
            
            # 계절성 조정
            seasonal_factors = {
                12: 1.20, 1: 1.20, 2: 1.15,
                3: 1.05, 4: 1.0, 5: 1.0,
                6: 1.10, 7: 1.15, 8: 1.10,
                9: 1.0, 10: 1.05, 11: 1.10
            }
            
            seasonal_factor = seasonal_factors.get(month, 1.0)
            predicted_peak = stats['percentile_95'] * seasonal_factor
            predicted_peak = min(predicted_peak, 95.0)
            
            recommended_contract = max(
                int(predicted_peak * 1.15 / 10) * 10,
                int(stats['max'] * 1.10 / 10) * 10
            )
            
            return {
                "station_id": station_id,
                "station_name": stations[station_id]["name"],
                "year": year,
                "month": month,
                "predicted_peak_kw": round(predicted_peak, 1),
                "recommended_contract_kw": recommended_contract,
                "seasonal_factor": seasonal_factor,
                "historical_data": {
                    "max_power": round(stats['max'], 1),
                    "avg_power": round(stats['mean'], 1),
                    "sessions_analyzed": stats['count']
                },
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "station_id": station_id,
                "station_name": stations[station_id]["name"],
                "year": year,
                "month": month,
                "predicted_peak_kw": 80.0,
                "recommended_contract_kw": 100,
                "note": "데이터 부족으로 보수적 추정"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"월별 계약 API 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/station-analysis/{station_id}")
async def get_station_detailed_analysis(station_id: str):
    """충전소 상세 분석"""
    try:
        stations = get_stations_with_cache()
        
        if station_id not in stations:
            raise HTTPException(status_code=404, detail=f"충전소 '{station_id}'를 찾을 수 없습니다.")
        
        loader = ChargingDataLoader(station_id)
        
        summary = loader.get_data_summary()
        patterns = loader.analyze_charging_patterns()
        realtime_status = loader.load_realtime_status()
        external_factors = loader.load_external_factors()
        
        # 성능 분석
        performance_analysis = {}
        charts_data = {}
        
        if 'power_statistics' in patterns:
            stats = patterns['power_statistics']
            avg_power = stats['mean']
            max_power = stats['max']
            
            utilization_rate = (avg_power / 100) * 100
            
            performance_analysis = {
                "utilization_rate": round(utilization_rate, 1),
                "peak_utilization": round((max_power / 100) * 100, 1),
                "average_session_power": round(avg_power, 1),
                "maximum_recorded_power": round(max_power, 1),
                "efficiency_grade": "A" if utilization_rate > 50 else "B" if utilization_rate > 30 else "C"
            }
            
            # 차트 데이터 준비
            hourly_patterns = patterns.get('hourly_patterns', {})
            hourly_pattern = [
                hourly_patterns.get(str(h), {}).get('avg_power', 0) for h in range(24)
            ]
            
            charts_data = {
                "hourly_pattern": hourly_pattern,
                "monthly_predictions": {
                    "data": [round(stats['percentile_95'] * factor, 1) 
                            for factor in [1.20, 1.15, 1.05, 1.0, 1.0, 1.10, 1.15, 1.10, 1.0, 1.05, 1.10, 1.20]],
                    "labels": ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]
                }
            }
        
        return {
            "station_id": station_id,
            "timestamp": datetime.now().isoformat(),
            "station_info": stations[station_id],
            "summary": summary,
            "patterns": patterns,
            "performance_analysis": performance_analysis,
            "charts_data": charts_data,
            "realtime_status": realtime_status,
            "external_factors": external_factors
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상세 분석 API 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === 관리 API ===
@app.post("/api/admin/refresh-cache")
async def refresh_cache():
    """캐시 새로고침"""
    try:
        invalidate_cache()
        stations = get_stations_with_cache()
        
        return {
            "message": "캐시가 성공적으로 새로고침되었습니다.",
            "stations_loaded": len(stations),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"캐시 새로고침 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === 오류 처리 ===
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "요청한 리소스를 찾을 수 없습니다.",
            "help": {
                "available_endpoints": [
                    "/station-selector",
                    "/dashboard/{station_id}",
                    "/api/stations",
                    "/predict/{station_id}",
                    "/api/docs"
                ],
                "note": "모든 충전소 정보는 CSV 데이터에서 동적으로 로드됩니다."
            }
        }
    )


if __name__ == "__main__":
    config = ConfigManager().config
    
    print("=" * 60)
    print("⚡ 100kW 급속충전소 전력 예측 시스템 (CSV 기반)")
    print("=" * 60)
    print(f"🌐 서버 주소: http://{config.api_host}:{config.api_port}")
    print(f"🏢 충전소 선택: http://{config.api_host}:{config.api_port}/station-selector")
    print(f"📊 API 문서: http://{config.api_host}:{config.api_port}/api/docs")
    print(f"💾 CSV 기반 동적 로딩")
    print("=" * 60)
    
    uvicorn.run(
        "main:app",
        host=config.api_host,
        port=config.api_port,
        workers=config.api_workers,
        reload=True,
        log_level="info"
    )